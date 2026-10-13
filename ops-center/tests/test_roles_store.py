from app.auth.user_store import SqliteOpsUserStore


def test_list_roles_fallback_without_db():
    store = SqliteOpsUserStore(conn=None)
    rows = store.list_roles()
    codes = {r["code"] for r in rows}
    assert codes == {"super_admin", "tenant_ops", "read_only_auditor"}
    for r in rows:
        assert "name" in r and r["name"]
