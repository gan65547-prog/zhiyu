from fastapi.testclient import TestClient
from app.config import get_settings

from app.main import app
from app.services.business_gateway import BusinessGateway


def _login_headers(client: TestClient) -> dict:
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": get_settings().bootstrap_admin_password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_removed_sales_endpoints_are_not_registered():
    client = TestClient(app)
    headers = _login_headers(client)
    responses = [
        client.post(
            "/api/v1/operations/tenants/t1/plan/upgrade",
            headers=headers,
            json={"target_plan": "pro"},
        ),
        client.post(
            "/api/v1/operations/tenants/t1/plan/manual-request",
            headers=headers,
            json={"target_plan": "pro"},
        ),
        client.post(
            "/api/v1/operations/tenants/t1/plan/redeem",
            headers=headers,
            json={"redeem_code": "ABC123"},
        ),
    ]
    assert [response.status_code for response in responses] == [404, 404, 404]


def test_cache_invalidate_requires_write_headers():
    client = TestClient(app)
    response = client.post(
        "/api/v1/operations/cache/invalidate",
        headers=_login_headers(client),
        json={"scopes": ["quota_overrides"]},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "MISSING_X_OP_ID"


def test_health_upstream_endpoint_exists():
    client = TestClient(app)
    response = client.get("/api/v1/operations/health/upstream", headers=_login_headers(client))
    # 上游可达性取决于本地环境，这里只验证路由存在且返回结构化状态
    assert response.status_code in {200, 502, 503}
    payload = response.json()
    if "status" in payload:
        assert payload["status"] in {"ok", "degraded", "down"}
    else:
        # 如果由 HTTPException(detail=...) 返回，结构在 detail 中
        assert "detail" in payload


def test_operation_detail_proxy_route():
    async def _mock_request(self, method, path, **kwargs):  # noqa: ANN001
        return {"success": True, "data": {"operation_id": "op_1"}}

    original = BusinessGateway.request
    BusinessGateway.request = _mock_request
    try:
        client = TestClient(app)
        response = client.get("/api/v1/operations/op_1", headers=_login_headers(client))
        assert response.status_code == 200
        assert response.json()["success"] is True
    finally:
        BusinessGateway.request = original


def test_operation_tasks_proxy_route():
    async def _mock_request(self, method, path, **kwargs):  # noqa: ANN001
        return {"success": True, "data": [{"task_id": "task_1"}]}

    original = BusinessGateway.request
    BusinessGateway.request = _mock_request
    try:
        client = TestClient(app)
        response = client.get("/api/v1/operations/op_1/tasks", headers=_login_headers(client))
        assert response.status_code == 200
        assert response.json()["success"] is True
    finally:
        BusinessGateway.request = original
