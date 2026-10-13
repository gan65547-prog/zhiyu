"""
/internal/admin 鉴权依赖 get_internal_admin_identity 的安全与必填头回归（不拉起完整 ASGI/Redis）。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.deps import get_internal_admin_identity


def _request(method: str = "GET"):
    req = MagicMock()
    req.method = method
    req.headers = MagicMock()
    req.headers.get = MagicMock(return_value=None)
    return req


@pytest.mark.asyncio
async def test_missing_request_id():
    with patch("api.deps.get_client_ip", new_callable=AsyncMock, return_value="127.0.0.1"):
        with pytest.raises(HTTPException) as ei:
            await get_internal_admin_identity(
                _request("GET"),
                x_request_id=None,
                x_internal_api_key="k",
                x_op_id=None,
                x_operator=None,
            )
    assert ei.value.status_code == 400
    assert ei.value.detail == "MISSING_REQUEST_ID"


@pytest.mark.asyncio
async def test_invalid_internal_api_key(monkeypatch):
    from core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s.security, "internal_api_keys", ["good-key"])
    monkeypatch.setattr(s.security, "internal_ip_whitelist", ["*"])

    with patch("api.deps.get_client_ip", new_callable=AsyncMock, return_value="127.0.0.1"):
        with pytest.raises(HTTPException) as ei:
            await get_internal_admin_identity(
                _request("GET"),
                x_request_id="rid-1",
                x_internal_api_key="wrong-key",
                x_op_id=None,
                x_operator=None,
            )
    assert ei.value.status_code == 401
    assert ei.value.detail == "INVALID_INTERNAL_API_KEY"


@pytest.mark.asyncio
async def test_ip_not_in_whitelist(monkeypatch):
    from core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s.security, "internal_api_keys", ["good-key"])
    monkeypatch.setattr(s.security, "internal_ip_whitelist", ["10.0.0.1"])

    with patch("api.deps.get_client_ip", new_callable=AsyncMock, return_value="192.168.1.1"):
        with pytest.raises(HTTPException) as ei:
            await get_internal_admin_identity(
                _request("GET"),
                x_request_id="rid-1",
                x_internal_api_key="good-key",
                x_op_id=None,
                x_operator=None,
            )
    assert ei.value.status_code == 403
    assert ei.value.detail == "IP_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_post_missing_operation_id(monkeypatch):
    from core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s.security, "internal_api_keys", ["good-key"])
    monkeypatch.setattr(s.security, "internal_ip_whitelist", ["*"])

    with patch("api.deps.get_client_ip", new_callable=AsyncMock, return_value="127.0.0.1"):
        with pytest.raises(HTTPException) as ei:
            await get_internal_admin_identity(
                _request("POST"),
                x_request_id="rid-1",
                x_internal_api_key="good-key",
                x_op_id=None,
                x_operator="ops",
            )
    assert ei.value.status_code == 400
    assert ei.value.detail == "MISSING_OPERATION_ID"


@pytest.mark.asyncio
async def test_post_missing_operator(monkeypatch):
    from core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s.security, "internal_api_keys", ["good-key"])
    monkeypatch.setattr(s.security, "internal_ip_whitelist", ["*"])

    with patch("api.deps.get_client_ip", new_callable=AsyncMock, return_value="127.0.0.1"):
        with pytest.raises(HTTPException) as ei:
            await get_internal_admin_identity(
                _request("POST"),
                x_request_id="rid-1",
                x_internal_api_key="good-key",
                x_op_id="op-123456",
                x_operator=None,
            )
    assert ei.value.status_code == 400
    assert ei.value.detail == "MISSING_OPERATOR"


@pytest.mark.asyncio
async def test_get_success_returns_identity(monkeypatch):
    from core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s.security, "internal_api_keys", ["good-key"])
    monkeypatch.setattr(s.security, "internal_ip_whitelist", ["*"])

    with patch("api.deps.get_client_ip", new_callable=AsyncMock, return_value="127.0.0.1"):
        out = await get_internal_admin_identity(
            _request("GET"),
            x_request_id="rid-1",
            x_internal_api_key="good-key",
            x_op_id=None,
            x_operator=None,
        )
    assert out["request_id"] == "rid-1"
    assert out["operation_id"] is None
    assert out["client_ip"] == "127.0.0.1"
    assert out["method"] == "GET"
