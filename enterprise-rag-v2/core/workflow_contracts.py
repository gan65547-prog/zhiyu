from typing import Any


def workflow_contains_required_steps(workflow: list[dict[str, Any]] | None, required_workflow: list[dict[str, Any]]) -> bool:
    """Return whether a stored definition can safely drive a built-in workflow."""
    keys = {str(step.get("key")) for step in (workflow or [])}
    return {str(step["key"]) for step in required_workflow}.issubset(keys)
