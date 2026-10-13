from core.config import Settings


def test_nested_celery_config_uses_process_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/7")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/8")

    settings = Settings()

    assert settings.celery.broker_url.endswith("/7")
    assert settings.celery.result_backend.endswith("/8")
