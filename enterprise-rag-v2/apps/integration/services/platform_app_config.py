import json
from typing import Optional, Dict, Any
from urllib.parse import parse_qs

from infrastructure.logging.logger import get_logger

from cryptography.fernet import Fernet, InvalidToken

logger = get_logger(__name__)


def _mask_token(token: Optional[str]) -> str:
    if not token:
        return "None"
    return f"{str(token)[:8]}***"


class PlatformAppConfigService:
    """
    平台应用配置服务

    职责:
      - 根据 (platform, app_id) 查找租户配置
      - 加密/解密凭证（Fernet, lazy init）
      - Redis 缓存（TTL 5min 元数据 / 60s 凭证）
      - 降级逻辑: 未匹配时返回默认配置
      - app_id 反查: 通过 verification_token 或 URL path 识别来源
    """

    def __init__(self, db, redis=None):
        self.db = db
        self.redis = redis
        self._cipher = None

    def _get_cipher(self) -> Fernet:
        if self._cipher is not None:
            return self._cipher

        import os
        # 加载 .env 文件
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # 尝试直接读取 .env 文件
            if os.path.exists(".env"):
                with open(".env", "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ENCRYPTION_KEY="):
                            key = line.split("=", 1)[1].strip()
                            break
        
        if not key:
            raise RuntimeError(
                'ENCRYPTION_KEY 未设置。'
                '生成方式: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        try:
            self._cipher = Fernet(key.encode())
            return self._cipher
        except (ValueError, TypeError) as e:
            raise RuntimeError(f"ENCRYPTION_KEY 格式无效: {e}")

    def _encrypt(self, plaintext: str) -> str:
        return self._get_cipher().encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        try:
            return self._get_cipher().decrypt(ciphertext.encode()).decode()
        except InvalidToken as e:
            logger.error(f"解密失败（可能 ENCRYPTION_KEY 已变更）: {e}")
            raise ValueError("无法解密凭证")

    async def get_config_by_app_id(
        self,
        platform: str,
        app_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据 (platform, app_id) 获取配置（含解密后的凭证）"""
        cache_key = f"pac:{platform}:{app_id}"

        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    if data.get("_cred"):
                        data["credentials"] = json.loads(self._decrypt(data.pop("_cred")))
                    return data
            except (json.JSONDecodeError, ValueError, TypeError, AttributeError, RuntimeError) as e:
                logger.warning(f"Redis 读取失败: {e}")

        try:
            query = """
                SELECT id, tenant_id, platform, app_id,
                       encrypted_credentials, verification_token,
                       encrypt_key, config, is_active
                FROM platform_app_configs
                WHERE platform = :platform AND app_id = :app_id AND is_active = TRUE
                LIMIT 1
            """
            
            # 检查 db 对象类型，支持不同的数据库连接
            if hasattr(self.db, 'fetch_one'):
                # 对于 aiosqlite 等库
                row = await self.db.fetch_one(query, {"platform": platform, "app_id": app_id})
            elif hasattr(self.db, 'execute'):
                # 对于 databases 库
                query_result = await self.db.execute(query, {"platform": platform, "app_id": app_id})
                row = await query_result.fetch_one()
            else:
                # 其他情况
                row = None
            
            if row:
                # 转换为字典
                if hasattr(row, '_asdict'):
                    row = row._asdict()
                elif isinstance(row, tuple):
                    # 对于 databases 库的返回，使用列名映射
                    columns = ['id', 'tenant_id', 'platform', 'app_id', 'encrypted_credentials', 'verification_token', 'encrypt_key', 'config', 'is_active']
                    row = dict(zip(columns, row))
            if not row:
                return None

            result = dict(row)  # 确保转换为字典
            encrypted_credentials = result.get("encrypted_credentials")
            if not encrypted_credentials:
                return None
            credentials_json = self._decrypt(encrypted_credentials)
            result["credentials"] = json.loads(credentials_json)
            # 删除加密的凭证，只返回解密后的
            if "encrypted_credentials" in result:
                del result["encrypted_credentials"]

            if self.redis:
                cred_encrypted_for_cache = self._encrypt(credentials_json)
                safe_cache = {**result, "_cred": cred_encrypted_for_cache}
                del safe_cache["credentials"]
                try:
                    await self.redis.setex(cache_key, 300, json.dumps(safe_cache, default=str))
                except (TypeError, ValueError, AttributeError):
                    pass

            return result

        except (json.JSONDecodeError, ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.error(f"查询配置失败: platform={platform}, app_id={app_id}, error={e}", exc_info=True)
            return None

    async def resolve_app_id(
        self,
        platform: str,
        request,
        body_data: Optional[Dict] = None
    ) -> Optional[str]:
        """
        多级降级的 app_id 识别策略

        优先级:
          1. 自定义请求头 (X-Lark-App-Id / X-App-Id)
          2. 请求体中的标识 (企微 AgentID)
          3. URL query 参数 (?app=cli_xxx)
          4. verification_token 反查（飞书 challenge token 匹配）
          5. None → 触发默认配置降级
        """

        detected = None

        header_candidates = {
            "feishu": ["X-Lark-App-Id", "x-lark-app-id"],
            "wecom": [],
            "dingtalk": ["X-Ai-CorpId"],
        }
        for header in header_candidates.get(platform, []):
            val = request.headers.get(header)
            if val:
                detected = val
                logger.debug(f"[AppID] 从请求头识别: {header}={val}")
                break

        if not detected and body_data:
            if platform == "wecom" and body_data.get("AgentID"):
                detected = str(body_data["AgentID"])
                logger.debug(f"[AppID] 从 AgentID 识别: {detected}")

        if not detected:
            url_str = str(request.url)
            query_params = parse_qs(url_str.split("?")[-1]) if "?" in url_str else {}
            app_from_query = query_params.get("app", [None])[0]
            if app_from_query:
                detected = app_from_query
                logger.debug(f"[AppID] 从 URL query 识别: ?app={detected}")

        logger.info(f"[AppID] 开始解析: platform={platform}, body_data_keys={list(body_data.keys()) if body_data else None}, detected={detected}, self.db={self.db}")
        
        if not detected and platform == "feishu" and body_data and self.db:
            # 飞书消息的 token 在 header 中
            header = body_data.get("header", {})
            token = header.get("token") or body_data.get("token") or body_data.get("challenge")
            logger.info(f"[AppID] 从 body 获取的 token: {_mask_token(token)}")
            if token:
                try:
                    query = """
                        SELECT app_id FROM platform_app_configs
                        WHERE platform = 'feishu'
                          AND verification_token = :token
                          AND is_active = TRUE
                        LIMIT 1
                    """
                    logger.info(f"[AppID] 执行 token 反查: token={_mask_token(token)}")
                    # 根据 db 对象类型选择合适的查询方式
                    if hasattr(self.db, 'fetch_one'):
                        row = await self.db.fetch_one(query, {"token": token})
                    elif hasattr(self.db, 'execute'):
                        query_result = await self.db.execute(query, {"token": token})
                        row = await query_result.fetch_one()
                    else:
                        row = None
                        logger.warning(f"[AppID] db 对象没有 fetch_one 或 execute 方法")
                    
                    logger.info(f"[AppID] token 反查结果: {row}")
                    if row:
                        detected = row["app_id"] if hasattr(row, '__getitem__') else row[0]
                        logger.info(f"[AppID] 从 verification_token 反查识别: {detected}")
                except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                    logger.warning(f"[AppID] token 反查失败: {e}", exc_info=True)

        return detected

    async def get_default_config(self, platform: str) -> Dict[str, Any]:
        """默认降级配置（从环境变量读取）"""
        import os
        from apps.integration.config import settings

        if platform == "feishu":
            return {
                "tenant_id": settings.default_tenant_id,
                "platform": "feishu",
                "app_id": settings.feishu.app_id or os.getenv("FEISHU_APP_ID", ""),
                "credentials": {
                    "app_secret": settings.feishu.app_secret or os.getenv("FEISHU_APP_SECRET", "")
                },
                "verification_token": settings.feishu.verification_token,
                "encrypt_key": settings.feishu.encrypt_key,
                "config": {},
                "_is_default": True
            }

        elif platform == "wecom":
            return {
                "tenant_id": settings.default_tenant_id,
                "platform": "wecom",
                "app_id": settings.wecom.corp_id or os.getenv("WECOM_CORP_ID", ""),
                "credentials": {
                    "corp_secret": settings.wecom.agent_secret or os.getenv("WECOM_AGENT_SECRET", ""),
                    "agent_id": str(settings.wecom.agent_id or os.getenv("WECOM_AGENT_ID", "1000001"))
                },
                "verification_token": settings.wecom.token,
                "encrypt_key": settings.wecom.encoding_aes_key,
                "config": {},
                "_is_default": True
            }

        elif platform == "dingtalk":
            return {
                "tenant_id": settings.default_tenant_id,
                "platform": "dingtalk",
                "app_id": os.getenv("DINGTALK_APP_ID", ""),
                "credentials": {"app_secret": os.getenv("DINGTALK_APP_SECRET", "")},
                "verification_token": None,
                "encrypt_key": None,
                "config": {},
                "_is_default": True
            }

        return {
            "tenant_id": settings.default_tenant_id,
            "platform": platform,
            "app_id": "",
            "credentials": {},
            "config": {},
            "_is_default": True
        }

    async def create_config(self, tenant_id, platform, app_id, credentials,
                            display_name=None, verification_token=None,
                            encrypt_key=None, config=None) -> Dict[str, Any]:
        encrypted = self._encrypt(json.dumps(credentials))
        import uuid
        config_id = str(uuid.uuid4())
        query = """
            INSERT INTO platform_app_configs (
                id, tenant_id, platform, app_id, encrypted_credentials,
                display_name, verification_token, encrypt_key, config, is_active
            ) VALUES (:id,:tenant_id,:platform,:app_id,:encrypted_credentials,
                      :display_name,:verification_token,:encrypt_key,
                      :config::jsonb, TRUE)
            RETURNING id
        """
        row = await self.db.fetch_one(query, {
            "id": config_id,
            "tenant_id": tenant_id,
            "platform": platform,
            "app_id": app_id,
            "encrypted_credentials": encrypted,
            "display_name": display_name,
            "verification_token": verification_token,
            "encrypt_key": encrypt_key,
            "config": json.dumps(config or {})
        })
        logger.info(f"[PlatformAppConfig] 创建成功: platform={platform}, app_id={app_id}, id={row['id']}")
        return {"id": row["id"]}

    async def update_config(self, config_id, **kwargs) -> bool:
        if "credentials" in kwargs:
            kwargs["encrypted_credentials"] = self._encrypt(json.dumps(kwargs.pop("credentials")))

        set_clauses = []
        params = {"id": config_id}
        for k, v in kwargs.items():
            if k in ("encrypted_credentials", "display_name", "verification_token",
                       "encrypt_key", "config", "is_active"):
                set_clauses.append(f"{k} = :{k}")
                params[k] = json.dumps(v) if k == "config" else v

        if not set_clauses:
            return False

        q = f"""
            UPDATE platform_app_configs
            SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """
        r = await self.db.execute(q, params)
        return r > 0


def build_adapter_config(platform: str, app_config: Dict[str, Any]) -> Dict[str, Any]:
    """将通用格式转换为 AdapterFactory 所需格式"""
    creds = app_config.get("credentials", {})
    if platform == "feishu":
        return {
            "app_id": app_config.get("app_id", ""),
            "app_secret": creds.get("app_secret", ""),
            "verification_token": app_config.get("verification_token"),
            "encrypt_key": app_config.get("encrypt_key")
        }
    elif platform == "wecom":
        return {
            "corp_id": app_config.get("app_id", ""),
            "agent_id": creds.get("agent_id", "1000001"),
            "agent_secret": creds.get("corp_secret", ""),
            "token": app_config.get("verification_token"),
            "encoding_aes_key": app_config.get("encrypt_key")
        }
    elif platform == "dingtalk":
        return {
            "app_id": app_config.get("app_id", ""),
            "app_secret": creds.get("app_secret", "")
        }
    return {}
