#!/usr/bin/env python3
"""根据 pyproject.toml 的 semver 与已有 release tag 计算下一版发布号。

格式: v{major}.{minor}.{patch}_{YYYYMMDDHHMM}_{git_sha8}
每次发布 patch 在「同 major.minor」下 +1；若无历史 tag 则首次使用 pyproject 中的 patch。
"""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    with (root / "pyproject.toml").open("rb") as f:
        pv = tomllib.load(f)["project"]["version"]
    parts = pv.split(".")
    if len(parts) != 3:
        print(f"invalid pyproject version: {pv!r}", file=sys.stderr)
        sys.exit(1)
    ma, mi, pa = int(parts[0]), int(parts[1]), int(parts[2])

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--short=8", "HEAD"],
        text=True,
    ).strip()

    tags = subprocess.check_output(
        ["git", "-C", str(root), "tag", "-l"],
        text=True,
    ).splitlines()

    esc_ma, esc_mi = re.escape(str(ma)), re.escape(str(mi))
    pat = re.compile(rf"^v{esc_ma}\.{esc_mi}\.(\d+)_(\d{{12}})_([0-9a-f]{{8}})$")
    max_p: int | None = None
    for t in tags:
        s = t.removeprefix("release/")
        m = pat.match(s)
        if m:
            p = int(m.group(1))
            max_p = p if max_p is None else max(max_p, p)

    new_p = pa if max_p is None else max_p + 1
    print(f"v{ma}.{mi}.{new_p}_{ts}_{sha}")


if __name__ == "__main__":
    main()
