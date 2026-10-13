from api.middleware.internal_admin_metrics import normalize_internal_admin_route


def test_normalize_replaces_uuid():
    path = "/internal/admin/tenants/550e8400-e29b-41d4-a716-446655440000/usage"
    assert normalize_internal_admin_route(path) == "/internal/admin/tenants/{id}/usage"
