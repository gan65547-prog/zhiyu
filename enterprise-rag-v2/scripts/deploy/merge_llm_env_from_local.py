#!/usr/bin/env python3
"""从本地 .env 读取发布时需同步到远端的变量，写入片段文件（不落盘密钥到仓库）。

同步键：
- OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL（LLM）
- INTERNAL_API_KEYS、INTERNAL_IP_WHITELIST（/internal/admin，与 ops-center 联调）
"""
from __future__ import annotations

import sys
from pathlib import Path

KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "INTERNAL_API_KEYS",
    "INTERNAL_IP_WHITELIST",
)


def parse_env(path: Path) -> dict[str, str]:
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
        k = k.strip()
        if k in KEYS:
            out[k] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    local_env = root / ".env"
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    data = parse_env(local_env)
    if not data:
        # 无本地配置时写空文件，远端脚本可跳过合并
        body = ""
    else:
        lines = [f"{k}={data[k]}" for k in KEYS if k in data and data[k]]
        body = "\n".join(lines) + ("\n" if lines else "")
    if out_path:
        out_path.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
