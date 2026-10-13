"""
用户映射服务 - v2.1 多租户架构核心组件

职责:
  将平台用户 (飞书open_id / 企微UserId / 微信OpenID) 映射到系统内部用户

功能:
  1. 查询已有映射 (支持 app_config_id 过滤)
  2. 自动注册新用户 (AUTO_REGISTER=true)
  3. 手动绑定流程 (返回绑定码)
  4. 初始化租户资源统计
  5. 多租户路由 (通过 app_config_id 查找租户)
"""

import uuid
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from services.utils.jwt import hash_password
from core.decorators import log_exceptions
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class UserMappingService:
    """用户映射服务"""
    
    def __init__(self, db=None, redis=None, quota_service=None):
        self.db = db
        self.redis = redis
        self.quota_service = quota_service
    
    @log_exceptions(__name__)
    async def get_or_create_user(
        self,
        platform: str,
        platform_user_id: str,
        user_info: Optional[Dict[str, Any]] = None,
        auto_register: bool = True,
        app_config_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取或创建用户映射
        
        Args:
            platform: 平台标识 (feishu|wecom|wechat|qq|dingtalk)
            platform_user_id: 平台唯一用户ID
            user_info: 平台用户信息 (姓名、头像、邮箱等)
            auto_register: 是否自动注册新用户
            app_config_id: 平台应用配置ID (v2.1 多租户架构)
        
        Returns:
            {
                "system_user_id": int,       # 系统用户ID
                "tenant_id": int,             # 租户ID
                "plan": str,                  # 历史兼容字段
                "is_new_user": bool,          # 是否新创建的用户
                "bind_code": str | None       # 需要手动绑定时的验证码
            }
        """
        
        logger.info(
            f"[UserMapping] 查询用户映射",
            extra={
                "platform": platform,
                "platform_user_id": platform_user_id[:20] + "...",
                "app_config_id": app_config_id,
                "auto_register": auto_register
            }
        )
        
        # ===== Step 1: 查询已有映射 =====
        existing_mapping = await self._query_existing_mapping(platform, platform_user_id, app_config_id)
        
        if existing_mapping:
            logger.info(f"[UserMapping] 找到已有映射: user_id={existing_mapping['system_user_id']}")
            
            plan = await self._get_user_plan(existing_mapping["system_user_id"])
            
            return {
                "system_user_id": existing_mapping["system_user_id"],
                "tenant_id": existing_mapping["tenant_id"],
                "plan": plan,
                "is_new_user": False,
                "bind_code": None
            }
        
        # ===== Step 2: 无映射，决策处理方式 =====
        if not auto_register:
            logger.info("[UserMapping] 自动注册已禁用，生成绑定码")
            bind_code = self._generate_bind_code()
            await self._cache_bind_code(bind_code, platform, platform_user_id, user_info, app_config_id)
            
            return {
                "system_user_id": None,
                "tenant_id": None,
                "plan": None,
                "is_new_user": False,
                "bind_code": bind_code
            }
        
        # ===== Step 3: 自动注册新用户 =====
        logger.info("[UserMapping] 开始自动注册新用户")
        result = await self._auto_register_user(platform, platform_user_id, user_info, app_config_id)
        
        # 确保返回的字典包含必要的键
        if not isinstance(result, dict):
            raise ValueError(f"_auto_register_user 返回值必须是字典类型，实际类型: {type(result)}")
        
        if "user_id" not in result:
            raise ValueError("_auto_register_user 返回的字典必须包含 'user_id' 键")
        
        if "tenant_id" not in result:
            raise ValueError("_auto_register_user 返回的字典必须包含 'tenant_id' 键")
        
        return {
            "system_user_id": result["user_id"],
            "tenant_id": result["tenant_id"],
            "plan": "unlimited",
            "is_new_user": True,
            "bind_code": None
        }
    
    @log_exceptions(__name__)
    async def _query_existing_mapping(self, platform: str, platform_user_id: str, app_config_id: Optional[str] = None) -> Optional[Dict]:
        """查询已有的用户映射记录"""
        if not self.db:
            logger.warning("数据库连接未初始化，无法查询映射")
            return None

        if app_config_id:
            query = """
                SELECT 
                    id, system_user_id, tenant_id, display_name, created_at
                FROM platform_users 
                WHERE platform = :platform AND platform_user_id = :platform_user_id AND app_config_id = :app_config_id
                LIMIT 1
            """
            row = await self.db.fetch_one(query, {
                "platform": platform,
                "platform_user_id": platform_user_id,
                "app_config_id": app_config_id
            })
        else:
            # 兼容旧数据 (app_config_id 为 NULL)
            query = """
                SELECT 
                    id, system_user_id, tenant_id, display_name, created_at
                FROM platform_users 
                WHERE platform = :platform AND platform_user_id = :platform_user_id AND app_config_id IS NULL
                LIMIT 1
            """
            row = await self.db.fetch_one(query, {
                "platform": platform,
                "platform_user_id": platform_user_id
            })
        
        if row:
            return dict(row)
        return None
    
    async def _get_user_plan(self, system_user_id: int) -> str:
        """兼容集成响应中的历史 plan 字段；开源自托管版不做套餐分级。"""
        return "unlimited"
    
    def _generate_bind_code(self) -> str:
        """生成6位随机绑定码"""
        import random
        import string
        
        chars = string.ascii_uppercase + string.digits
        code = ''.join(random.choices(chars, k=6))
        
        logger.info(f"[UserMapping] 生成绑定码: {code}")
        return code
    
    async def _cache_bind_code(
        self, 
        bind_code: str, 
        platform: str, 
        platform_user_id: str,
        user_info: Optional[Dict] = None,
        app_config_id: Optional[str] = None
    ):
        """缓存绑定码（5分钟有效期）"""
        if not self.redis:
            logger.warning("Redis未初始化，无法缓存绑定码")
            return
        
        cache_key = f"integration:bind:{bind_code}"
        cache_data = {
            "platform": platform,
            "platform_user_id": platform_user_id,
            "user_info": user_info or {},
            "app_config_id": app_config_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            import json
            await self.redis.setex(
                cache_key,
                300,  # 5分钟过期
                json.dumps(cache_data)
            )
            logger.debug(f"[UserMapping] 绑定码已缓存: key={cache_key}")
            
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"缓存绑定码失败: {e}")
    
    @log_exceptions(__name__)
    async def _auto_register_user(
        self,
        platform: str,
        platform_user_id: str,
        user_info: Optional[Dict],
        app_config_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        自动注册新用户并创建映射
        
        Returns:
            {"user_id": int, "tenant_id": int}
        """
        if not self.db:
            raise RuntimeError("数据库连接未初始化")
        
        # 生成用户名 (基于平台+平台用户ID前缀)
        username = f"{platform}_{platform_user_id[:8]}_{uuid.uuid4().hex[:6]}"
        display_name = user_info.get("name", username) if user_info else username
        email = user_info.get("email") if user_info else f"{username}@example.com"
        
        # 1. 获取租户ID (优先从 app_config_id 查询)
        tenant_id = await self._get_tenant_by_app_config(app_config_id)
        if not tenant_id:
            tenant_id = await self._get_or_create_tenant(display_name)
        
        # 2. 创建系统用户
        user_query = """
            INSERT INTO users (
                id, tenant_id, username, email, hashed_password, display_name, is_active, is_superuser, source, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :username, :email, :hashed_password, :display_name, true, false, :source, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id
        """
        user_id = str(uuid.uuid4())
        # 集成用户仅用于系统映射，使用随机高熵口令哈希，避免固定弱凭据。
        generated_password = secrets.token_urlsafe(64)
        hashed_password = hash_password(generated_password)
        
        user_result = await self.db.fetch_one(user_query, {
            "id": user_id,
            "tenant_id": tenant_id,
            "username": username,
            "email": email,
            "hashed_password": hashed_password,
            "display_name": display_name,
            "source": f"integration_{platform}"
        })
        
        system_user_id = user_result["id"]
        logger.info(f"[UserMapping] 创建系统用户成功: id={system_user_id}, name={display_name}")
        
        # 3. 检查是否已存在平台映射记录
        existing_query = """
            SELECT id, system_user_id FROM platform_users
            WHERE platform = :platform AND platform_user_id = :platform_user_id
        """
        
        # 根据 db 对象类型选择合适的查询方式
        if hasattr(self.db, 'fetch_one'):
            existing_record = await self.db.fetch_one(existing_query, {
                "platform": platform,
                "platform_user_id": platform_user_id
            })
        elif hasattr(self.db, 'execute'):
            query_result = await self.db.execute(existing_query, {
                "platform": platform,
                "platform_user_id": platform_user_id
            })
            existing_record = await query_result.fetch_one()
        else:
            existing_record = None
        
        if existing_record:
            logger.info(f"[UserMapping] 平台映射已存在，直接返回: platform={platform}, platform_user_id={platform_user_id}, system_user_id={existing_record['system_user_id']}")
            # 从平台映射记录中查询租户ID
            tenant_query = """
                SELECT tenant_id FROM platform_users
                WHERE id = :id
            """
            tenant_result = await self.db.fetch_one(tenant_query, {"id": existing_record["id"]})
            tenant_id = tenant_result["tenant_id"] if tenant_result else None
            return {
                "user_id": existing_record["system_user_id"],
                "tenant_id": tenant_id
            }
        
        # 4. 创建平台映射记录
        mapping_query = """
            INSERT INTO platform_users (
                platform, platform_user_id, system_user_id, tenant_id, app_config_id,
                display_name, avatar_url, email, metadata, created_at, updated_at
            ) VALUES (
                :platform, :platform_user_id, :system_user_id, :tenant_id, :app_config_id,
                :display_name, :avatar_url, :email, :metadata, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """
        # 将metadata转换为JSON字符串
        import json
        metadata_json = json.dumps(user_info or {})
        
        await self.db.execute(mapping_query, {
            "platform": platform,
            "platform_user_id": platform_user_id,
            "system_user_id": system_user_id,
            "tenant_id": tenant_id,
            "app_config_id": app_config_id,
            "display_name": display_name,
            "avatar_url": user_info.get("avatar_url") if user_info else None,
            "email": email,
            "metadata": metadata_json
        })
        
        logger.info(f"[UserMapping] 创建平台映射成功: platform={platform}, tenant={tenant_id}, app_config={app_config_id}")
        
        # 4. 初始化租户资源统计
        if self.quota_service:
            try:
                init_result = await self.quota_service.init_free_tier(
                    tenant_id=str(tenant_id),
                    user_email=email
                )
                logger.info(f"[UserMapping] 租户资源统计初始化成功: {init_result.get('message')}")
                
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[UserMapping] 配额初始化失败(不影响注册): {e}")
        else:
            logger.warning("[UserMapping] QuotaService未初始化，跳过配额初始化")
        
        return {
            "user_id": system_user_id,
            "tenant_id": tenant_id
        }
    
    async def _get_tenant_by_app_config(self, app_config_id: Optional[str]) -> Optional[str]:
        """通过 app_config_id 获取租户ID"""
        if not self.db or not app_config_id:
            return None
        
        try:
            query = """
                SELECT tenant_id FROM platform_app_configs 
                WHERE id = :app_config_id AND is_active = true
                LIMIT 1
            """
            row = await self.db.fetch_one(query, {"app_config_id": app_config_id})
            
            if row:
                logger.info(f"[UserMapping] 通过 app_config 找到租户: {row['tenant_id']}")
                return row["tenant_id"]
            
            logger.warning(f"[UserMapping] app_config_id={app_config_id} 未找到对应租户")
            return None
            
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"[UserMapping] 通过 app_config 获取租户失败: {e}", exc_info=True)
            return None
    
    @log_exceptions(__name__)
    async def _get_or_create_tenant(self, display_name: str) -> str:
        """获取或创建默认租户"""
        # 尝试查询默认租户
        query = """
            SELECT id FROM tenants 
            WHERE name = '默认租户' OR plan = 'FREE'
            LIMIT 1
        """
        tenant_result = await self.db.fetch_one(query)
        
        if tenant_result:
            return tenant_result["id"]
        
        # 如果没有默认租户，创建一个
        tenant_id = str(uuid.uuid4())
        create_query = """
            INSERT INTO tenants (
                id, name, contact_email, plan, status, created_at, updated_at
            ) VALUES (
                :id, :name, :contact_email, 'FREE', 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id
        """
        new_tenant = await self.db.fetch_one(create_query, {
            "id": tenant_id,
            "name": f"{display_name}的团队" if display_name else "默认租户",
            "contact_email": "default@example.com"
        })
        
        logger.info(f"[UserMapping] 创建新租户: id={new_tenant['id']}")
        return new_tenant["id"]
