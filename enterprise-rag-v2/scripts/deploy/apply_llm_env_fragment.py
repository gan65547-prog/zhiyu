#!/usr/bin/env python3
"""将片段中的 KEY=value 合并进目标 .env：同名校验覆盖，其余行保留。"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: apply_llm_env_fragment.py <fragment_path> <target.env>", file=sys.stderr)
        return 2
    frag_path = Path(sys.argv[1])
    env_path = Path(sys.argv[2])
    if not frag_path.is_file():
        return 0
    frag_body = frag_path.read_text(encoding="utf-8", errors="replace").strip()
    if not frag_body:
        return 0

    keys: set[str] = set()
    frag_lines: list[str] = []
    for raw in frag_body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k = line.split("=", 1)[0].strip()
        keys.add(k)
        frag_lines.append(raw.rstrip())

    prev = env_path.read_text(encoding="utf-8", errors="replace").splitlines() if env_path.is_file() else []
    kept: list[str] = []
    for raw in prev:
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k = line.split("=", 1)[0].strip()
            if k in keys:
                continue
        kept.append(raw)

    out_lines = kept + frag_lines
    env_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
