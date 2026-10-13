#!/usr/bin/env python3
"""Check dependency direction with a small, measurable legacy baseline."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


RULES = {
    "api": ("sqlalchemy", "infrastructure.database"),
    "services": ("api",),
    "core": ("api",),
}


def imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return values


def scan(roots: list[Path]) -> dict[str, int]:
    violations: dict[str, int] = {}
    for root in roots:
        layer = root.name
        forbidden = RULES.get(layer, ())
        if not forbidden:
            continue
        for path in root.rglob("*.py"):
            for imported in imports(path):
                for prefix in forbidden:
                    if imported == prefix or imported.startswith(prefix + "."):
                        key = f"{path.as_posix()}::{prefix}"
                        violations[key] = violations.get(key, 0) + 1
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", action="append", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        allowed = baseline.get("violations", {})
        reasons = baseline.get("reasons", {})
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] module boundary baseline unavailable: {exc}")
        return 1

    missing_reasons = [key for key in allowed if not str(reasons.get(key, "")).strip()]
    if missing_reasons:
        print("===== MODULE BOUNDARY GATE: FAILED =====")
        print("[FAIL] baseline entries require a reason: " + ", ".join(missing_reasons))
        return 1

    failures = []
    for key, count in scan(args.root).items():
        if count > allowed.get(key, 0):
            failures.append(f"{key}: {count} > baseline {allowed.get(key, 0)}")
    if failures:
        print("===== MODULE BOUNDARY GATE: FAILED =====")
        print("\n".join(f"[FAIL] {item}" for item in failures))
        return 1
    print("===== MODULE BOUNDARY GATE: PASS =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
