from core.workflow_contracts import workflow_contains_required_steps


RESEARCH_WORKFLOW = [{"key": key} for key in ("collect_sources", "build_evidence", "synthesize_findings", "generate_report", "human_review")]
ASSET_ORGANIZE_WORKFLOW = [{"key": key} for key in ("read_material", "summarize", "extract_tags", "propose_knowledge", "human_review")]


def test_research_runtime_does_not_reuse_tool_only_definition():
    tool_only = [{"key": "extract_terms", "label": "提取候选术语", "tool": "extract_terms"}]
    assert not workflow_contains_required_steps(tool_only, RESEARCH_WORKFLOW)
    assert workflow_contains_required_steps(RESEARCH_WORKFLOW, RESEARCH_WORKFLOW)


def test_asset_runtime_requires_the_complete_builtin_workflow():
    partial = ASSET_ORGANIZE_WORKFLOW[:-1]
    assert not workflow_contains_required_steps(partial, ASSET_ORGANIZE_WORKFLOW)
    assert workflow_contains_required_steps(ASSET_ORGANIZE_WORKFLOW, ASSET_ORGANIZE_WORKFLOW)
