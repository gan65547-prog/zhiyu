from fastapi.testclient import TestClient
from app.config import get_settings

from app.main import app


def test_login_success():
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": get_settings().bootstrap_admin_password},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["token_type"] == "Bearer"
    assert payload["data"]["access_token"]


def test_login_wrong_password():
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
    assert response.status_code == 401


def test_auth_me_requires_authorization():
    client = TestClient(app)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
