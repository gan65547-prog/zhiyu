"""RBAC enforcement for tenant and quota operations."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import deps
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _headers_for_roles(roles: list[str]) -> dict[str, str]:
    async def fake_user() -> dict:
        return {"username": "rbac_test", "roles": roles}

    app.dependency_overrides[deps.require_ops_user] = fake_user
    return {"Authorization": "Bearer bypass"}


def teardown_override() -> None:
    app.dependency_overrides.pop(deps.require_ops_user, None)


@pytest.mark.parametrize(
    "roles,rbac_allowed",
    [
        (["read_only_auditor"], False),
        (["quota_ops"], False),
        (["tenant_ops"], True),
        (["super_admin"], True),
    ],
)
def test_quota_update_rbac_matrix(
    client: TestClient, roles: list[str], rbac_allowed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """配额 POST 仅 tenant_ops / super_admin；通过后由网关访问上游（可能 502）。"""
    from app.services.business_gateway import BusinessGateway

    async def _ok(self, method, path, **kwargs):  # noqa: ANN001
        return {"success": True, "data": {}, "meta": {}}

    monkeypatch.setattr(BusinessGateway, "request", _ok)
    try:
        h = _headers_for_roles(roles)
        resp = client.post(
            "/api/v1/operations/tenants/t-1/quota",
            headers={**h, "X-Op-Id": "rbac-quota-001", "X-Operator": "pytest"},
            json={"quota_type": "documents", "value": 10, "reason": "rbac-test"},
        )
        if not rbac_allowed:
            assert resp.status_code == 403
            assert resp.json()["detail"]["error"]["code"] == "RBAC_FORBIDDEN"
        else:
            assert resp.status_code == 200
    finally:
        teardown_override()


def test_read_only_may_call_tenants_list(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """只读角色可访问租户列表（读路径）。"""
    from app.services.business_gateway import BusinessGateway

    async def _ok(self, method, path, **kwargs):  # noqa: ANN001
        return {"success": True, "data": [], "meta": {}}

    monkeypatch.setattr(BusinessGateway, "request", _ok)
    try:
        h = _headers_for_roles(["read_only_auditor"])
        resp = client.get("/api/v1/operations/tenants?page=1&page_size=5", headers=h)
        assert resp.status_code in {200, 502, 503}
    finally:
        teardown_override()
