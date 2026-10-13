from fastapi.testclient import TestClient
from app.config import get_settings

from app.main import app


def _login_headers(client: TestClient) -> dict:
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": get_settings().bootstrap_admin_password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_users_requires_auth():
    client = TestClient(app)
    response = client.get("/api/v1/users")
    assert response.status_code == 401


def test_user_crud_and_role_assign():
    client = TestClient(app)
    headers = _login_headers(client)

    create_resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "ops1", "password": "pass123456", "roles": ["tenant_ops"]},
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["data"]["username"] == "ops1"

    role_resp = client.post("/api/v1/users/ops1/roles", headers=headers, json={"roles": ["quota_ops"]})
    assert role_resp.status_code == 200
    assert role_resp.json()["data"]["roles"] == ["quota_ops"]

    delete_resp = client.delete("/api/v1/users/ops1", headers=headers)
    assert delete_resp.status_code == 200
