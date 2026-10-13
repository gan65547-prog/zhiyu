#!/usr/bin/env python3
"""Enforce maintainable code shape without hiding existing technical debt.

The baseline records known legacy violations. A baseline item may grow within
its review budget; new violations block the gate so normal feature growth is
not confused with a newly introduced structural debt.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


DEFAULT_FILE_LIMIT = 800
DEFAULT_FUNCTION_LIMIT = 120
DEFAULT_COMPLEXITY_LIMIT = 15
HARD_FILE_LIMIT = 2000
HARD_FUNCTION_LIMIT = 400
HARD_COMPLEXITY_LIMIT = 50


def complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(0, len(child.values) - 1)
        elif isinstance(child, ast.IfExp):
            score += 1
        elif isinstance(child, ast.comprehension):
            score += 1 + len(child.ifs)
        elif isinstance(child, ast.match_case):
            score += 1
    return score


def function_key(path: Path, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    return f"{path.as_posix()}::{node.name}"


def scan(roots: list[Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    observed = {"files": {}, "functions": {}}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            relative = path.as_posix()
            lines = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
            if lines > DEFAULT_FILE_LIMIT:
                finding = {"kind": "file", "key": relative, "lines": lines}
                findings.append(finding)
                observed["files"][relative] = {"max_lines": lines}
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except SyntaxError as exc:
                findings.append({"kind": "syntax", "key": relative, "error": str(exc)})
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                end = getattr(node, "end_lineno", node.lineno)
                length = end - node.lineno + 1
                score = complexity(node)
                key = function_key(path, node)
                if length > DEFAULT_FUNCTION_LIMIT or score > DEFAULT_COMPLEXITY_LIMIT:
                    finding = {
                        "kind": "function",
                        "key": key,
                        "lines": length,
                        "complexity": score,
                        "line": node.lineno,
                    }
                    findings.append(finding)
                    observed["functions"][key] = {
                        "max_lines": length,
                        "max_complexity": score,
                    }
    return observed, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    observed, findings = scan(args.root)
    if args.report:
        print(json.dumps(observed, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] code quality baseline unavailable: {exc}")
        return 1

    failures: list[str] = []
    warnings: list[str] = []
    for finding in findings:
        if finding["kind"] == "syntax":
            failures.append(f"syntax error: {finding['key']}: {finding['error']}")
            continue
        section = baseline.get(f"{finding['kind']}s", {})
        allowed = section.get(finding["key"])
        if allowed is None:
            failures.append(
                f"new structural violation requires refactor or explicit baseline: "
                f"{finding['key']} (lines={finding.get('lines')}, "
                f"complexity={finding.get('complexity')})"
            )
            continue
        if finding["kind"] == "file":
            baseline_lines = allowed.get("max_lines", 0)
            growth = allowed.get("growth_budget_lines", max(50, int(baseline_lines * 0.30)))
            if finding["lines"] > baseline_lines + growth:
                failures.append(f"file grew beyond budget: {finding['key']}")
            elif finding["lines"] > baseline_lines:
                if finding["lines"] > HARD_FILE_LIMIT:
                    warnings.append(f"legacy file crossed hard threshold within approved growth budget: {finding['key']}")
                else:
                    warnings.append(f"file grew within review budget: {finding['key']}")
        if finding["kind"] == "function":
            baseline_lines = allowed.get("max_lines", 0)
            baseline_complexity = allowed.get("max_complexity", 0)
            line_growth = allowed.get("growth_budget_lines", max(30, int(baseline_lines * 0.20)))
            complexity_growth = allowed.get("growth_budget_complexity", 3)
            if finding["lines"] > baseline_lines + line_growth:
                failures.append(f"function grew beyond budget: {finding['key']}")
            elif finding["complexity"] > baseline_complexity + complexity_growth:
                failures.append(f"function complexity grew beyond budget: {finding['key']}")
            elif finding["lines"] > baseline_lines or finding["complexity"] > baseline_complexity:
                if finding["lines"] > HARD_FUNCTION_LIMIT or finding["complexity"] > HARD_COMPLEXITY_LIMIT:
                    warnings.append(f"legacy function crossed hard threshold within approved growth budget: {finding['key']}")
                else:
                    warnings.append(f"function grew within review budget: {finding['key']}")

    if failures:
        print("===== CODE STRUCTURE GATE: FAILED =====")
        print("\n".join(f"[FAIL] {item}" for item in failures))
        return 1
    if warnings:
        print("===== CODE STRUCTURE GATE: PASS WITH REVIEW WARNINGS =====")
        print("\n".join(f"[WARN] {item}" for item in warnings))
        return 0
    print(
        "===== CODE STRUCTURE GATE: PASS "
        f"(file>{DEFAULT_FILE_LIMIT}, function>{DEFAULT_FUNCTION_LIMIT}, complexity>{DEFAULT_COMPLEXITY_LIMIT}) ====="
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
