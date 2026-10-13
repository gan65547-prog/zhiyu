#!/usr/bin/env python3
"""将 LLM 配置片段合并到远端 .env。

接收两个参数：
1. 片段文件路径（包含 OPENAI_* / INTERNAL_* 键值对）
2. 目标 .env 文件路径

逻辑：
- 逐行读取片段文件
- 若键已存在于目标 .env，则用片段值覆盖
- 若键不存在，则追加到目标 .env
"""
from __future__ import annotations

import sys
from pathlib import Path


def load_fragment(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def merge_into_env(fragment: dict[str, str], env_path: Path) -> None:
    if not fragment:
        print("No fragment to merge, skipping.")
        return

    lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines() if env_path.is_file() else []

    existing_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            existing_keys.add(k)
            if k in fragment:
                new_lines.append(f"{k}={fragment[k]}")
                continue
        new_lines.append(line)

    for k, v in fragment.items():
        if k not in existing_keys:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Merged {len(fragment)} keys into {env_path}")


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: apply_llm_env_fragment.py <fragment_file> <target_env_file>", file=sys.stderr)
        return 1

    fragment_path = Path(sys.argv[1])
    env_path = Path(sys.argv[2])

    fragment = load_fragment(fragment_path)
    merge_into_env(fragment, env_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
