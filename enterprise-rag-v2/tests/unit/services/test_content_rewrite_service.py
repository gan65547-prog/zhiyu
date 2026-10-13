import pytest
from unittest.mock import AsyncMock

from services.impl import content_rewrite_service
from services.impl.content_rewrite_service import rewrite_for_platform, rewrite_with_model


@pytest.mark.parametrize("platform, marker", [("x", "标题"), ("wechat", "欢迎转发"), ("zhihu", "你怎么看"), ("website", "# 标题")])
def test_rewrite_for_supported_platforms(platform, marker):
    result = rewrite_for_platform("标题", "第一段\n\n第二段", platform)
    assert marker in result


def test_rewrite_rejects_unknown_platform():
    with pytest.raises(ValueError, match="不支持"):
        rewrite_for_platform("标题", "正文", "unknown")


@pytest.mark.asyncio
async def test_model_rewrite_is_auditable_and_does_not_change_source(monkeypatch):
    fake_provider = type("Provider", (), {
        "model_name": "test-model",
        "generate": AsyncMock(return_value="模型改写结果"),
    })()
    monkeypatch.setattr(content_rewrite_service.LLMProviderFactory, "create", lambda _provider=None: fake_provider)

    result = await rewrite_with_model(
        title="标题", body="原始事实内容", platform="wechat", provider="openai", max_tokens=256,
    )

    assert result["content"] == "模型改写结果"
    assert result["platform"] == "wechat"
    assert result["provider"] == "openai"
    assert result["model"] == "test-model"
    assert len(result["source_content_sha256"]) == 64
    assert result["requires_human_review"] is True
    fake_provider.generate.assert_awaited_once()
