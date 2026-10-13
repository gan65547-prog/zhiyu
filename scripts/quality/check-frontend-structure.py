#!/usr/bin/env python3
"""Check frontend file/function shape with debt baseline and growth budgets.

This is intentionally a conservative structural check, not a formatter or a
replacement for TypeScript compilation. It blocks new oversized Vue/TS files
and functions while allowing measured legacy debt to grow only within review
budget. Complex refactors must preserve cohesive component boundaries.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_FILE_LIMIT = 800
DEFAULT_FUNCTION_LIMIT = 120
MAX_SOURCE_LINE_LENGTH = 500
HARD_FILE_LIMIT = 2000
HARD_FUNCTION_LIMIT = 400

FUNCTION_START = re.compile(
    r"^\s*(?:(?:export\s+)?(?:async\s+)?function\s+(?P<function>[\w$]+)|"
    r"(?:const|let)\s+(?P<arrow>[\w$]+)\s*=\s*(?:async\s*)?(?:\([^\n]*\)|[\w$]+)\s*=>)\s*\{"
)


def script_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix != ".vue":
        return text.splitlines()
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", text, flags=re.DOTALL)
    return "\n".join(blocks).splitlines()


def complexity(text: str) -> int:
    score = 1
    score += len(re.findall(r"\b(?:if|for|while|catch|switch)\b", text))
    score += text.count("&&") + text.count("||") + text.count("?")
    return score


def function_findings(path: Path, lines: list[str], key: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        match = FUNCTION_START.match(lines[index])
        if not match:
            index += 1
            continue
        name = match.group("function") or match.group("arrow") or "anonymous"
        start = index
        body = []
        balance = 0
        opened = False
        while index < len(lines):
            line = lines[index]
            body.append(line)
            balance += line.count("{") - line.count("}")
            opened = opened or "{" in line
            index += 1
            if opened and balance <= 0:
                break
        length = index - start
        score = complexity("\n".join(body))
        if length > DEFAULT_FUNCTION_LIMIT:
            findings.append({"kind": "function", "key": f"{key}::{name}", "lines": length, "complexity": score, "line": start + 1})
    return findings


def scan(roots: list[Path], repo_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    observed = {"files": {}, "functions": {}, "long_lines": {}}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.resolve().rglob("*")):
            if path.suffix not in {".vue", ".ts"} or "node_modules" in path.parts or not path.is_file():
                continue
            key = path.relative_to(repo_root).as_posix()
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if len(lines) > DEFAULT_FILE_LIMIT:
                findings.append({"kind": "file", "key": key, "lines": len(lines)})
                observed["files"][key] = {"max_lines": len(lines)}
            findings.extend(function_findings(path, script_lines(path), key))
            long_lines = [len(line) for line in lines if len(line) > MAX_SOURCE_LINE_LENGTH]
            if long_lines:
                findings.append({
                    "kind": "long_line",
                    "key": key,
                    "count": len(long_lines),
                    "max_length": max(long_lines),
                })
                observed["long_lines"][key] = {
                    "count": len(long_lines), "max_length": max(long_lines),
                }
            for finding in findings:
                if finding["kind"] == "function" and finding["key"].startswith(f"{key}::"):
                    observed["functions"][finding["key"]] = {"max_lines": finding["lines"], "max_complexity": finding["complexity"]}
    return observed, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    observed, findings = scan(args.root, repo_root)
    if args.report:
        print(json.dumps(observed, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] frontend quality baseline unavailable: {exc}")
        return 1
    failures: list[str] = []
    warnings: list[str] = []
    for finding in findings:
        allowed = baseline.get(f"{finding['kind']}s", {}).get(finding["key"])
        if allowed is None:
            failures.append(f"new frontend structural violation requires refactor or explicit baseline: {finding['key']} (lines={finding.get('lines')})")
            continue
        base_lines = int(allowed.get("max_lines", 0))
        if finding["kind"] == "file":
            growth = allowed.get("growth_budget_lines", max(50, int(base_lines * 0.30)))
            if finding["lines"] > base_lines + growth:
                failures.append(f"frontend file grew beyond budget: {finding['key']}")
            elif finding["lines"] > base_lines:
                if finding["lines"] > HARD_FILE_LIMIT:
                    warnings.append(f"legacy frontend file crossed hard threshold within approved growth budget: {finding['key']}")
                else:
                    warnings.append(f"frontend file grew within review budget: {finding['key']}")
        elif finding["kind"] == "long_line":
            allowed_count = int(allowed.get("max_count", 0))
            if finding["count"] > allowed_count:
                failures.append(
                    f"new frontend source lines exceed {MAX_SOURCE_LINE_LENGTH} characters: {finding['key']} "
                    f"(count={finding['count']}, max={finding['max_length']})"
                )
            elif finding["max_length"] > int(allowed.get("max_length", 0)):
                failures.append(
                    f"frontend source line grew beyond baseline: {finding['key']} "
                    f"(max={finding['max_length']})"
                )
        elif finding["kind"] == "function":
            line_growth = allowed.get("growth_budget_lines", max(30, int(base_lines * 0.20)))
            if finding["lines"] > base_lines + line_growth:
                failures.append(f"frontend function grew beyond budget: {finding['key']}")
            elif finding["lines"] > base_lines:
                if finding["lines"] > HARD_FUNCTION_LIMIT:
                    warnings.append(f"legacy frontend function crossed hard threshold within approved growth budget: {finding['key']}")
                else:
                    warnings.append(f"frontend function grew within review budget: {finding['key']}")
    if failures:
        print("===== FRONTEND STRUCTURE GATE: FAILED =====")
        print("\n".join(f"[FAIL] {item}" for item in failures))
        return 1
    if warnings:
        print("===== FRONTEND STRUCTURE GATE: PASS WITH REVIEW WARNINGS =====")
        print("\n".join(f"[WARN] {item}" for item in warnings))
        return 0
    print(f"===== FRONTEND STRUCTURE GATE: PASS (file>{DEFAULT_FILE_LIMIT}, function>{DEFAULT_FUNCTION_LIMIT}) =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
