from pathlib import Path


def test_011_audit_logs_migration_file_exists():
    root = Path(__file__).resolve().parents[2]
    p = root / "alembic" / "versions" / "011_audit_logs_align_orm.py"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "resource_type" in text
    assert "011_audit_logs_align_orm" in text
