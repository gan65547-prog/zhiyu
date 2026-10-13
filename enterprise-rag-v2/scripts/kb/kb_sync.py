#!/usr/bin/env python3
"""
将仓库内的 Markdown/纯文本同步到 enterprise-rag-v2 指定数据集（通过现有上传 API）。

设计说明见：documents/design/项目开发资料与业务流程知识库及日志定位能力落地设计-v1.md（FR-06 / 第 7.4 节 / 第 10 章）

环境变量（推荐）：
  KB_SYNC_BASE_URL      API 根，如 https://rag.example.com
  KB_SYNC_TOKEN         Bearer JWT（需具备目标数据集上传权限）
  KB_SYNC_DATASET_ID    默认目标数据集 UUID（未命中映射时使用；仅单库时可只配此项）
  KB_SYNC_DATASET_MAP   可选，JSON：多路径前缀 -> 数据集，见下方格式
  KB_SYNC_REPO_ROOT     仓库根目录，默认当前工作目录
  KB_SYNC_ROOTS         逗号分隔的相对路径，默认 documents/kb
  KB_SYNC_PATHS_FILE    可选，文件内每行一个相对路径（# 开头为注释）
  KB_SYNC_MAX_RETRIES   可选，上传/列表/删除 HTTP 重试次数，默认 3
  RELEASE_VERSION       可选，写入 metadata
  GIT_COMMIT            可选，写入 metadata

KB_SYNC_DATASET_MAP 支持两种 JSON 形式（二选一）：
  1) 对象：键为「仓库相对路径前缀」，值为 dataset UUID（按前缀长度最长优先匹配）
     例：{"documents/kb/architecture/":"uuid-a","documents/kb/runbook/":"uuid-b"}
  2) 数组：{"prefix":"documents/kb/architecture/","dataset_id":"uuid-a"} 列表，同样按 prefix 长度最长优先

幂等策略：上传前按「规范文件名」在**目标数据集**内查找同名文档并批量删除（设计文档 7.4.2 之 S1）。
规范文件名：kb-sync__<相对路径中 / 替换为 __>，过长则用哈希缩短。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable, List, Sequence, Tuple

import httpx

DEFAULT_ROOTS = "documents/kb"
ALLOWED_SUFFIXES = {".md", ".txt", ".markdown"}
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return val.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def parse_dataset_map(raw: str | None) -> List[Tuple[str, str]]:
    """
    返回 [(prefix_posix, dataset_id), ...]，prefix 已规范为 posix 且不以 / 结尾时补全便于 startswith。
    按 prefix 长度降序排列（最长优先）。
    """
    if not raw or not raw.strip():
        return []
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"KB_SYNC_DATASET_MAP JSON 无效: {e}") from e

    pairs: List[Tuple[str, str]] = []

    if isinstance(data, dict):
        for k, v in data.items():
            if not k or not v:
                continue
            pairs.append((_normalize_prefix(str(k)), str(v).strip()))
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            p = item.get("prefix")
            did = item.get("dataset_id")
            if p and did:
                pairs.append((_normalize_prefix(str(p)), str(did).strip()))
    else:
        raise ValueError("KB_SYNC_DATASET_MAP 须为 JSON 对象或数组")

    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


def _normalize_prefix(p: str) -> str:
    p = p.replace("\\", "/").strip()
    if not p:
        return ""
    if p != "/" and not p.endswith("/"):
        p = p + "/"
    return p


def resolve_dataset_id(rel_posix: str, mapping: List[Tuple[str, str]], default_id: str | None) -> str:
    rel_norm = rel_posix.replace("\\", "/").lstrip("/")
    for prefix, did in mapping:
        p = prefix.rstrip("/")
        if not p:
            continue
        if rel_norm == p or rel_norm.startswith(p + "/"):
            return did
    if default_id:
        return default_id
    raise ValueError(
        f"路径未匹配 KB_SYNC_DATASET_MAP 且未设置 KB_SYNC_DATASET_ID: {rel_posix}"
    )


def canonical_upload_name(rel_posix: str) -> str:
    """生成稳定、可去重的上传文件名（不等于磁盘上的原名）。"""
    prefix = "kb-sync__" + rel_posix.replace("/", "__")
    if len(prefix) <= 200:
        return prefix
    digest = hashlib.sha256(rel_posix.encode("utf-8")).hexdigest()[:16]
    base = Path(rel_posix).name
    return f"kb-sync__{digest}__{base}"


def iter_files(
    repo_root: Path,
    roots: Sequence[str],
    paths_file: Path | None,
) -> List[Path]:
    files: List[Path] = []
    seen: set[str] = set()

    for root in roots:
        r = (repo_root / root.strip()).resolve()
        if not r.exists():
            print(f"[kb-sync] skip missing root: {r}", file=sys.stderr)
            continue
        if r.is_file():
            candidates = [r]
        else:
            candidates = sorted(p for p in r.rglob("*") if p.is_file())
        for p in candidates:
            if p.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            rel = p.resolve().relative_to(repo_root.resolve())
            key = rel.as_posix()
            if key in seen:
                continue
            seen.add(key)
            files.append(p)

    if paths_file and paths_file.is_file():
        for raw in paths_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            p = (repo_root / line).resolve()
            if not p.is_file():
                print(f"[kb-sync] skip missing file from list: {p}", file=sys.stderr)
                continue
            if p.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            rel = p.relative_to(repo_root.resolve())
            key = rel.as_posix()
            if key in seen:
                continue
            seen.add(key)
            files.append(p)

    files.sort(key=lambda x: x.as_posix())
    return files


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_retries: int,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            r = client.request(method, url, **kwargs)
            if r.status_code in RETRYABLE_STATUS and attempt < max_retries:
                wait = min(2**attempt, 30)
                time.sleep(wait)
                continue
            return r
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_exc = e
            if attempt >= max_retries:
                raise
            time.sleep(min(2**attempt, 30))
    assert last_exc is not None
    raise last_exc


def list_document_ids_by_name(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    upload_name: str,
    max_retries: int,
) -> List[str]:
    """分页扫描数据集中 file_name == upload_name 的文档，返回 id 列表。"""
    found: List[str] = []
    page = 1
    page_size = 100
    while True:
        url = f"{base_url.rstrip('/')}/api/v1/documents/datasets/{dataset_id}"
        r = _request_with_retry(
            client, "GET", url, max_retries=max_retries, params={"page": page, "page_size": page_size}
        )
        r.raise_for_status()
        body = r.json()
        data = body.get("data") or {}
        items = data.get("items") or []
        for it in items:
            if it.get("name") == upload_name:
                found.append(str(it["id"]))
        if len(items) < page_size:
            break
        page += 1
    return found


def delete_documents(
    client: httpx.Client, base_url: str, doc_ids: Iterable[str], max_retries: int
) -> None:
    ids = list(doc_ids)
    if not ids:
        return
    url = f"{base_url.rstrip('/')}/api/v1/documents/batch-delete"
    r = _request_with_retry(
        client, "POST", url, max_retries=max_retries, json={"document_ids": ids}
    )
    r.raise_for_status()


def upload_file(
    client: httpx.Client,
    base_url: str,
    dataset_id: str,
    upload_name: str,
    file_path: Path,
    metadata: dict,
    max_retries: int,
) -> None:
    url = f"{base_url.rstrip('/')}/api/v1/documents/datasets/{dataset_id}/"
    process_rule = json.dumps({"metadata": metadata}, ensure_ascii=False)
    with file_path.open("rb") as fh:
        files = {"file": (upload_name, fh, "application/octet-stream")}
        data = {"process_rule": process_rule}
        r = _request_with_retry(
            client, "POST", url, max_retries=max_retries, files=files, data=data
        )
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success", True):
        raise RuntimeError(f"Upload rejected: {payload}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync kb markdown/text into RAG dataset.")
    p.add_argument("--repo-root", default=_env("KB_SYNC_REPO_ROOT", "."), help="仓库根目录")
    p.add_argument("--base-url", default=_env("KB_SYNC_BASE_URL"), help="API Base URL")
    p.add_argument("--token", default=_env("KB_SYNC_TOKEN"), help="Bearer JWT")
    p.add_argument("--dataset-id", default=_env("KB_SYNC_DATASET_ID"), help="默认数据集 UUID")
    p.add_argument(
        "--dataset-map",
        default=_env("KB_SYNC_DATASET_MAP"),
        help="可选：JSON 字符串，路径前缀到 dataset_id 的映射",
    )
    p.add_argument(
        "--roots",
        default=_env("KB_SYNC_ROOTS", DEFAULT_ROOTS),
        help="逗号分隔相对路径，默认 documents/kb",
    )
    p.add_argument(
        "--paths-file",
        default=_env("KB_SYNC_PATHS_FILE"),
        help="可选：每行一个相对路径的补充列表文件",
    )
    p.add_argument("--dry-run", action="store_true", help="只打印将上传的文件，不调用 API")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    base_url = args.base_url
    token = args.token
    default_dataset_id = (args.dataset_id or "").strip() or None
    max_retries = _env_int("KB_SYNC_MAX_RETRIES", 3)

    try:
        mapping = parse_dataset_map(args.dataset_map)
    except ValueError as e:
        print(f"[kb-sync] {e}", file=sys.stderr)
        return 2

    if not base_url or not token:
        print("[kb-sync] KB_SYNC_BASE_URL、KB_SYNC_TOKEN 为必填", file=sys.stderr)
        return 2
    if not mapping and not default_dataset_id:
        print(
            "[kb-sync] 须配置 KB_SYNC_DATASET_ID，或提供 KB_SYNC_DATASET_MAP",
            file=sys.stderr,
        )
        return 2

    roots = [x.strip() for x in str(args.roots).split(",") if x.strip()]
    paths_file = Path(args.paths_file).resolve() if args.paths_file else None

    files = iter_files(repo_root, roots, paths_file)
    if not files:
        print("[kb-sync] no files to sync", file=sys.stderr)
        return 0

    release = _env("RELEASE_VERSION") or _env("GITHUB_REF_NAME")
    commit = _env("GIT_COMMIT") or _env("GITHUB_SHA")

    print(
        json.dumps(
            {
                "event": "kb_sync_start",
                "file_count": len(files),
                "dataset_map_entries": len(mapping),
                "default_dataset_id": default_dataset_id,
                "release_version": release,
                "git_commit": commit,
                "dry_run": args.dry_run,
                "max_retries": max_retries,
            },
            ensure_ascii=False,
        )
    )

    if args.dry_run:
        for fp in files:
            rel = fp.relative_to(repo_root).as_posix()
            did = resolve_dataset_id(rel, mapping, default_dataset_id)
            print(f"[dry-run] {rel} -> dataset={did} file={canonical_upload_name(rel)}")
        return 0

    timeout = httpx.Timeout(120.0, connect=30.0)
    with httpx.Client(timeout=timeout, headers=_headers(token)) as client:
        ok = 0
        for fp in files:
            rel = fp.relative_to(repo_root).as_posix()
            dataset_id = resolve_dataset_id(rel, mapping, default_dataset_id)
            upload_name = canonical_upload_name(rel)
            meta = {
                "kb_sync": True,
                "kb_source_path": rel,
                "source_commit": commit,
                "release_version": release,
            }
            dup_ids = list_document_ids_by_name(
                client, base_url, dataset_id, upload_name, max_retries
            )
            if dup_ids:
                delete_documents(client, base_url, dup_ids, max_retries)
            upload_file(
                client, base_url, dataset_id, upload_name, fp, meta, max_retries
            )
            ok += 1
            print(
                json.dumps(
                    {
                        "event": "kb_sync_file",
                        "path": rel,
                        "dataset_id": dataset_id,
                        "upload_name": upload_name,
                        "removed_duplicates": len(dup_ids),
                    },
                    ensure_ascii=False,
                )
            )

    print(
        json.dumps(
            {
                "event": "kb_sync_done",
                "uploaded": ok,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
