#!/usr/bin/env python3
"""
通用知识目录导入器 — 将任意 markdown 目录导入 ganfy RAG 平台

支持:
  - 无 frontmatter 的普通 .md 文件（自动提取首个 # 标题或文件名）
  - 目录层级自动映射为标签
  - 按知识类型分 dataset（reference / engineering / notes）

用法:
  python3.12 scripts/import_directory_to_ganfy.py --source /path/to/md/dir --dataset "工程参考" --dry-run
  python3.12 scripts/import_directory_to_ganfy.py --source /path/to/md/dir --dataset "工程参考" --all
  python3.12 scripts/import_directory_to_ganfy.py --source documents/kb --dataset "团队知识" --all

环境变量:
  GANFY_BASE_URL  默认 http://localhost:8000
  GANFY_EMAIL     默认 admin@example.com
  GANFY_PASSWORD  默认 admin123
"""

from __future__ import annotations

import json
import os
import sys
import time
import hashlib
import argparse
import re
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).parent.parent.resolve()

BASE_URL = os.getenv("GANFY_BASE_URL", "http://localhost:8000")
LOGIN_EMAIL = os.getenv("GANFY_EMAIL", "admin@example.com")
PASSWORD = os.getenv("GANFY_PASSWORD", "admin123")


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def _extract_title(file_path: Path) -> str:
    """从文件提取标题：首个 # 标题 或 文件名"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# ") and not line.startswith("## "):
                    return line[2:].strip()
    except Exception:
        pass
    return file_path.stem


def _derive_tags(file_path: Path, base_dir: Path) -> list[str]:
    """从文件路径推导标签"""
    rel = file_path.relative_to(base_dir)
    parts = list(rel.parts[:-1])  # 去掉文件名
    return [p for p in parts if p not in ("", ".", "..")]


def parse_directory(source_dir: Path) -> list[dict]:
    """解析目录下所有 .md 文件"""
    pages = []
    md_files = sorted(source_dir.rglob("*.md"))

    for md_file in md_files:
        # 跳过隐藏文件和过短文件
        if md_file.name.startswith("."):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if len(content.strip()) < 20:
            continue

        title = _extract_title(md_file)
        tags = _derive_tags(md_file, source_dir)

        pages.append({
            "title": title,
            "content": content,
            "tags": tags,
            "source_file": str(md_file.relative_to(source_dir.parent)),
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest()[:12],
        })

    return pages


def _get_csrf_token(session: requests.Session, base_url: str) -> Optional[str]:
    try:
        r = session.get(f"{base_url}/api/v1/datasets/", timeout=10)
        token = r.headers.get("X-CSRF-Token")
        if not token:
            for cookie in session.cookies:
                if cookie.name == "csrf_token":
                    token = cookie.value
                    break
        return token
    except Exception:
        return None


def login(base_url: str) -> tuple:
    session = requests.Session()
    csrf_token = _get_csrf_token(session, base_url)
    try:
        headers = {}
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token
        r = session.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": LOGIN_EMAIL, "password": PASSWORD},
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            token = r.json().get("data", {}).get("access_token", "")
            new_csrf = _get_csrf_token(session, base_url)
            return token, session, new_csrf or csrf_token
    except Exception as e:
        print(f"  {Colors.RED}Login failed: {e}{Colors.END}")
    return None, None, None


def _make_headers(token: str, csrf_token: Optional[str]) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        h["X-CSRF-Token"] = csrf_token
    return h


def get_or_create_dataset(
    base_url: str, session: requests.Session, token: str,
    csrf_token: Optional[str], dataset_name: str, knowledge_type: str = "reference",
) -> Optional[str]:
    headers = _make_headers(token, csrf_token)

    try:
        r = session.get(
            f"{base_url}/api/v1/datasets/",
            headers=headers,
            params={"keyword": dataset_name, "page_size": 50},
            timeout=10,
        )
        if r.status_code == 200:
            for ds in r.json().get("data", {}).get("items", []):
                if ds.get("name") == dataset_name:
                    return ds["id"]
    except Exception:
        pass

    try:
        r = session.post(
            f"{base_url}/api/v1/datasets/",
            headers=headers,
            json={
                "name": dataset_name,
                "description": f"从目录导入 — {dataset_name}",
                "chunk_size": 500,
                "chunk_overlap": 50,
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            ds_id = r.json().get("data", {}).get("id")
            if ds_id:
                print(f"  {Colors.GREEN}Created dataset '{dataset_name}' → {ds_id}{Colors.END}")
                return ds_id
    except Exception as e:
        print(f"  {Colors.RED}Create dataset failed: {e}{Colors.END}")

    return None


def upload_page(
    base_url: str, session: requests.Session, token: str,
    csrf_token: Optional[str], dataset_id: str, page: dict,
    knowledge_type: str,
) -> tuple[bool, str]:
    import tempfile

    file_name = Path(page["source_file"]).name
    metadata = {
        "source_file": page["source_file"],
        "content_hash": page["content_hash"],
        "import_tags": page["tags"],
    }
    process_rule = json.dumps({
        "tags": page["tags"],
        "metadata": metadata,
        "knowledge_type": knowledge_type,
    })

    headers = _make_headers(token, csrf_token)

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8",
        ) as f:
            f.write(page["content"])
            tmp_path = f.name

        with open(tmp_path, "rb") as fh:
            r = session.post(
                f"{base_url}/api/v1/documents/datasets/{dataset_id}",
                files={"file": (file_name, fh, "text/markdown")},
                data={"process_rule": process_rule},
                headers=headers,
                timeout=60,
            )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if r.status_code not in (200, 201):
        return False, f"HTTP {r.status_code}: {r.text[:120]}"

    doc_id = r.json().get("data", {}).get("id")
    if not doc_id:
        return False, "No document_id in response"

    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            r2 = session.get(
                f"{base_url}/api/v1/documents/{doc_id}",
                headers=headers, timeout=10,
            )
            if r2.status_code == 200:
                d = r2.json().get("data", {})
                st = d.get("status", "")
                if st == "completed":
                    return True, f"doc_id={doc_id}, {d.get('chunk_count', 0)} chunks"
                elif st == "failed":
                    return False, f"processing failed: {d.get('error_message', '')}"
            time.sleep(1)
        except Exception:
            time.sleep(2)

    return False, f"processing timeout (doc_id={doc_id})"


def print_summary(pages: list[dict]) -> None:
    """Dry-run: 展示解析结果"""
    # 按上级目录分组
    by_parent = {}
    for p in pages:
        parent = str(Path(p["source_file"]).parts[0] if "/" in p["source_file"] else "root")
        by_parent.setdefault(parent, []).append(p)

    for parent, items in sorted(by_parent.items()):
        print(f"\n{Colors.BOLD}{Colors.CYAN}── {parent} ({len(items)} files) ──{Colors.END}")
        for p in items[:5]:
            print(f"  - {Colors.BOLD}{p['title']}{Colors.END}")
            print(f"    file: {p['source_file']}")
            if p["tags"]:
                print(f"    tags: {p['tags']}")
        if len(items) > 5:
            print(f"  ... and {len(items) - 5} more")


def main():
    p = argparse.ArgumentParser(
        description="将目录下 .md 文件批量导入 ganfy RAG 平台",
    )
    p.add_argument("--source", required=True, help="源目录路径")
    p.add_argument("--dataset", required=True, help="数据集名称")
    p.add_argument("--knowledge-type", default="reference",
                   choices=["topic", "concept", "summary", "recipe", "reference", "errata"],
                   help="知识类型 (默认: reference)")
    p.add_argument("--dry-run", action="store_true", help="只解析展示，不上传")
    p.add_argument("--all", action="store_true", help="全量导入")
    p.add_argument("--base-url", default=BASE_URL, help=f"ganfy API 地址 (默认: {BASE_URL})")
    p.add_argument("--limit", type=int, default=0, help="限制导入条数（调试用）")
    args = p.parse_args()

    source_dir = Path(args.source).resolve()
    if not source_dir.is_dir():
        print(f"{Colors.RED}源目录不存在: {source_dir}{Colors.END}")
        return 1

    print(f"{Colors.BOLD}{Colors.CYAN}目录 → ganfy 知识导入器{Colors.END}")
    print(f"  源目录: {source_dir}")

    pages = parse_directory(source_dir)
    if not pages:
        print(f"{Colors.RED}No .md files found in {source_dir}{Colors.END}")
        return 1

    print(f"  解析到 {len(pages)} 个页面")

    if args.limit > 0:
        pages = pages[:args.limit]
        print(f"  限制: 只导入前 {args.limit} 个")

    if args.dry_run:
        print_summary(pages)
        return 0

    if not args.all:
        print(f"{Colors.YELLOW}请指定 --all 确认导入，或 --dry-run 预览{Colors.END}")
        return 1

    print(f"\n{Colors.BOLD}连接 ganfy: {args.base_url}{Colors.END}")
    token, session, csrf_token = login(args.base_url)
    if not token:
        print(f"{Colors.RED}登录失败{Colors.END}")
        return 1

    dataset_id = get_or_create_dataset(
        args.base_url, session, token, csrf_token,
        args.dataset, args.knowledge_type,
    )
    if not dataset_id:
        print(f"{Colors.RED}无法创建/获取数据集{Colors.END}")
        return 1

    ok, fail = 0, 0
    for i, page in enumerate(pages, 1):
        # 每 20 个文件重新认证，防止 JWT 过期
        if i > 1 and i % 20 == 0:
            new_token, new_session, new_csrf = login(args.base_url)
            if new_token:
                token, session, csrf_token = new_token, new_session, new_csrf
                print(f"  {Colors.CYAN}[re-auth OK]{Colors.END}")

        name = page["title"]
        print(f"  [{i}/{len(pages)}] {name} ...", end=" ", flush=True)
        success, detail = upload_page(
            args.base_url, session, token, csrf_token, dataset_id, page, args.knowledge_type,
        )
        if success:
            print(f"{Colors.GREEN}OK{Colors.END} ({detail})")
            ok += 1
        else:
            print(f"{Colors.RED}FAIL{Colors.END} ({detail})")
            fail += 1

    print(f"\n{Colors.BOLD}导入完成: {Colors.GREEN}{ok} OK{Colors.END}, {Colors.RED}{fail} FAIL{Colors.END}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
