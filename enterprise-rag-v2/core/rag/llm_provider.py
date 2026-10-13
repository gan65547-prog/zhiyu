"""
LLM响应生成器

提供大语言模型响应生成功能
"""

from typing import List, Optional, AsyncIterator, Dict, Any
import httpx
import json
import os
import re

from infrastructure.logging.logger import get_logger

_llm_log = get_logger("core.rag.llm_provider")

from core.rag_config import get_rag_config, normalize_openai_base_url
from core.interfaces.rag_engine import RetrievedDocument


def _build_errata_prefix(doc: RetrievedDocument) -> str:
    """为有勘误的文档构建警告前缀，注入到 LLM 提示词中"""
    errata_list = doc.metadata.get("_errata", [])
    if not errata_list:
        return ""

    lines = ["!!! 勘误警告 — 以下资料有已知错误，请优先参考勘误信息 !!!"]
    for e in errata_list:
        sev_label = {"critical": "严重", "major": "重要", "minor": "轻微", "note": "备注"}.get(
            e.get("severity", ""), e.get("severity", "")
        )
        line = f"  [{e['errata_code']}] {e['title']} (严重程度: {sev_label})"
        if e.get("fix_suggestion"):
            line += f"\n  修正建议: {e['fix_suggestion']}"
        lines.append(line)
    lines.append("")

    return "\n".join(lines) + "\n"


def _deterministic_evidence_response(
    query: str,
    documents: List[RetrievedDocument],
) -> str:
    """远程模型不可用时，基于检索结果生成可追溯的确定性摘要。

    这不是伪装成模型回答，而是把当前已经检索到的证据重新排序、去重并
    截取成可继续阅读的结果，保证网络或模型故障时问答仍然有用。
    """
    if not documents:
        return "当前没有检索到可引用的资料。请先导入并完成索引，再继续提问。"

    compact_query = re.sub(r"\s+", "", query or "").lower()
    query_tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", compact_query))
    if len(compact_query) >= 2:
        query_tokens.update(compact_query[index:index + 2] for index in range(len(compact_query) - 1))

    ranked: list[tuple[float, int, RetrievedDocument]] = []
    seen: set[str] = set()
    for index, document in enumerate(documents):
        content = re.sub(r"\s+", " ", document.content or "").strip()
        if not content:
            continue
        fingerprint = content[:500]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        content_lower = content.lower()
        overlap = sum(1 for token in query_tokens if token in content_lower)
        ranked.append((float(document.score or 0) + overlap * 0.35, -index, document))

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    lines = ["模型服务当前不可用，以下为基于已检索证据的确定性摘要：", ""]
    for index, (_score, _order, document) in enumerate(ranked[:3], start=1):
        snippet = re.sub(r"\s+", " ", document.content or "").strip()
        if len(snippet) > 360:
            snippet = snippet[:360].rstrip("，。；、 ") + "…"
        source = document.document_name or "未命名文档"
        lines.append(f"{index}. {snippet}")
        lines.append(f"   来源：{source}")
    lines.extend(["", "你可以继续追问；待模型服务恢复后，系统会生成完整的综合回答。"])
    return "\n".join(lines)


class ResponseGenerator:
    """响应生成器抽象接口"""

    async def generate(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """生成响应"""
        pass

    async def generate_stream(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[str]:
        """流式生成响应"""
        pass


class OllamaLLMProvider(ResponseGenerator):
    """Ollama LLM提供商"""

    def __init__(self, model_name: Optional[str] = None):
        self.config = get_rag_config()
        self.model_name = model_name or self.config.llm_model
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端，带连接池限制"""
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            self._client = httpx.AsyncClient(timeout=120.0, limits=limits)
        return self._client

    def _build_prompt(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """构建提示词"""
        context_parts = []
        for doc in documents:
            doc_name = doc.document_name or "未知文档"
            errata_prefix = _build_errata_prefix(doc)
            context_parts.append(
                f"{errata_prefix}[来源文档: {doc_name}]\n{doc.content}"
            )

        context = "\n\n".join(context_parts)

        history_parts = []
        if conversation_history:
            for msg in conversation_history[-5:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                role_label = "用户" if role == "user" else "你"
                history_parts.append(f"{role_label}: {content}")

        history = "\n".join(history_parts) if history_parts else ""

        prompt = f"""你是一个企业知识库助手，请根据提供的资料回答用户的问题。

## 资料
{context if context else "（无相关检索资料）"}

## 对话历史
{history if history else "（无历史对话）"}

## 当前问题
{query}

## 回答要求
1. 基于资料内容回答，不要编造。如果资料中完全没有相关信息，请直接说"我查到的资料里没有相关信息"
2. 回答自然口语化，像在和同事聊天，不要用生硬的模板风格
3. 注意对话历史中的上下文，如果是追问或补充，直接回答增量内容即可
4. 引用资料时标注来源文档名称，例如：根据《员工手册》中的规定...
5. 如果用户只是打招呼（你好、嗨等），可以不用检索直接友好回应
6. 如果多份资料内容有矛盾，指出不同资料的说法差异，不要强行统一
7. 优先回答用户最关心的核心问题，不要罗列所有细节
8. 回答结构要求：先综合所有相关资料，给出一个完整、连贯、有条理的回答，不要简单罗列原文片段；然后在回答的最后，单独用"参考文档"小节列出本次引用的文档名称列表"""

        return prompt

    async def generate(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """生成响应"""
        client = await self._get_client()
        prompt = self._build_prompt(query, documents, conversation_history)

        try:
            response = await client.post(
                f"{self.config.llm_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
            _llm_log.exception("Ollama 非流式调用失败")

        return self._fallback_response(query, documents)

    async def generate_stream(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[str]:
        """流式生成响应"""
        client = await self._get_client()
        prompt = self._build_prompt(query, documents, conversation_history)

        try:
            async with client.stream(
                "POST",
                f"{self.config.llm_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            # Ollama /api/generate 流式字段是 response；
                            # 兼容历史/其他 provider 可能返回的 token 字段。
                            token = data.get("response", "") or data.get("token", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
            _llm_log.exception("Ollama 流式调用失败")
            yield self._fallback_response(query, documents)

    def _fallback_response(
        self,
        query: str,
        documents: List[RetrievedDocument]
    ) -> str:
        """当 LLM 不可用时的可追溯证据摘要。"""
        return _deterministic_evidence_response(query, documents)

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


class DeepSeekProvider(ResponseGenerator):
    """DeepSeek API提供商"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        self.config = get_rag_config()
        self.api_key = api_key or self.config.deepseek_api_key
        self.model_name = model or self.config.deepseek_model
        self.base_url = normalize_openai_base_url(base_url or self.config.deepseek_base_url or "")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端，带连接池限制"""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            self._client = httpx.AsyncClient(
                timeout=120.0,
                headers=headers,
                limits=limits
            )
        return self._client

    def _build_messages(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []
        
        # 系统提示
        system_prompt = """你是一个企业知识库助手，请根据提供的资料回答用户的问题。

## 回答要求
1. 基于资料内容回答，不要编造。如果资料中完全没有相关信息，直接说"我查到的资料里没有相关信息"，不要尝试编造答案
2. 回答自然口语化，像在和同事聊天，不要用生硬的模板风格
3. 注意对话历史中的上下文，如果是追问或补充，直接回答增量内容即可
4. 引用资料时标注来源文档名称，例如：根据《员工手册》中的规定...
5. 如果用户只是打招呼（你好、嗨等），可以不用检索直接友好回应
6. 如果多份资料内容有矛盾，指出不同资料的说法差异，不要强行统一
7. 优先回答用户最关心的核心问题，不要罗列所有细节
8. 回答结构要求：先综合所有相关资料，给出一个完整、连贯、有条理的回答，不要简单罗列原文片段；然后在回答的最后，单独用"参考文档"小节列出本次引用的文档名称列表"""
        
        messages.append({"role": "system", "content": system_prompt})
        
        # 添加对话历史
        if conversation_history:
            for msg in conversation_history[-5:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    messages.append({"role": "assistant", "content": content})
        
        # 构建上下文
        context_parts = []
        for doc in documents:
            doc_name = doc.document_name or "未知文档"
            errata_prefix = _build_errata_prefix(doc)
            context_parts.append(
                f"{errata_prefix}[文档: {doc_name}]\n{doc.content}"
            )
        
        context = "\n\n".join(context_parts) if context_parts else "无相关上下文"
        
        # 添加当前问题
        user_message = f"""[上下文信息]
{context}

[用户问题]
{query}"""
        
        messages.append({"role": "user", "content": user_message})
        
        return messages

    def _fallback_response(
        self,
        query: str,
        documents: List[RetrievedDocument]
    ) -> str:
        """当 LLM 不可用时的可追溯证据摘要。"""
        return _deterministic_evidence_response(query, documents)

    async def generate(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """使用DeepSeek API生成响应"""
        if not self.api_key:
            return "错误：未配置 API 密钥，请在 .env 中设置 OPENAI_API_KEY（DeepSeek 兼容）"

        client = await self._get_client()
        messages = self._build_messages(query, documents, conversation_history)

        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                }
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                _llm_log.error(f"DeepSeek API错误: {response.status_code} - {response.text}")
                return self._fallback_response(query, documents)
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            _llm_log.exception("DeepSeek/OpenAI 兼容接口非流式调用异常")
            return self._fallback_response(query, documents)

    async def generate_stream(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncIterator[str]:
        """流式生成响应"""
        if not self.api_key:
            yield "错误：未配置 API 密钥，请在 .env 中设置 OPENAI_API_KEY（DeepSeek 兼容）"
            return

        client = await self._get_client()
        messages = self._build_messages(query, documents, conversation_history)

        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    try:
                        body = await response.aread()
                        detail = body.decode("utf-8", errors="replace")[:1200]
                    except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
                        detail = getattr(response, "reason_phrase", None) or ""
                    _llm_log.error(f"DeepSeek API返回错误 HTTP {response.status_code}。详情: {detail}")
                    yield self._fallback_response(query, documents)
                    return
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                        except (KeyError, IndexError) as err:
                            _llm_log.warning("解析流式 chunk 异常: %s, line=%s", err, line[:200])
                            continue
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            _llm_log.exception("DeepSeek/OpenAI 兼容接口流式调用异常")
            yield self._fallback_response(query, documents)

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


class OpenAIProvider(DeepSeekProvider):
    """通用 OpenAI 兼容聊天 Provider。

    DeepSeekProvider 已实现兼容协议的请求、流式响应和证据提示词组装；
    这里仅切换到通用配置入口，避免不同厂商复制一套调用逻辑。
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(api_key=api_key, model=model, base_url=base_url or os.getenv("OPENAI_BASE_URL", ""))


class LLMProviderFactory:
    """按显式配置创建允许的 LLM Provider。"""

    _PROVIDERS = {"ollama": OllamaLLMProvider, "deepseek": DeepSeekProvider, "openai": OpenAIProvider}

    @classmethod
    def create(cls, provider: str | None = None, **kwargs: Any) -> ResponseGenerator:
        key = (provider or os.getenv("LLM_PROVIDER", "deepseek")).strip().lower()
        provider_type = cls._PROVIDERS.get(key)
        if provider_type is None:
            raise ValueError(f"不支持的 LLM provider: {key}")
        return provider_type(**kwargs)
