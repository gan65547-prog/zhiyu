"""
统一错误响应格式

提供一致的API错误响应格式和异常处理
"""

from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError
import traceback

from infrastructure.logging.logger import get_logger


logger = get_logger("api.errors")


class ErrorCode:
    """错误码定义"""

    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    NOT_FOUND = "not_found"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    BAD_REQUEST = "bad_request"
    CONFLICT = "conflict"
    SERVICE_UNAVAILABLE = "service_unavailable"
    QUOTA_EXCEEDED = "quota_exceeded"


class ErrorResponse:
    """统一错误响应格式"""

    def __init__(
        self,
        error: str,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        timestamp: Optional[str] = None
    ):
        self.error = error
        self.message = message
        self.code = code or error
        self.details = details
        self.request_id = request_id
        self.timestamp = timestamp or self._get_timestamp()

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        if self.request_id:
            result["request_id"] = self.request_id
        result["timestamp"] = self.timestamp
        return result


class APIException(HTTPException):
    """API异常基类"""

    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error": error,
                "message": message,
                "code": code or error,
                "details": details
            },
            headers=headers
        )


class ValidationException(APIException):
    """验证异常"""

    def __init__(
        self,
        message: str = "请求参数验证失败",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=422,
            error=ErrorCode.VALIDATION_ERROR,
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            details=details
        )


class AuthenticationException(APIException):
    """认证异常"""

    def __init__(
        self,
        message: str = "认证失败，请重新登录",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=401,
            error=ErrorCode.AUTHENTICATION_ERROR,
            message=message,
            code=ErrorCode.AUTHENTICATION_ERROR,
            details=details,
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationException(APIException):
    """授权异常"""

    def __init__(
        self,
        message: str = "权限不足，无法执行此操作",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=403,
            error=ErrorCode.AUTHORIZATION_ERROR,
            message=message,
            code=ErrorCode.AUTHORIZATION_ERROR,
            details=details
        )


class NotFoundException(APIException):
    """资源不存在异常"""

    def __init__(
        self,
        message: str = "请求的资源不存在",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=404,
            error=ErrorCode.NOT_FOUND,
            message=message,
            code=ErrorCode.NOT_FOUND,
            details=details
        )


class RateLimitException(APIException):
    """限流异常"""

    def __init__(
        self,
        message: str = "请求过于频繁，请稍后再试",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        super().__init__(
            status_code=429,
            error=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details=details,
            headers=headers
        )


class BadRequestException(APIException):
    """错误请求异常"""

    def __init__(
        self,
        message: str = "请求格式错误",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=400,
            error=ErrorCode.BAD_REQUEST,
            message=message,
            code=ErrorCode.BAD_REQUEST,
            details=details
        )


class ConflictException(APIException):
    """资源冲突异常"""

    def __init__(
        self,
        message: str = "资源冲突",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=409,
            error=ErrorCode.CONFLICT,
            message=message,
            code=ErrorCode.CONFLICT,
            details=details
        )


class QuotaExceededException(APIException):
    """配额超限异常"""

    def __init__(
        self,
        message: str = "配额超限",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=402,
            error=ErrorCode.QUOTA_EXCEEDED,
            message=message,
            code=ErrorCode.QUOTA_EXCEEDED,
            details=details
        )


class InternalServerException(APIException):
    """服务器内部异常"""

    def __init__(
        self,
        message: str = "服务器内部错误",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=500,
            error=ErrorCode.INTERNAL_SERVER_ERROR,
            message=message,
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            details=details
        )


class ServiceUnavailableException(APIException):
    """服务不可用异常"""

    def __init__(
        self,
        message: str = "服务暂时不可用",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        super().__init__(
            status_code=503,
            error=ErrorCode.SERVICE_UNAVAILABLE,
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            details=details,
            headers=headers
        )


class ErrorHandlerMiddleware:
    """错误处理中间件工具类"""

    @staticmethod
    def get_request_id(request: Request) -> Optional[str]:
        """获取请求ID"""
        return request.headers.get("X-Request-ID")

    @staticmethod
    def format_validation_error(exc: RequestValidationError) -> Dict[str, Any]:
        """格式化验证错误"""
        errors = []
        for error in exc.errors():
            loc = ".".join(str(l) for l in error["loc"])
            errors.append({
                "field": loc,
                "message": error["msg"],
                "type": error["type"]
            })
        return {
            "error": ErrorCode.VALIDATION_ERROR,
            "message": "请求参数验证失败",
            "details": {"errors": errors}
        }

    @staticmethod
    def format_generic_error(
        exc: Exception,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """格式化通用错误"""
        return {
            "error": ErrorCode.INTERNAL_SERVER_ERROR,
            "message": "服务器内部错误",
            "details": {
                "type": type(exc).__name__,
                "message": str(exc)
            },
            "request_id": request_id
        }


def create_error_response(
    error: str,
    message: str,
    code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """创建错误响应"""
    error_response = ErrorResponse(
        error=error,
        message=message,
        code=code,
        details=details,
        request_id=request_id
    )
    return JSONResponse(
        status_code=500,
        content=error_response.to_dict()
    )


def create_validation_error_response(
    errors: List[Dict[str, Any]],
    request_id: Optional[str] = None
) -> JSONResponse:
    """创建验证错误响应"""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": ErrorCode.VALIDATION_ERROR,
                "message": "请求参数验证失败",
                "details": {"errors": errors}
            },
            "request_id": request_id,
            "timestamp": ErrorResponse()._get_timestamp()
        }
    )


def create_not_found_response(
    resource: str,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """创建资源不存在响应"""
    message = f"{resource}不存在"
    if resource_id:
        message = f"{resource} ({resource_id}) 不存在"
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": {
                "code": ErrorCode.NOT_FOUND,
                "message": message
            },
            "request_id": request_id,
            "timestamp": ErrorResponse()._get_timestamp()
        }
    )


def create_conflict_response(
    message: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> JSONResponse:
    """创建资源冲突响应"""
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "error": {
                "code": ErrorCode.CONFLICT,
                "message": message,
                "details": details
            },
            "request_id": request_id,
            "timestamp": ErrorResponse()._get_timestamp()
        }
    )
