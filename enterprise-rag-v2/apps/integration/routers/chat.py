"""
聊天路由 - 多平台消息接入核心入口 (v2.1 多租户架构)

支持飞书、企业微信等平台的 Webhook 消息接收和处理:

  飞书/企微 → Webhook → POST /api/v1/integration/chat → 租户路由 → RAG 与资源统计

业务流程:
  1. Challenge 验证 (飞书)
  2. IP/Header 识别 (平台判断)
  3. 消息解析 (text 提取)
  4. 租户路由 (v2.1 核心: PlatformAppConfigService)
  5. 用户映射 (app_config_id 透传)
  6. 资源用量检查与统计
  7. RAG 知识库检索
  8. 使用量计数
  9. 回复发送 (租户专属凭证)
  10. 格式化响应
"""

import uuid
import json
import base64
import os
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

from apps.integration.models.request import ChatRequest
from apps.integration.models.response import ChatResponse
from apps.integration.services.query_service import QueryService
from apps.integration.config import settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-gateway-secret", "x-api-key"}
_SENSITIVE_KEYS = {"token", "authorization", "cookie", "secret", "password", "api_key", "x-api-key"}

router = APIRouter(prefix="/chat", tags=["Integration"])


def _sanitize_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}


def _mask_token(token: Optional[str]) -> str:
    if not token:
        return "None"
    return f"{token[:8]}***"


def _sanitize_payload(value):
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if str(key).lower() in _SENSITIVE_KEYS:
                masked[key] = "***"
            else:
                masked[key] = _sanitize_payload(item)
        return masked
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    return value


def _looks_like_feishu_event_v2(body_data: Optional[dict]) -> bool:
    """
    通过请求体识别飞书事件（schema 2.0）。

    经 frpc/反代时，源 IP 常为 127.0.0.1，且部分环境不转发 x-lark-* 头，
    仅靠 IP/头会误判为「非飞书」并走到缺少 X-Platform-User-Id 的分支。
    """
    if not body_data or not isinstance(body_data, dict):
        return False
    if body_data.get("schema") == "2.0" and isinstance(body_data.get("header"), dict):
        return True
    h = body_data.get("header")
    if isinstance(h, dict) and h.get("event_type") and "event" in body_data:
        return True
    return False


def decrypt_feishu_event(encrypt_text: str, encrypt_key: str) -> dict:
    """
    解密飞书事件订阅 payload。

    飞书密文结构:
      16 bytes random + 4 bytes msg_len + msg + app_id
    """
    key = base64.b64decode(f"{encrypt_key}=")
    encrypted_data = base64.b64decode(encrypt_text)
    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded_plain = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded_plain) + unpadder.finalize()

    if len(plain) < 20:
        raise ValueError("飞书解密后的数据长度异常")

    body = plain[16:]
    msg_len = int.from_bytes(body[:4], byteorder="big")
    msg = body[4: 4 + msg_len]
    return json.loads(msg.decode("utf-8"))


def _build_kb_selection_card(kb_list: list) -> dict:
    """构建知识库选择卡片"""
    actions = []
    for kb in kb_list:
        name = kb["name"]
        kb_id = kb["id"]
        desc = kb.get("description", "")
        text_lines = [f"**{name}**"]
        if desc:
            text_lines.append(desc)
        actions.append({
            "tag": "button",
            "text": {"tag": "lark_md", "content": "\n".join(text_lines)},
            "url": None,
            "multi_url": None,
            "type": "default",
            "value": json.dumps({"action": "kb_select", "dataset_id": kb_id, "dataset_name": name}),
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "选择知识库"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"请选择要查询的知识库（共 {len(kb_list)} 个）：\n选择后将记住偏好，后续提问自动在该知识库中搜索。",
                },
            },
            {
                "tag": "action",
                "layout": "flow",
                "actions": actions,
            },
        ],
    }


async def _handle_card_action(
    body_data: dict,
    platform: str,
    db_instance,
    redis_instance,
    pac_service,
    app_config: dict,
    request_id: str,
):
    """处理飞书卡片交互回调（知识库选择等）"""
    from fastapi.responses import JSONResponse

    event = body_data.get("event", {})
    action = event.get("action", {})
    action_value_str = action.get("value", "{}")
    operator = event.get("operator", {})
    open_id = operator.get("open_id", "")

    try:
        action_value = json.loads(action_value_str)
    except (json.JSONDecodeError, TypeError):
        action_value = {}

    action_type = action_value.get("action", "")

    if action_type == "kb_select":
        dataset_id = action_value.get("dataset_id")
        dataset_name = action_value.get("dataset_name", dataset_id)

        # 确定会话键：优先用群聊 chat_id，私聊用 open_id
        context = event.get("context", {})
        chat_id = context.get("open_chat_id") or body_data.get("event", {}).get("context", {}).get("open_chat_id", "")
        if not chat_id:
            chat_id = "_private_"

        conversation_key = f"feishu:{chat_id}:{open_id}"

        # 存储到 Redis
        if redis_instance:
            try:
                kb_pref_key = f"kb_pref:{conversation_key}"
                await redis_instance.setex(kb_pref_key, 86400 * 7, json.dumps({
                    "dataset_id": dataset_id,
                    "dataset_name": dataset_name,
                    "updated_at": None,  # placeholder
                }))
                logger.info(
                    f"[CardAction] KB 偏好已保存: key={kb_pref_key}, kb={dataset_name}",
                    extra={"request_id": request_id},
                )
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[CardAction] Redis 写入 KB 偏好失败: {e}")

        # 发送确认消息
        adapter_config = build_adapter_config(platform, app_config)
        adapter = None
        if platform == "feishu":
            from apps.integration.adapters.factory import AdapterFactory
            adapter = AdapterFactory.create_adapter(platform, adapter_config)

        if adapter:
            confirm_msg = f"已选择知识库：**{dataset_name}**\n后续提问将自动在该知识库中搜索。\n发送 /kb 可随时切换。"
            # card.action.trigger 场景中 chat_id 可能为空，统一按私聊处理
            await adapter.send_message(
                user_id=open_id,
                content=confirm_msg,
                chat_id=None,
                chat_type="private",
            )
            logger.info(
                f"[CardAction] 确认消息已发送: kb={dataset_name}",
                extra={"request_id": request_id},
            )

    return JSONResponse(content={"success": True}, status_code=200)


def get_query_service(request: Request) -> QueryService:
    """依赖注入: 获取QueryService实例"""
    
    db = getattr(request.app.state, 'db', None)
    # 这里只读取已初始化实例，避免在同步依赖里直接调用 async get_redis() 产生未 await 警告
    redis = getattr(request.app.state, 'redis', None)
    quota_svc = getattr(request.app.state, 'quota_service', None)
    
    return QueryService(
        db=db,
        redis=redis,
        quota_service=quota_svc,
        user_mapping_service=None  # 会自动创建
    )


def build_adapter_config(platform: str, app_config: dict) -> dict:
    """构建适配器配置"""
    config = app_config.copy()
    # 移除内部字段，但保留 app_id 和 credentials
    config.pop("id", None)
    config.pop("tenant_id", None)
    config.pop("platform", None)
    config.pop("encrypted_credentials", None)
    config.pop("is_active", None)
    config.pop("config", None)
    config.pop("created_at", None)
    config.pop("updated_at", None)
    config.pop("_is_default", None)
    
    # 提取 app_secret 到顶层
    if "credentials" in config:
        credentials = config.get("credentials", {})
        if isinstance(credentials, dict):
            if "app_secret" in credentials:
                config["app_secret"] = credentials["app_secret"]
            # 提取其他必要字段
            if "verification_token" in credentials:
                config["verification_token"] = credentials["verification_token"]
            if "encrypt_key" in credentials:
                config["encrypt_key"] = credentials["encrypt_key"]
        config.pop("credentials", None)
    
    # 保留 app_id 用于获取 access_token
    return config


@router.post("", response_model=None)
async def integration_chat(
    request: Request,
    query_svc: QueryService = Depends(get_query_service),
):
    """
    多平台消息接入统一聊天入口

    支持平台:
      - 飞书: 事件订阅 Webhook
      - 企业微信: 消息回调
      - 其他平台: X-Platform + X-Platform-User-Id 头

    响应格式:
      - 正常: {success:true, answer:"...", sources:[...], quota_info:{...}}
      - 资源上限: {success:true, answer:"资源上限提示...", quota_exceeded:true}
      - 需要绑定: {success:true, answer:"绑定提示..."}
    """
    # ===== Step 0: 优先处理飞书 Challenge 验证（必须在所有其他逻辑之前）=====
    try:
        # 记录完整的请求信息
        logger.info(f"[Chat] 收到请求: POST /api/v1/integration/chat")
        logger.info(f"[Chat] 请求头(脱敏): {_sanitize_headers(request.headers)}")
        logger.info(f"[Chat] 客户端IP: {request.client.host if request.client else 'unknown'}")
        
        raw_body = await request.body()
        logger.info(f"[Chat] 收到请求体，大小: {len(raw_body)} bytes, Content-Type: {request.headers.get('content-type', 'unknown')}")
        logger.info("[Chat] 请求体预览已省略（避免敏感信息泄露）")

        if raw_body:
            try:
                body_data = json.loads(raw_body)
                logger.info(f"[Chat] 请求体解析成功，类型: {type(body_data).__name__}")
                if isinstance(body_data, dict):
                    logger.info(f"[Chat] 请求体keys: {list(body_data.keys())}")
                    
                    # 检查是否是飞书的 challenge 验证请求
                    if "challenge" in body_data:
                        challenge_value = body_data["challenge"]
                        logger.info(f"[Chat] ✅ 检测到飞书Challenge验证请求，challenge: {challenge_value[:50]}...")
                        # 飞书要求原样返回challenge值，确保格式完全正确
                        response = {"challenge": challenge_value}
                        logger.info("[Chat] 返回Challenge响应")
                        return JSONResponse(content=response, status_code=200, headers={"Content-Type": "application/json"})
                    # 检查是否是飞书的加密消息
                    elif "encrypt" in body_data:
                        logger.info(f"[Chat] ✅ 检测到飞书加密消息，开始解密")
                        encrypt_text = body_data.get("encrypt", "")
                        encrypt_key = (
                            settings.feishu_encrypt_key
                            or os.getenv("FEISHU_ENCRYPT_KEY")
                            or os.getenv("INTEGRATION_FEISHU_ENCRYPT_KEY")
                        )
                        if not encrypt_key:
                            logger.error("[Chat] ❌ FEISHU_ENCRYPT_KEY 未配置，无法解密飞书消息")
                            return JSONResponse(content={"success": True}, status_code=200)
                        try:
                            decrypted_body = decrypt_feishu_event(encrypt_text, encrypt_key)
                            logger.info(f"[Chat] ✅ 飞书消息解密成功，keys: {list(decrypted_body.keys())}")
                            body_data = decrypted_body
                        except (ValueError, TypeError, json.JSONDecodeError) as decrypt_err:
                            logger.error(f"[Chat] ❌ 飞书消息解密失败: {decrypt_err}", exc_info=True)
                            # 返回 200 避免飞书重试风暴，但保留错误日志用于排查
                            return JSONResponse(content={"success": True}, status_code=200)
                    else:
                        logger.info(f"[Chat] 非Challenge请求，继续正常处理流程")
                else:
                    logger.warning(f"[Chat] 请求体不是字典类型: {type(body_data).__name__}")
                    body_data = None
            except json.JSONDecodeError as e:
                logger.error(f"[Chat] ❌ JSON解析失败: {str(e)}")
                body_data = None
        else:
            logger.warning("[Chat] 请求体为空")
            body_data = None

    except (RuntimeError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as e:
        logger.error(f"[Chat] ❌ 处理请求体时发生异常: {type(e).__name__}: {str(e)}", exc_info=True)
        body_data = None
    
    # ===== Step 1: 解析请求头 + 平台识别 =====
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    platform = "feishu"
    platform_user_id = ""
    is_platform_webhook = False
    
    # 消息去重检查
    message_id = None
    if body_data and "event" in body_data and "message" in body_data["event"]:
        message_id = body_data["event"]["message"].get("message_id")
    elif body_data and "metadata" in body_data:
        message_id = body_data["metadata"].get("message_id")
    
    # 使用Redis进行消息去重
    if message_id:
        redis_instance = getattr(request.app.state, 'redis', None)
        if not redis_instance:
            cache_mod = __import__('infrastructure.cache', fromlist=['get_redis'])
            redis_instance = await cache_mod.get_redis()
        if redis_instance:
            try:
                event_id = None
                if body_data and "header" in body_data:
                    event_id = body_data["header"].get("event_id")
                dedupe_id = event_id or message_id
                key = f"processed_message:{platform}:{dedupe_id}"
                if await redis_instance.exists(key):
                    logger.info(f"[Chat] 消息已处理过，跳过重复处理: {dedupe_id}")
                    return JSONResponse(content={"success": True, "message": "Message already processed"}, status_code=200)
                # 设置过期时间为24小时
                await redis_instance.setex(key, 86400, "1")
                logger.info(f"[Chat] 标记消息为已处理: {dedupe_id}")
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[Chat] 消息去重检查失败: {e}")
    
    # 检查是否是飞书的请求（通过请求头或 IP 地址）
    client_ip = request.client.host if request.client else "unknown"
    ip_address = client_ip.split(":")[0]
    feishu_ip_ranges = [
        "101.126",
        "123.58",
        "180.163"
    ]
    
    is_feishu_ip = any(ip_address.startswith(ip_range) for ip_range in feishu_ip_ranges)
    is_feishu_request = any(key.lower().startswith("x-lark-") for key in request.headers)
    is_feishu_by_body = _looks_like_feishu_event_v2(body_data if isinstance(body_data, dict) else None)

    if is_feishu_by_body and not is_feishu_ip and not is_feishu_request:
        logger.info(
            "[Chat] 通过请求体识别为飞书事件（常见于 frpc/反代：源 IP 非飞书段或未转发 x-lark-* 头）"
        )

    if is_feishu_ip or is_feishu_request or is_feishu_by_body:
        platform = "feishu"
        is_platform_webhook = True
        event_type = ""
        if body_data and "header" in body_data:
            event_type = body_data.get("header", {}).get("event_type", "")

        # 飞书会推送已读、回执等事件；这里只处理接收消息和卡片点击事件
        if event_type == "card.action.trigger":
            # ============================================================
            # 处理卡片交互回调（知识库选择按钮点击等）
            # ============================================================
            logger.info("[Chat] 收到 card.action.trigger 事件")
            kb_result = await _handle_card_action(
                body_data, platform, db_instance, redis_instance,
                pac_service, app_config, request_id
            )
            return kb_result

        if event_type and event_type != "im.message.receive_v1":
            logger.info(f"[Chat] 忽略非消息接收事件: event_type={event_type}")
            return JSONResponse(
                content={"success": True, "ignored_event_type": event_type},
                status_code=200
            )

        # 尝试从请求体中获取 user_id
        if body_data and "event" in body_data and "sender" in body_data["event"]:
            sender = body_data["event"]["sender"]
            sender_id = sender.get("sender_id", {})
            if sender_id.get("open_id"):
                platform_user_id = sender_id["open_id"]
            elif sender_id.get("user_id"):
                platform_user_id = sender_id["user_id"]
            else:
                logger.warning("[Chat] 飞书消息中未找到有效的用户ID")
        else:
            logger.warning("[Chat] 飞书消息格式不符合预期，缺少sender信息")
        
        # 检查是否是飞书消息事件
        if body_data and "header" in body_data and body_data["header"].get("event_type") == "im.message.receive_v1":
            event = body_data.get("event", {})
            message = event.get("message", {})
            sender_type = event.get("sender", {}).get("sender_type")
            content_str = message.get("content", "{}")
            message_type = message.get("message_type", "")
            
            # 在转换之前保存原始 token
            feishu_token = body_data.get("header", {}).get("token", "")

            # 只处理用户发送的文本消息，避免机器人自身消息触发重复回复
            if sender_type != "user":
                logger.info(f"[Chat] 忽略非用户消息: sender_type={sender_type}")
                body_data = None
            elif message_type == "text":
                try:
                    content_dict = json.loads(content_str)
                    query_text = content_dict.get("text", "").strip()
                    if query_text:
                        logger.info(f"[Chat] 飞书消息内容: {query_text[:100]}")
                        # 构建符合 ChatRequest 格式的请求体
                        body_data = {
                            "query": query_text,
                            "conversation_id": message.get("chat_id", ""),
                            "metadata": {
                                "platform": "feishu",
                                "message_id": message.get("message_id", ""),
                                "chat_id": message.get("chat_id", ""),
                                "chat_type": message.get("chat_type", ""),
                                "tenant_key": event.get("tenant_key", ""),
                                "open_id": platform_user_id,
                                "feishu_token": feishu_token
                            }
                        }
                    else:
                        logger.warning("[Chat] 飞书消息内容为空")
                        body_data = None
                except json.JSONDecodeError:
                    logger.error(f"[Chat] 解析飞书消息内容失败: {content_str[:100]}")
                    body_data = None
            else:
                logger.info(f"[Chat] 飞书消息类型非文本: {message_type}")
                body_data = None
    
    elif body_data and body_data.get("MsgType"):
        # 企业微信消息
        platform = "wecom"
        is_platform_webhook = True
        platform_user_id = body_data.get("FromUserName", "unknown")
        if body_data.get("MsgType") == "text":
            body_data = {
                "query": body_data.get("Content", "").strip(),
                "conversation_id": platform_user_id,
                "metadata": {
                    "platform": "wecom",
                    "message_id": body_data.get("MsgId", ""),
                    "open_id": platform_user_id
                }
            }
    
    else:
        # 其他平台或手动调用
        platform = request.headers.get("X-Platform", "feishu")
        platform_user_id = request.headers.get("X-Platform-User-Id", "")
        
        if not platform or not platform_user_id:
            raise HTTPException(
                status_code=400,
                detail="缺少必要的请求头: X-Platform, X-Platform-User-Id",
                headers={"X-Request-ID": request_id}
            )
    
    # ===== Step 2: 解析请求体 =====
    try:
        if body_data is None:
            raise HTTPException(
                status_code=400,
                detail="请求体格式错误",
                headers={"X-Request-ID": request_id}
            )
        
        logger.info(f"[Chat] 创建 ChatRequest，body_data(脱敏): {_sanitize_payload(body_data)}")
        body = ChatRequest(**body_data)
    except HTTPException:
        raise
    except (ValueError, TypeError) as e:
        logger.error(f"[Chat] 解析请求体失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="请求体格式错误",
            headers={"X-Request-ID": request_id}
        )
    
    logger.info(
        f"[Chat] 收到查询请求",
        extra={
            "request_id": request_id,
            "platform": platform,
            "platform_user_id": platform_user_id[:20] + "..." if platform_user_id else "empty",
            "query": body.query[:100],
            "conversation_id": body.conversation_id,
            "message_id": message_id
        }
    )
    
    # ================================================================
    # v2.1 核心: 使用 PlatformAppConfigService 进行租户路由
    # ================================================================
    db_instance = getattr(request.app.state, 'db', None)
    redis_instance = getattr(request.app.state, 'redis', None)

    from apps.integration.services.platform_app_config import PlatformAppConfigService
    pac_service = PlatformAppConfigService(db=db_instance, redis=redis_instance)

    logger.info(f"[Chat] 开始解析 app_id，platform={platform}", extra={"request_id": request_id})
    
    # 直接通过 token 查找 app_id
    header = body_data.get("header", {})
    logger.info(f"[Chat] body_data 结构: {list(body_data.keys())}", extra={"request_id": request_id})
    # 从 body_data 或 metadata 中获取 feishu token
    token = None
    if isinstance(header, dict):
        token = header.get("token")
    if not token:
        metadata = body_data.get("metadata", {})
        if isinstance(metadata, dict):
            token = metadata.get("feishu_token")
    if not token:
        token = body_data.get("token")
    logger.info(f"[Chat] 从 body 获取的 token: {_mask_token(token)}", extra={"request_id": request_id})
    
    if token and platform == "feishu" and db_instance:
        try:
            token_query = """
                SELECT app_id FROM platform_app_configs
                WHERE platform = 'feishu'
                  AND verification_token = :token
                  AND is_active = TRUE
                LIMIT 1
            """
            if hasattr(db_instance, 'fetch_one'):
                token_result = await db_instance.fetch_one(token_query, {"token": token})
            elif hasattr(db_instance, 'execute'):
                query_result = await db_instance.execute(token_query, {"token": token})
                token_result = await query_result.fetch_one()
            else:
                token_result = None
            
            logger.info(f"[Chat] token 查询结果: {token_result}", extra={"request_id": request_id})
            
            if token_result:
                detected_app_id = token_result["app_id"] if hasattr(token_result, '__getitem__') else token_result[0]
                logger.info(f"[Chat] 从 token 反查到 app_id: {detected_app_id}", extra={"request_id": request_id})
            else:
                detected_app_id = await pac_service.resolve_app_id(platform, request, body_data)
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"[Chat] token 查询失败: {e}", extra={"request_id": request_id})
            detected_app_id = await pac_service.resolve_app_id(platform, request, body_data)
    else:
        detected_app_id = await pac_service.resolve_app_id(platform, request, body_data)
    
    logger.info(f"[Chat] 解析到 app_id: {detected_app_id}", extra={"request_id": request_id})

    app_config = None
    if detected_app_id:
        logger.info(f"[Chat] 根据 app_id 查询配置: {detected_app_id}", extra={"request_id": request_id})
        app_config = await pac_service.get_config_by_app_id(platform, detected_app_id)
        logger.info(
            f"[Chat] 查询到配置: app_id={app_config.get('app_id')}, platform={app_config.get('platform')}",
            extra={"request_id": request_id},
        )

    if not app_config:
        logger.info(f"[Chat] 未匹配到 app_config (detected={detected_app_id})，使用默认配置",
                 extra={"request_id": request_id})
        app_config = await pac_service.get_default_config(platform)

    tenant_id_for_mapping = app_config.get("tenant_id")
    effective_app_config_id = app_config.get("id") if not app_config.get("_is_default") else None

    logger.info(f"[Chat] 租户路由完成: tenant={tenant_id_for_mapping}, app_config_id={effective_app_config_id}, "                f"is_default={app_config.get('_is_default')}", extra={"request_id": request_id})

    try:
        # ===== Step 2.5: 知识库选择菜单 ====="
        query_text_stripped = body.query.strip().lower() if body.query else ""
        is_kb_menu_cmd = query_text_stripped in ("/kb", "选择知识库", "切换知识库", "@选择知识库")

        if is_kb_menu_cmd and platform in ("feishu", "wecom"):
            logger.info(f"[Chat] 用户请求知识库选择菜单: {body.query}")
            # 先获取用户的 system_user_id（可能需要映射）
            tmp_user_id_for_kb = None
            tmp_tenant_id_for_kb = tenant_id_for_mapping
            try:
                from apps.integration.config import settings as integration_settings
                mapping_result = await query_svc.user_mapping_service.get_or_create_user(
                    platform=platform,
                    platform_user_id=platform_user_id,
                    auto_register=integration_settings.auto_register_enabled,
                    app_config_id=effective_app_config_id,
                )
                if "system_user_id" in mapping_result and mapping_result["system_user_id"]:
                    tmp_user_id_for_kb = mapping_result["system_user_id"]
                    if not tmp_tenant_id_for_kb:
                        tmp_tenant_id_for_kb = mapping_result.get("tenant_id")
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[Chat] 获取用户映射失败（KB菜单仍会尝试）: {e}")

            if tmp_user_id_for_kb and tmp_tenant_id_for_kb:
                kb_list = await query_svc.get_available_kb_list(
                    int(tmp_tenant_id_for_kb), int(tmp_user_id_for_kb)
                )

                adapter_config = build_adapter_config(platform, app_config)
                from apps.integration.adapters.factory import AdapterFactory
                adapter = AdapterFactory.create_adapter(platform, adapter_config)

                if adapter:
                    if kb_list:
                        card = _build_kb_selection_card(kb_list)
                        chat_id_val = body.metadata.get("chat_id") if hasattr(body, "metadata") else None
                        chat_type_val = body.metadata.get("chat_type") if hasattr(body, "metadata") else None
                        await adapter.send_card_message(
                            user_id=platform_user_id,
                            card=card,
                            chat_id=chat_id_val,
                            chat_type=chat_type_val,
                        )
                        logger.info(f"[Chat] KB选择卡片已发送, kb_count={len(kb_list)}")
                    else:
                        await adapter.send_message(
                            user_id=platform_user_id,
                            content="当前租户下暂无可用知识库，请先在工作台中创建知识库。",
                            chat_id=body.metadata.get("chat_id") if hasattr(body, "metadata") else None,
                            chat_type=body.metadata.get("chat_type") if hasattr(body, "metadata") else None,
                        )

            return JSONResponse(content={"success": True, "action": "kb_menu"}, status_code=200)

        # ===== Step 3: 读取会话级 KB 偏好（Redis）=====
        kb_pref_dataset_id = None
        if platform == "feishu" and redis_instance and platform_user_id:
            try:
                chat_id_for_pref = body.metadata.get("chat_id") if hasattr(body, "metadata") else None
                pref_key = f"kb_pref:feishu:{chat_id_for_pref or '_private_'}:{platform_user_id}"
                pref_raw = await redis_instance.get(pref_key)
                if pref_raw:
                    pref_data = json.loads(pref_raw)
                    kb_pref_dataset_id = pref_data.get("dataset_id")
                    logger.info(f"[Chat] 读取到会话 KB 偏好: {pref_data.get('dataset_name')} ({kb_pref_dataset_id})")
            except (RuntimeError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as e:
                logger.warning(f"[Chat] 读取 KB 偏好失败: {e}")

        # ===== Step 3-7: 核心业务处理 (委托给QueryService) =====
        result = await query_svc.handle_query(
            platform=platform,
            platform_user_id=platform_user_id,
            request_body=body,
            tenant_id=tenant_id_for_mapping,
            system_user_id=None,
            app_config_id=effective_app_config_id,  # v2.1: 透传！
            kb_pref_dataset_id=kb_pref_dataset_id,
        )
        
        logger.info(
            f"[Chat] 查询完成",
            extra={
                "request_id": request_id,
                "quota_exceeded": result.quota_exceeded,
                "source_count": len(result.sources),
                "answer_length": len(result.answer)
            }
        )

        # 如果是飞书/企微平台，发送消息回复给用户
        if platform in ("feishu", "wecom") and platform_user_id and result.answer:
            try:
                from apps.integration.adapters.factory import AdapterFactory
                logger.info(
                    f"[Chat] 发送回复: platform={platform}, user_id={platform_user_id}, "
                    f"is_default={app_config.get('_is_default')}"
                )
                
                # 验证适配器配置
                adapter_config = build_adapter_config(platform, app_config)
                if platform == "feishu":
                    required_fields = ["app_id", "app_secret"]
                    missing_fields = [field for field in required_fields if not adapter_config.get(field)]
                    if missing_fields:
                        logger.error(f"[Chat] 飞书适配器配置缺少必要字段: {missing_fields}")
                        return result
                
                adapter = AdapterFactory.create_adapter(
                    platform, adapter_config
                )
                if not adapter:
                    logger.error(f"[Chat] 无法创建 {platform} 平台适配器")
                    return result

                success = await adapter.send_message(
                    user_id=platform_user_id,
                    content=result.answer,
                    chat_id=body.metadata.get("chat_id"),
                    chat_type=body.metadata.get("chat_type"),
                )
                if success:
                    logger.info(f"[Chat] ✅ 消息发送成功")
                else:
                    logger.error(f"[Chat] ❌ 消息发送失败")
            except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.error(f"[Chat] ❌ 发送回复失败: {str(e)}", exc_info=True)
        elif platform in ("feishu", "wecom") and not platform_user_id:
            logger.error(f"[Chat] ❌ 无法发送消息：platform_user_id为空")

        if is_platform_webhook and platform in ("feishu", "wecom"):
            return JSONResponse(content={"success": True}, status_code=200)

        return result
        
    except HTTPException:
        raise
    
    except ValueError as ve:
        logger.error(f"[Chat] 业务异常: {ve}", extra={"request_id": request_id}, exc_info=True)
        # 避免信息泄露，返回通用错误提示
        return ChatResponse(
            success=True,
            answer="服务暂时不可用，请稍后重试。",
            sources=[],
            quota_exceeded=False
        )
    
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        error_str = str(e)
        logger.error(
            f"[Chat] 处理请求时发生未预期错误",
            extra={
                "request_id": request_id,
                "error": error_str
            },
            exc_info=True
        )
        
        # 针对常见错误提供更具体的提示
        if "user_id" in error_str:
            logger.warning("[Chat] 检测到user_id相关错误，可能是用户信息获取失败")
            answer = "抱歉，无法获取您的用户信息。请确保您已正确授权应用，或稍后再试。"
        elif "token" in error_str.lower():
            logger.warning("[Chat] 检测到token相关错误，可能是飞书授权问题")
            answer = "抱歉，系统授权失败。请联系管理员检查飞书应用配置。"
        else:
            answer = "抱歉，处理您的查询时遇到了问题。请稍后再试，或联系技术支持。"
        
        return ChatResponse(
            success=True,  # 即使出错也返回200，避免平台重试风暴
            answer=answer,
            sources=[],
            quota_exceeded=False
        )
