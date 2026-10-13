#!/usr/bin/env python3.12
"""
知识库健康检查脚本

检查项:
  1. 断链检测 — related_pages 指向不存在的文档
  2. 溯源有效性 — source_files 路径是否存在
  3. 勘误统计 — 按严重程度/状态分组
  4. 知识分层统计 — 按 knowledge_type 统计文档数
  5. 过期检测 — 超过 N 个月未更新的文档

用法:
  python3.12 scripts/kb/lint_knowledge_base.py              # 检查 wiki 源文件
  python3.12 scripts/kb/lint_knowledge_base.py --api        # 通过 ganfy API 检查
  python3.12 scripts/kb/lint_knowledge_base.py --stale 6    # 标记 6 个月以上的过期内容
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

import frontmatter

ROOT = Path(__file__).parent.parent.parent.resolve()
WIKI_ROOT = Path("/Volumes/TOSHIBA/workerexp/wiki")
RAW_ROOT = Path("/Volumes/TOSHIBA/workerexp")

BASE_URL = os.getenv("GANFY_BASE_URL", "http://localhost:8000")


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def parse_wiki_pages() -> list[dict]:
    """解析所有 wiki 页面"""
    pages = []
    for type_dir in ["topics", "concepts", "summaries", "recipes"]:
        dir_path = WIKI_ROOT / type_dir
        if not dir_path.is_dir():
            continue
        for md_file in sorted(dir_path.glob("*.md")):
            try:
                post = frontmatter.load(str(md_file))
            except Exception:
                continue
            title = post.get("title", md_file.stem)
            tags = post.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            related = post.get("related", [])
            if isinstance(related, str):
                related = [r.strip() for r in related.split(",")]
            sources = post.get("sources", [])
            if isinstance(sources, str):
                sources = [s.strip() for s in sources.split(",")]

            pages.append({
                "title": title,
                "wiki_type": post.get("type", ""),
                "tags": tags,
                "related": related,
                "sources": sources,
                "date": str(post.get("date", "")),
                "source_file": str(md_file.relative_to(WIKI_ROOT)),
                "absolute_path": str(md_file),
            })
    return pages


def check_broken_links(pages: list[dict]) -> list[dict]:
    """检测 related 指向不存在的页面"""
    all_files = {p["source_file"] for p in pages}
    all_titles = {p["title"] for p in pages}
    # Also map title → file for suggestions
    name_to_file = {}
    for p in pages:
        name_to_file[p["title"]] = p["source_file"]
        stem = Path(p["source_file"]).stem
        name_to_file[stem] = p["source_file"]

    issues = []
    for p in pages:
        for ref in p["related"]:
            is_broken = True
            suggestion = ""

            # Try exact title match
            if ref in name_to_file:
                is_broken = False
            # Try stem match
            elif ref.replace("-", " ") in name_to_file:
                is_broken = False
            # Try as file path
            elif any(ref in f or f.endswith(ref + ".md") for f in all_files):
                is_broken = False

            if is_broken:
                # Find closest match
                closest = _find_closest(ref, list(name_to_file.keys()))
                suggestion = name_to_file[closest] if closest else ""
                issues.append({
                    "source": p["source_file"],
                    "bad_link": ref,
                    "suggestion": suggestion,
                })

    return issues


def check_source_validity(pages: list[dict]) -> list[dict]:
    """检测 source 指向的原始文件是否存在"""
    issues = []
    for p in pages:
        for src in p["sources"]:
            full_path = RAW_ROOT / src
            if not full_path.exists():
                issues.append({
                    "source": p["source_file"],
                    "missing_source": src,
                    "expected_path": str(full_path),
                })
    return issues


def check_stale_content(pages: list[dict], months: int = 6) -> list[dict]:
    """检测超过 N 个月未更新的文档"""
    cutoff = datetime.now() - timedelta(days=months * 30)
    stale = []
    for p in pages:
        date_str = p.get("date", "")
        if not date_str:
            stale.append({**p, "reason": "无更新日期"})
            continue
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            if dt < cutoff:
                stale.append({
                    "source_file": p["source_file"],
                    "title": p["title"],
                    "last_updated": date_str[:10],
                    "months_old": round((datetime.now() - dt).days / 30, 1),
                })
        except ValueError:
            stale.append({
                "source_file": p["source_file"],
                "title": p["title"],
                "reason": f"日期格式异常: {date_str}",
            })
    return stale


def check_known_errata() -> dict:
    """读取已知勘误文件统计"""
    errata_file = WIKI_ROOT / "concepts" / "known-errata.md"
    if not errata_file.exists():
        return {"error": "known-errata.md not found"}

    content = errata_file.read_text(encoding="utf-8")
    stats = {"total": 0, "by_severity": defaultdict(int), "entries": []}

    # Parse errata table: | ID | 页面 | 严重度 | 描述 | 状态 |
    import re
    for match in re.finditer(
        r'\|\s*(E-\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]*)\s*\|',
        content,
    ):
        code = match.group(1).strip()
        page = match.group(2).strip().strip('`')
        severity = match.group(3).strip()
        desc = match.group(4).strip()
        status = match.group(5).strip()
        stats["total"] += 1
        stats["by_severity"][severity] += 1
        stats["entries"].append({
            "code": code,
            "page": page,
            "severity": severity,
            "status": status,
            "description": desc[:100],
        })

    return dict(stats)


def statistics(pages: list[dict]) -> dict:
    """统计知识库概况"""
    by_type = defaultdict(int)
    by_tag = defaultdict(int)
    by_date = defaultdict(int)

    for p in pages:
        by_type[p["wiki_type"]] += 1
        for tag in p["tags"]:
            by_tag[tag] += 1
        date = p.get("date", "")[:7]  # YYYY-MM
        if date:
            by_date[date] += 1

    return {
        "total_pages": len(pages),
        "by_type": dict(by_type),
        "by_tag": dict(sorted(by_tag.items(), key=lambda x: -x[1])[:15]),
        "by_month": dict(sorted(by_date.items())),
        "avg_related_links": round(
            sum(len(p["related"]) for p in pages) / max(len(pages), 1), 1
        ),
        "avg_sources": round(
            sum(len(p["sources"]) for p in pages) / max(len(pages), 1), 1
        ),
    }


def check_api_mode(base_url: str) -> dict:
    """通过 ganfy API 检查已导入文档的健康状态"""
    import requests

    results = {
        "connected": False,
        "by_knowledge_type": {},
        "total_documents": 0,
        "errata_count": 0,
        "errors": [],
    }

    try:
        # Login
        username = os.getenv("GANFY_USERNAME", "admin")
        password = os.getenv("GANFY_PASSWORD", "admin123")
        r = requests.post(
            f"{base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code != 200:
            results["errors"].append(f"Login failed: HTTP {r.status_code}")
            return results

        token = r.json().get("data", {}).get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}
        results["connected"] = True

        # List datasets
        r = requests.get(
            f"{base_url}/api/v1/datasets/",
            headers=headers,
            params={"page_size": 50},
            timeout=10,
        )
        datasets = r.json().get("data", {}).get("items", []) if r.status_code == 200 else []

        # Per dataset: count by knowledge_type
        for ds in datasets:
            ds_name = ds.get("name", "")
            ds_id = ds.get("id", "")
            for kt in ["topic", "concept", "summary", "recipe"]:
                r = requests.get(
                    f"{base_url}/api/v1/documents/",
                    headers=headers,
                    params={
                        "dataset_id": ds_id,
                        "knowledge_type": kt,
                        "page_size": 1,
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    total = r.json().get("data", {}).get("total", 0)
                    if total > 0:
                        results["by_knowledge_type"][kt] = (
                            results["by_knowledge_type"].get(kt, 0) + total
                        )

        # Count total
        results["total_documents"] = sum(results["by_knowledge_type"].values())

        # Count errata
        try:
            r = requests.get(
                f"{base_url}/api/v1/errata/",
                headers=headers,
                params={"page_size": 1},
                timeout=10,
            )
            if r.status_code == 200:
                results["errata_count"] = r.json().get("data", {}).get("total", 0)
        except Exception:
            pass

    except requests.ConnectionError:
        results["errors"].append(f"Cannot connect to {base_url}")
    except Exception as e:
        results["errors"].append(str(e))

    return results


def _find_closest(target: str, candidates: list[str]) -> Optional[str]:
    """在候选中找最相似的项"""
    if not candidates:
        return None
    target_lower = target.lower().replace("-", " ").replace("_", " ")
    best, best_score = None, 0
    for c in candidates:
        c_lower = c.lower().replace("-", " ").replace("_", " ")
        score = _jaccard_sim(target_lower, c_lower)
        if score > best_score:
            best_score = score
            best = c
    return best if best_score > 0.15 else None


def _jaccard_sim(a: str, b: str) -> float:
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def print_section(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")


def main():
    import argparse
    p = argparse.ArgumentParser(description="知识库健康检查")
    p.add_argument("--api", action="store_true", help="通过 ganfy API 检查")
    p.add_argument("--stale", type=int, default=0, metavar="MONTHS",
                   help="检测超过 N 个月的过期文档")
    p.add_argument("--base-url", default=BASE_URL)
    args = p.parse_args()

    if args.api:
        print_section("ganfy API 知识库健康检查")
        result = check_api_mode(args.base_url)
        print(f"  连接状态: {'✓' if result['connected'] else '✗'} {args.base_url}")
        if result["errors"]:
            for e in result["errors"]:
                print(f"  {Colors.RED}错误: {e}{Colors.END}")
        print(f"  总文档数: {result['total_documents']}")
        print(f"  勘误条数: {result['errata_count']}")
        print(f"\n  按知识分层:")
        for kt, count in sorted(result["by_knowledge_type"].items()):
            print(f"    {kt:12s}: {count} 篇")
        return 0 if not result["errors"] else 1

    # File-system mode
    print_section("Wiki 知识库健康检查")
    print(f"  检查路径: {WIKI_ROOT}")

    pages = parse_wiki_pages()
    if not pages:
        print(f"  {Colors.RED}未找到 wiki 页面{Colors.END}")
        return 1

    # 1. Statistics
    stats = statistics(pages)
    print(f"\n{Colors.BOLD}── 1. 知识库概况 ──{Colors.END}")
    print(f"  总页面: {stats['total_pages']}")
    print(f"  平均关联链接: {stats['avg_related_links']} /页")
    print(f"  平均溯源引用: {stats['avg_sources']} /页")
    print(f"\n  按类型:")
    for kt, count in sorted(stats["by_type"].items()):
        print(f"    {kt:12s}: {count:3d} 篇")

    print(f"\n  Top 标签:")
    for tag, count in list(stats["by_tag"].items())[:10]:
        print(f"    {tag:20s}: {count}")

    # 2. Broken links
    print(f"\n{Colors.BOLD}── 2. 断链检测 ──{Colors.END}")
    broken = check_broken_links(pages)
    if broken:
        print(f"  {Colors.RED}发现 {len(broken)} 条断链:{Colors.END}")
        for issue in broken:
            sug = f" → 建议: {issue['suggestion']}" if issue["suggestion"] else ""
            print(f"    [{issue['source']}] {Colors.YELLOW}{issue['bad_link']}{Colors.END}{sug}")
    else:
        print(f"  {Colors.GREEN}未发现断链{Colors.END}")

    # 3. Source validity
    print(f"\n{Colors.BOLD}── 3. 溯源有效性 ──{Colors.END}")
    src_issues = check_source_validity(pages)
    if src_issues:
        print(f"  {Colors.RED}发现 {len(src_issues)} 条失效溯源:{Colors.END}")
        for issue in src_issues:
            print(f"    [{issue['source']}] → {issue['missing_source']}")
            print(f"      期望路径: {issue['expected_path']}")
    else:
        print(f"  {Colors.GREEN}溯源路径均有效{Colors.END}")

    # 4. Errata
    print(f"\n{Colors.BOLD}── 4. 勘误统计 ──{Colors.END}")
    errata_stats = check_known_errata()
    if "error" in errata_stats:
        print(f"  {Colors.YELLOW}{errata_stats['error']}{Colors.END}")
    else:
        print(f"  总计: {errata_stats['total']} 条")
        for sev, count in sorted(errata_stats["by_severity"].items()):
            icon = "🔴" if sev == "高" else "🟡" if sev == "中" else "🟢"
            print(f"    {icon} {sev}: {count} 条")
        for entry in errata_stats["entries"]:
            print(f"    [{entry['code']}] {entry['page']} | {entry['severity']} | {entry['status']}: {entry['description']}")

    # 5. Stale content
    if args.stale > 0:
        print(f"\n{Colors.BOLD}── 5. 过期检测 (> {args.stale} 个月) ──{Colors.END}")
        stale = check_stale_content(pages, args.stale)
        if stale:
            print(f"  {Colors.YELLOW}发现 {len(stale)} 篇可能过期的文档:{Colors.END}")
            for s in stale:
                title = s.get("title", s.get("source_file", "?"))
                months = s.get("months_old", "?")
                reason = s.get("reason", "")
                print(f"    {title} — {months} 个月前更新" + (f" ({reason})" if reason else ""))
        else:
            print(f"  {Colors.GREEN}所有文档均在 {args.stale} 个月内更新{Colors.END}")

    # Summary
    total_issues = len(broken) + len(src_issues)
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    if total_issues == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}  知识库健康状态: 良好{Colors.END}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}  知识库健康状态: {total_issues} 个问题需处理{Colors.END}")
        print(f"    断链: {len(broken)} | 失效溯源: {len(src_issues)}")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
