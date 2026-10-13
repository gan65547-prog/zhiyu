#!/usr/bin/env python3.12
"""
将 workerexp/wiki 结构化知识导入 ganfy RAG 平台

保留 wiki 的全部元数据:
  - frontmatter (type, tags, related, sources, date)
  - recipe 特有字段 (difficulty, estimated_time, verified_on_board, last_verified)
  - [[wikilinks]] 保持原文可搜索
  - 按 wiki type 分 dataset 组织

用法:
  python3.12 scripts/import_wiki_to_ganfy.py --dry-run          # 只解析展示
  python3.12 scripts/import_wiki_to_ganfy.py --type recipes     # 只导入 recipes
  python3.12 scripts/import_wiki_to_ganfy.py --all              # 全量导入
  python3.12 scripts/import_wiki_to_ganfy.py --all --skip-existing  # 跳过已存在的

环境变量:
  GANFY_BASE_URL  默认 http://localhost:8000
  GANFY_USERNAME  默认 admin
  GANFY_PASSWORD  默认 admin123
"""

from __future__ import annotations

import json
import os
import sys
import time
import hashlib
from pathlib import Path
from typing import Optional

import frontmatter
import requests

ROOT = Path(__file__).parent.parent.resolve()
WIKI_ROOT = Path("/Volumes/TOSHIBA/workerexp/wiki")

BASE_URL = os.getenv("GANFY_BASE_URL", "http://localhost:8000")
USERNAME = os.getenv("GANFY_USERNAME", "admin")
PASSWORD = os.getenv("GANFY_PASSWORD", "admin123")
LOGIN_EMAIL = os.getenv("GANFY_EMAIL", "admin@example.com")

DATASET_MAP = {
    "topic":   "领域全景",
    "concept": "深度概念",
    "summary": "项目复盘",
    "recipe":  "工程食谱",
}

IMPORT_PRIORITY = ["recipe", "summary", "concept", "topic"]


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def parse_wiki_pages() -> list[dict]:
    """解析所有 wiki 页面，返回结构化数据列表"""
    pages = []
    for type_dir_name, wiki_type in [
        ("topics", "topic"),
        ("concepts", "concept"),
        ("summaries", "summary"),
        ("recipes", "recipe"),
    ]:
        dir_path = WIKI_ROOT / type_dir_name
        if not dir_path.is_dir():
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            try:
                post = frontmatter.load(str(md_file))
            except Exception as e:
                print(f"  {Colors.RED}Parse error: {md_file.name}: {e}{Colors.END}")
                continue

            title = post.get("title", md_file.stem)
            tags = post.get("tags", [])
            # 确保 tags 是 list
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            related = post.get("related", [])
            if isinstance(related, str):
                related = [r.strip() for r in related.split(",") if r.strip()]

            sources = post.get("sources", [])
            if isinstance(sources, str):
                sources = [s.strip() for s in sources.split(",") if s.strip()]

            page = {
                "title": title,
                "wiki_type": wiki_type,
                "tags": tags,
                "related": related,
                "sources": sources,
                "date": str(post.get("date", "")),
                "content": post.content,
                "source_file": str(md_file.relative_to(WIKI_ROOT)),
                "content_hash": hashlib.sha256(
                    post.content.encode("utf-8")
                ).hexdigest()[:12],
            }

            # recipe 特有字段
            if wiki_type == "recipe":
                page["difficulty"] = post.get("difficulty", "")
                page["estimated_time"] = post.get("estimated_time", "")
                page["verified_on_board"] = post.get("verified_on_board", False)
                page["last_verified"] = str(post.get("last_verified", ""))

            pages.append(page)

    return pages


def _get_csrf_token(session: requests.Session, base_url: str) -> Optional[str]:
    """通过 GET 请求获取 CSRF token（Double Submit Cookie 模式）"""
    try:
        # 使用非豁免路径以触发 CSRF token 生成
        r = session.get(f"{base_url}/api/v1/datasets/", timeout=10)
        # 优先从响应头获取，其次从 cookie 获取
        token = r.headers.get("X-CSRF-Token")
        if not token:
            for cookie in session.cookies:
                if cookie.name == "csrf_token":
                    token = cookie.value
                    break
        return token
    except Exception:
        return None


def login(base_url: str) -> Optional[tuple[str, requests.Session]]:
    """登录获取 access_token 和带有 CSRF 支持的 session"""
    session = requests.Session()

    # 先获取 CSRF token
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
            # 登录后重新获取 CSRF token（session 可能变更）
            new_csrf = _get_csrf_token(session, base_url)
            if new_csrf:
                csrf_token = new_csrf
            return token, session, csrf_token
    except Exception as e:
        print(f"  {Colors.RED}Login failed: {e}{Colors.END}")
    return None, None, None


def _make_headers(token: str, csrf_token: Optional[str]) -> dict:
    """构建请求头"""
    h = {"Authorization": f"Bearer {token}"}
    if csrf_token:
        h["X-CSRF-Token"] = csrf_token
    return h


def get_or_create_dataset(
    base_url: str, session: requests.Session, token: str,
    csrf_token: Optional[str], wiki_type: str,
) -> Optional[str]:
    """获取或创建对应 wiki 类型的数据集，返回 dataset_id"""
    dataset_name = DATASET_MAP[wiki_type]
    headers = _make_headers(token, csrf_token)

    # 先查找是否已存在
    try:
        r = session.get(
            f"{base_url}/api/v1/datasets/",
            headers=headers,
            params={"keyword": dataset_name, "page_size": 50},
            timeout=10,
        )
        if r.status_code == 200:
            items = r.json().get("data", {}).get("items", [])
            for ds in items:
                if ds.get("name") == dataset_name:
                    return ds["id"]
    except Exception:
        pass

    # 不存在则创建
    try:
        r = session.post(
            f"{base_url}/api/v1/datasets/",
            headers=headers,
            json={
                "name": dataset_name,
                "description": f"Wiki 知识库 - {dataset_name}（来自 workerexp/wiki）",
                "chunk_size": 800 if wiki_type == "concept" else 500,
                "chunk_overlap": 100 if wiki_type == "concept" else 50,
            },
            timeout=10,
        )
        if r.status_code in (200, 201):
            ds_id = r.json().get("data", {}).get("id")
            if ds_id:
                print(f"  {Colors.GREEN}Created dataset '{dataset_name}' → {ds_id}{Colors.END}")
                return ds_id
        else:
            print(f"  {Colors.RED}Create dataset failed: HTTP {r.status_code}: {r.text[:200]}{Colors.END}")
    except Exception as e:
        print(f"  {Colors.RED}Create dataset failed: {e}{Colors.END}")

    return None


def build_metadata(page: dict) -> dict:
    """将 wiki frontmatter 编码为 ganfy 文档 metadata"""
    meta = {
        "wiki_type": page["wiki_type"],
        "wiki_title": page["title"],
        "wiki_date": page["date"],
        "wiki_source_file": page["source_file"],
        "wiki_related": page["related"],
        "wiki_sources": page["sources"],
    }
    if page["wiki_type"] == "recipe":
        meta.update({
            "difficulty": page.get("difficulty", ""),
            "estimated_time": page.get("estimated_time", ""),
            "verified_on_board": page.get("verified_on_board", False),
            "last_verified": str(page.get("last_verified", "")),
        })
    return meta


def upload_page(
    base_url: str, session: requests.Session, token: str,
    csrf_token: Optional[str], dataset_id: str, page: dict,
    skip_existing: bool = False,
) -> tuple[bool, str]:
    """上传单个 wiki 页面到指定数据集"""
    import tempfile

    file_name = Path(page["source_file"]).name

    # 构建 tags: 合并 wiki_type + 页面 tags
    all_tags = [page["wiki_type"]] + page["tags"]

    metadata = build_metadata(page)
    process_rule = json.dumps({
        "tags": all_tags,
        "metadata": metadata,
        "knowledge_type": page["wiki_type"],
    })

    headers = _make_headers(token, csrf_token)

    # 写入临时文件
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

    # 等待处理完成
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
                    cc = d.get("chunk_count", 0)
                    return True, f"doc_id={doc_id}, {cc} chunks"
                elif st == "failed":
                    return False, f"processing failed: {d.get('error_message', '')}"
            time.sleep(1)
        except Exception:
            time.sleep(2)

    return False, f"processing timeout (doc_id={doc_id})"


def print_page_summary(pages: list[dict]) -> None:
    """Dry-run: 展示解析结果"""
    by_type = {}
    for p in pages:
        by_type.setdefault(p["wiki_type"], []).append(p)

    for wtype in IMPORT_PRIORITY:
        items = by_type.get(wtype, [])
        if not items:
            continue
        print(f"\n{Colors.BOLD}{Colors.CYAN}── {DATASET_MAP[wtype]} ({wtype}) ──{Colors.END}")
        for i, p in enumerate(items, 1):
            content_preview = p["content"][:80].replace("\n", " ")
            print(f"  {i:2d}. {Colors.BOLD}{p['title']}{Colors.END}")
            print(f"      file: {p['source_file']}  |  date: {p['date']}")
            print(f"      tags: {p['tags']}")
            if p["related"]:
                print(f"      related: {p['related']}")
            if p["sources"]:
                print(f"      sources: {len(p['sources'])} files")
            print(f"      preview: {content_preview}...")
            if p["wiki_type"] == "recipe":
                extra = []
                if p.get("difficulty"):
                    extra.append(f"difficulty={p['difficulty']}")
                if p.get("estimated_time"):
                    extra.append(f"time={p['estimated_time']}")
                if p.get("verified_on_board"):
                    extra.append("board-verified")
                if extra:
                    print(f"      recipe-meta: {', '.join(extra)}")


def main():
    import argparse

    p = argparse.ArgumentParser(
        description="将 workerexp/wiki 结构化知识导入 ganfy RAG 平台",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="只解析展示，不上传")
    p.add_argument("--type", choices=["topic", "concept", "summary", "recipe"],
                   help="只导入指定类型")
    p.add_argument("--all", action="store_true",
                   help="导入全部类型（按优先级: recipe → summary → concept → topic）")
    p.add_argument("--skip-existing", action="store_true",
                   help="跳过已存在的文档（默认覆盖）")
    p.add_argument("--base-url", default=BASE_URL,
                   help=f"ganfy API 地址 (默认: {BASE_URL})")
    args = p.parse_args()

    print(f"{Colors.BOLD}{Colors.CYAN}Wiki → ganfy 知识导入工具{Colors.END}")
    print(f"  Wiki 源: {WIKI_ROOT}")

    # 解析 wiki
    pages = parse_wiki_pages()
    if not pages:
        print(f"{Colors.RED}No wiki pages found in {WIKI_ROOT}{Colors.END}")
        return 1

    print(f"  解析到 {len(pages)} 个页面")

    if args.dry_run:
        print_page_summary(pages)
        return 0

    # 确定要导入的类型
    if args.type:
        target_types = [args.type]
    elif args.all:
        target_types = IMPORT_PRIORITY
    else:
        print(f"{Colors.YELLOW}请指定 --all 或 --type <type> 或 --dry-run{Colors.END}")
        return 1

    # API 导入
    print(f"\n{Colors.BOLD}连接 ganfy: {args.base_url}{Colors.END}")
    token, session, csrf_token = login(args.base_url)
    if not token:
        print(f"{Colors.RED}登录失败，请确认后端已启动且账号密码正确{Colors.END}")
        return 1

    total_ok, total_fail = 0, 0

    for wtype in target_types:
        type_pages = [pg for pg in pages if pg["wiki_type"] == wtype]
        if not type_pages:
            print(f"\n{Colors.YELLOW}  {DATASET_MAP[wtype]}: 无页面{Colors.END}")
            continue

        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}  {DATASET_MAP[wtype]} ({wtype}) — {len(type_pages)} 页{Colors.END}")

        dataset_id = get_or_create_dataset(args.base_url, session, token, csrf_token, wtype)
        if not dataset_id:
            print(f"  {Colors.RED}无法创建/获取数据集{Colors.END}")
            total_fail += len(type_pages)
            continue

        for i, page in enumerate(type_pages, 1):
            name = page["title"]
            print(f"  [{i}/{len(type_pages)}] {name} ...", end=" ", flush=True)
            ok, detail = upload_page(
                args.base_url, session, token, csrf_token, dataset_id, page, args.skip_existing,
            )
            if ok:
                print(f"{Colors.GREEN}OK{Colors.END} ({detail})")
                total_ok += 1
            else:
                print(f"{Colors.RED}FAIL{Colors.END} ({detail})")
                total_fail += 1

    # 汇总
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}  导入完成: {Colors.GREEN}{total_ok} 成功{Colors.END}"
          f"{Colors.BOLD}, {Colors.RED}{total_fail} 失败{Colors.END}")
    print(f"{Colors.BOLD}  总计: {total_ok + total_fail}{Colors.END}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
