import pytest

from services.impl.agent_tool_registry import AgentToolRegistry
from services.impl.agent_runtime_service import AgentRuntimeService


def test_agent_tool_registry_is_explicit_and_descriptive():
    registry = AgentToolRegistry()
    tools = registry.describe()
    assert {tool["key"] for tool in tools} == {"safe_fetch_url", "extract_terms"}
    assert registry.get("shell") is None
    assert all(tool["read_only"] for tool in tools)


@pytest.mark.asyncio
async def test_extract_terms_is_bounded_and_does_not_call_external_system():
    result = await AgentToolRegistry().execute("extract_terms", {"text": "智能制造 AI platform"})
    assert result["terms"] == ["智能制造", "AI", "platform"]
    assert result["requires_approval"] is False

    with pytest.raises(ValueError, match="20000"):
        await AgentToolRegistry().execute("extract_terms", {"text": "x" * 20001})


def test_agent_workflow_rejects_unregistered_tools():
    with pytest.raises(ValueError, match="未注册"):
        AgentRuntimeService._validate_workflow(
            [{"key": "bad", "tool": "shell", "input": {}}], AgentToolRegistry()
        )
    with pytest.raises(ValueError, match="JSON 对象"):
        AgentRuntimeService._validate_workflow(
            [{"key": "fetch", "tool": "safe_fetch_url", "input": "url"}], AgentToolRegistry()
        )
