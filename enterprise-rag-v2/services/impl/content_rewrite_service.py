"""内容多平台改写策略；不负责审核或平台发布。"""

import hashlib
import os
import re
from typing import Any

from core.interfaces.rag_engine import RetrievedDocument
from core.rag.llm_provider import LLMProviderFactory


SUPPORTED_CONTENT_PLATFORMS = {"wechat", "x", "zhihu", "website"}


def _create_llm(provider: str, **kwargs: Any):
    """创建模型并兼容旧版/测试替身只接受 provider 参数的工厂。"""
    try:
        return LLMProviderFactory.create(provider, **kwargs)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return LLMProviderFactory.create(provider)


def rewrite_for_platform(title: str, body: str, platform: str) -> str:
    platform = platform.strip().lower()
    if platform not in SUPPORTED_CONTENT_PLATFORMS:
        raise ValueError(f"不支持的平台改写类型: {platform}")
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", body.strip()) if part.strip()]
    if platform == "x":
        compact = re.sub(r"\s+", " ", body).strip()
        return f"{title}\n\n{compact[:240]}" + ("…" if len(compact) > 240 else "")
    if platform == "zhihu":
        return f"# {title}\n\n" + "\n\n".join(paragraphs) + "\n\n你怎么看？欢迎结合实际案例讨论。"
    if platform == "wechat":
        return f"【{title}】\n\n" + "\n\n".join(paragraphs) + "\n\n欢迎转发给需要的团队。"
    return f"# {title}\n\n" + "\n\n".join(paragraphs)


async def rewrite_with_model(
    *,
    title: str,
    body: str,
    platform: str,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    """调用白名单模型生成平台版本，并返回可审计元数据。

    原稿正文不会传入修改操作；调用方必须把返回结果放到独立变体字段，
    并保持人工审核状态。模型只接收当前草稿这一条不可信内容，不获得工具权限。
    """
    normalized_platform = platform.strip().lower()
    if normalized_platform not in SUPPORTED_CONTENT_PLATFORMS:
        raise ValueError(f"不支持的平台改写类型: {normalized_platform}")
    if not body.strip():
        raise ValueError("空草稿不能进行模型改写")
    if not 128 <= int(max_tokens) <= 4000:
        raise ValueError("模型改写 max_tokens 必须在 128 到 4000 之间")

    selected_provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()
    if selected_provider == "ollama":
        llm = _create_llm(selected_provider, model_name=model)
    else:
        llm = _create_llm(selected_provider, api_key=api_key, model=model, base_url=base_url)
    document = RetrievedDocument(
        id="content-draft",
        content=f"标题：{title}\n\n正文：\n{body}",
        metadata={"source_type": "content_draft"},
        score=1.0,
        document_id="content-draft",
        document_name="当前内容草稿",
        chunk_index=0,
    )
    prompt = (
        f"请将当前内容改写为 {normalized_platform} 平台版本。"
        "保留事实，不新增无法从原稿验证的观点；只返回改写后的标题和正文，"
        "不要输出解释、来源列表或 Markdown 代码块。结果必须进入人工审核。"
    )
    generated = await llm.generate(prompt, [document], temperature=0.3, max_tokens=int(max_tokens))
    model_name = getattr(llm, "model_name", llm.__class__.__name__)
    return {
        "content": generated.strip(),
        "platform": normalized_platform,
        "provider": (provider or "configured").strip().lower() if provider else "configured",
        "model": model_name,
        "source_content_sha256": hashlib.sha256(f"{title}\n{body}".encode("utf-8")).hexdigest(),
        "requires_human_review": True,
    }
