"""
JWT工具类

提供JWT令牌的创建和验证功能
"""

from datetime import timezone, datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from jose import jwt, JWTError

import bcrypt

from core.config import get_settings


settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def hash_password(password: str) -> str:
    """哈希密码"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建访问令牌"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.auth.access_token_expire_minutes)

    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc)
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建刷新令牌"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.auth.refresh_token_expire_days)

    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc)
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """解码令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret,
            algorithms=[settings.auth.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


def validate_password_strength(password: str) -> tuple[bool, str]:
    """验证密码强度"""
    if len(password) < 8:
        return False, "密码长度至少8个字符"

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)

    if not (has_upper and has_lower and has_digit):
        return False, "密码必须包含大小写字母和数字"

    return True, ""


class TokenPayload:
    """令牌载荷"""

    def __init__(self, payload: Dict[str, Any]):
        self.sub: str = payload.get("sub", "")
        self.exp: datetime = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
        self.type: str = payload.get("type", "access")
        self.iat: datetime = datetime.fromtimestamp(payload.get("iat", 0), tz=timezone.utc)
        self.tenant_id: Optional[str] = payload.get("tenant_id")
        self.workspace_id: Optional[str] = payload.get("workspace_id")
        self.username: Optional[str] = payload.get("username")
        self.email: Optional[str] = payload.get("email")
        self.is_superuser: bool = payload.get("is_superuser", False)

    @property
    def user_id(self) -> UUID:
        """获取用户ID"""
        return UUID(self.sub)

    @property
    def is_expired(self) -> bool:
        """检查是否过期"""
        return datetime.now(timezone.utc) > self.exp
