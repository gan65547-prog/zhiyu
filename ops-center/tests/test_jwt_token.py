from app.auth.token_service import create_access_token, verify_access_token


def test_jwt_create_and_verify_roundtrip():
    token = create_access_token("admin_user", ["super_admin", "tenant_ops"])
    assert token.count(".") == 2
    payload = verify_access_token(token)
    assert payload["sub"] == "admin_user"
    assert payload["roles"] == ["super_admin", "tenant_ops"]
    assert "exp" in payload and "iat" in payload
