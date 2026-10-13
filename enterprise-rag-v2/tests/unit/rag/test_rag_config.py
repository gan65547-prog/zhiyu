from core import rag_config


def test_deepseek_alias_selects_remote_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "real-looking-provider-key")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    rag_config._rag_config = None

    config = rag_config.get_rag_config()

    assert config.deepseek_api_key == "real-looking-provider-key"
    assert config.llm_provider == "deepseek"

    rag_config._rag_config = None
