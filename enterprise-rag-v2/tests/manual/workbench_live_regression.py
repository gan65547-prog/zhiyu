#!/usr/bin/env python3
"""Repeatable live regression for the local workbench APIs.

Run with the API and a worker already started, for example:
  GANFY_E2E_EMAIL=... GANFY_E2E_PASSWORD=... python tests/manual/workbench_live_regression.py

The local worker must consume ``celery,documents_high,chat_async`` so that
document, research, metric-sync and asynchronous chat checks use the same
runtime configuration.

The script intentionally creates uniquely named records and only uses local,
deterministic inputs. It is a business-flow smoke test, not a replacement for
browser-level visual regression.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests


BASE_URL = os.getenv("GANFY_E2E_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.getenv("GANFY_E2E_EMAIL")
PASSWORD = os.getenv("GANFY_E2E_PASSWORD")
# The first local worker run may load the embedding model from disk/cache.
# Keep the default long enough for a cold-start regression; CI can override it.
MAX_WAIT = int(os.getenv("GANFY_E2E_MAX_WAIT", "900"))
PREFIX = f"Codex回归-{int(time.time())}"


class LiveRegression:
    def __init__(self) -> None:
        self.http = requests.Session()
        # 本地回归必须直连 GANFY_E2E_BASE_URL；开发机的系统代理可能把
        # 127.0.0.1 请求转发到代理隧道，导致异步轮询无法观察真实服务状态。
        self.http.trust_env = False
        self.checks: list[tuple[str, str]] = []
        self.workspace_id = ""
        self.dataset_id = ""
        self._refreshing_auth = False

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.http.request(method, f"{BASE_URL}{path}", timeout=30, **kwargs)
        if (
            response.status_code == 401
            and EMAIL
            and PASSWORD
            and not self._refreshing_auth
            and path != "/api/v1/auth/login"
        ):
            self._refreshing_auth = True
            try:
                self.login()
            finally:
                self._refreshing_auth = False
            response = self.http.request(method, f"{BASE_URL}{path}", timeout=30, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:300]}")
        if not response.content:
            return None
        return response.json()

    @staticmethod
    def data(value: Any) -> Any:
        if isinstance(value, dict) and "data" in value:
            return value["data"]
        return value

    def check(self, name: str, fn) -> Any:
        try:
            result = fn()
            self.checks.append(("PASS", name))
            return result
        except Exception as exc:  # noqa: BLE001 - report every failed flow and continue
            self.checks.append(("FAIL", f"{name}: {exc}"))
            return None

    def login(self) -> None:
        if not EMAIL or not PASSWORD:
            raise RuntimeError("请设置 GANFY_E2E_EMAIL 和 GANFY_E2E_PASSWORD")
        login_result = self.data(self.request("POST", "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}))
        access_token = login_result.get("access_token") if isinstance(login_result, dict) else None
        if access_token:
            self.http.headers.update({"Authorization": f"Bearer {access_token}"})
        self.request("GET", "/api/v1/workspaces/")
        csrf = self.http.cookies.get("csrf_token")
        if csrf:
            self.http.headers.update({"x-csrf-token": csrf})

    def wait_for(self, fn, label: str) -> Any:
        deadline = time.time() + MAX_WAIT
        last: Any = None
        while time.time() < deadline:
            last = fn()
            status = str(last.get("status", "")) if isinstance(last, dict) else ""
            if status.lower() in {"ready", "completed", "success", "failed", "cancelled", "error"}:
                return last
            time.sleep(3)
        raise RuntimeError(f"{label} 超时，最后状态: {last}")

    def run(self) -> int:
        self.check("登录与工作区读取", self.login)
        if not self.http.cookies:
            return self.report()
        workspaces = self.data(self.request("GET", "/api/v1/workspaces/")) or []
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("items", [])
        self.workspace_id = workspaces[0]["id"]
        datasets = self.data(self.request("GET", "/api/v1/datasets/", params={"workspace_id": self.workspace_id})) or {}
        datasets = datasets.get("items", datasets) if isinstance(datasets, dict) else datasets
        if datasets:
            self.dataset_id = datasets[0]["id"]
        else:
            created_dataset = self.data(self.request("POST", "/api/v1/datasets/", json={
                "workspace_id": self.workspace_id,
                "name": f"{PREFIX}-知识库",
                "description": "live regression dataset",
            }))
            self.dataset_id = str(created_dataset["id"])

        asset = self.check("素材创建、文本解析与状态轮询", self.asset_flow)
        self.check("知识整理任务入队", lambda: self.request("POST", f"/api/v1/assets/{asset['id']}/organize") if asset else None)
        self.check("研究项目与运行创建", self.research_flow)
        self.check("研究运行取消与重试前状态", self.research_cancel_flow)
        self.check("Agent 无审批工具执行", self.agent_flow)
        self.check("内容选题、草稿、改写、审核与发布", self.content_flow)
        self.check("异步对话与消息落库", self.chat_flow)
        return self.report()

    def asset_flow(self) -> dict[str, Any]:
        asset = self.request("POST", "/api/v1/assets", json={
            "workspace_id": self.workspace_id,
            "dataset_id": self.dataset_id or None,
            "source_type": "text",
            "title": f"{PREFIX}-素材",
        })
        asset = self.data(asset)
        self.request("POST", f"/api/v1/assets/{asset['id']}/text", json={"content": "回归测试验证共享素材可解析并进入知识库。"})
        final_status = self.wait_for(lambda: self.data(self.request("GET", f"/api/v1/assets/{asset['id']}/processing-status")), "素材解析")
        if str(final_status.get("status", "")).lower() not in {"ready", "completed"} or not final_status.get("document_id"):
            raise RuntimeError(f"素材解析未形成可整理文档: {final_status}")
        return asset

    def research_flow(self) -> None:
        project = self.data(self.request("POST", "/api/v1/research/projects", json={
            "workspace_id": self.workspace_id, "name": f"{PREFIX}-研究", "description": "live regression",
            "questions": [{"question": "素材是否可以被检索？", "sort_order": 0}],
            "samples": [{"dataset_id": self.dataset_id}] if self.dataset_id else [],
        }))
        run = self.data(self.request("POST", f"/api/v1/research/projects/{project['id']}/runs", json={
            "limits": {"max_sources": 1, "max_source_bytes": 1024 * 1024, "max_output_tokens": 256},
        }))
        self.wait_for(lambda: self.data(self.request("GET", f"/api/v1/research/runs/{run['id']}")), "研究运行")

    def research_cancel_flow(self) -> None:
        project = self.data(self.request("POST", "/api/v1/research/projects", json={
            "workspace_id": self.workspace_id, "name": f"{PREFIX}-取消研究", "description": "cancel regression",
            # Keep the run cancellable long enough to exercise the cancellation
            # transition. An empty source set is a valid negative input, but
            # it is rejected immediately as `failed` before cancellation can
            # be observed.
            "questions": [{"question": "取消状态是否可追踪？", "sort_order": 0}],
            "samples": [{"dataset_id": self.dataset_id}] if self.dataset_id else [],
        }))
        run = self.data(self.request("POST", f"/api/v1/research/projects/{project['id']}/runs", json={
            "limits": {"max_sources": 1, "max_source_bytes": 1024, "max_output_tokens": 256},
        }))
        cancelled = self.data(self.request("POST", f"/api/v1/research/runs/{run['id']}/cancel"))
        if cancelled.get("status") != "cancelled":
            raise RuntimeError(f"研究取消未保持 cancelled 终态: {cancelled}")

    def agent_flow(self) -> None:
        tools = self.data(self.request("GET", "/api/v1/agents/tools")) or []
        tool = next(item for item in tools if item.get("key") == "extract_terms")
        definition = self.data(self.request("POST", "/api/v1/agents", json={
            "workspace_id": self.workspace_id, "name": f"{PREFIX}-Agent", "agent_type": "asset_organize",
            "workflow": [{"key": "extract", "label": "提取术语", "tool": tool["key"], "input": {"text": "回归测试术语"}}],
        }))
        run = self.data(self.request("POST", "/api/v1/agents/runs", json={
            "workspace_id": self.workspace_id, "definition_id": definition["id"], "input": {}, "config": {},
        }))
        result = self.data(self.request("POST", f"/api/v1/agents/runs/{run['id']}/steps/extract/execute", json={"input": {"text": "回归测试术语"}}))
        if result.get("status") not in {"completed", "success"}:
            raise RuntimeError(f"Agent 工具未成功执行: {result}")

    def content_flow(self) -> None:
        topic = self.data(self.request("POST", "/api/v1/content/topics", json={"workspace_id": self.workspace_id, "title": f"{PREFIX}-选题", "brief": "live regression"}))
        draft = self.data(self.request("POST", "/api/v1/content/drafts", json={"workspace_id": self.workspace_id, "topic_id": topic["id"], "title": f"{PREFIX}-草稿", "body": "这是用于验证内容生产链路的草稿。"}))
        self.request("POST", f"/api/v1/content/drafts/{draft['id']}/rewrite", json={"platforms": ["wechat", "website"], "mode": "deterministic"})
        self.request("POST", f"/api/v1/content/drafts/{draft['id']}/review", json={"status": "approved"})
        publish = self.data(self.request("POST", f"/api/v1/content/drafts/{draft['id']}/publish", json={"platform": "manual"}))
        if publish.get("status") != "ready":
            raise RuntimeError(f"人工发布必须进入待确认状态: {publish}")
        self.request("POST", f"/api/v1/content/publishes/{publish['id']}/confirm", json={"response": {"source": "manual-regression"}})
        self.request("POST", f"/api/v1/content/publishes/{publish['id']}/metrics", json={"impressions": 100, "clicks": 8, "likes": 12, "comments": 2, "shares": 1})
        imported = self.data(self.request("POST", "/api/v1/content/publishes/metrics/import", json={
            "workspace_id": self.workspace_id,
            "items": [{
                "publish_id": publish["id"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metric": {"impressions": 180, "clicks": 16, "likes": 20, "comments": 3, "shares": 2},
            }],
        }))
        if imported.get("inserted") != 1:
            raise RuntimeError(f"批量指标导入未写入: {imported}")
        sync = self.data(self.request("POST", "/api/v1/content/publishes/metrics/sync", json={
            "workspace_id": self.workspace_id,
            "platform": "manual",
            "items": [{
                "publish_id": publish["id"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metric": {"impressions": 220, "clicks": 18, "likes": 22, "comments": 3, "shares": 2},
            }],
        }))
        sync_result = self.wait_for(lambda: self.data(self.request("GET", f"/api/v1/content/publishes/metrics/sync/{sync['id']}")), "指标同步任务")
        if sync_result.get("status") != "completed" or sync_result.get("inserted") != 1:
            raise RuntimeError(f"指标同步任务未完成: {sync_result}")
        metric_response = self.data(self.request(
            "GET", "/api/v1/content/publishes/metrics", params={"workspace_id": self.workspace_id}
        )) or {}
        metric_items = metric_response.get("items", metric_response) if isinstance(metric_response, dict) else metric_response
        matching_metrics = [item for item in (metric_items or []) if str(item.get("publish_record_id")) == str(publish["id"])]
        if len(matching_metrics) < 2:
            raise RuntimeError(f"指标同步已完成，但指标列表未形成至少两条快照: {matching_metrics}")
        overview = self.data(self.request(
            "GET", "/api/v1/data-center/overview", params={"workspace_id": self.workspace_id}
        )) or {}
        performance = overview.get("content_performance", {}) if isinstance(overview, dict) else {}
        if int(performance.get("impressions", 0)) < 400 or int(performance.get("clicks", 0)) < 34:
            raise RuntimeError(f"指标已写入但数据中心汇总未更新: {performance}")
        self.request("POST", f"/api/v1/content/publishes/{publish['id']}/retrospective")

    def chat_flow(self) -> None:
        job = self.data(self.request("POST", "/api/v1/chat/async", json={"query": "回归测试", "dataset_id": self.dataset_id or None}))
        result = self.wait_for(lambda: self.data(self.request("GET", f"/api/v1/chat/jobs/{job['job_id']}")), "异步对话")
        if str(result.get("status", "")).lower() not in {"success", "completed"}:
            raise RuntimeError(f"对话任务未成功: {result}")

    def report(self) -> int:
        print(f"Live regression: {BASE_URL} / {PREFIX}")
        for status, name in self.checks:
            print(f"[{status}] {name}")
        failures = sum(status == "FAIL" for status, _ in self.checks)
        print(f"Summary: {len(self.checks) - failures} passed, {failures} failed")
        return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(LiveRegression().run())
