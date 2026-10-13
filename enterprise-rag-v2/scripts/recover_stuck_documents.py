#!/usr/bin/env python3
"""
回收长时间卡住的文档处理任务（status=PROCESSING）。

用法:
  .venv/bin/python scripts/recover_stuck_documents.py --minutes 30 --action pending
  .venv/bin/python scripts/recover_stuck_documents.py --minutes 60 --action failed
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import select

# 统一项目根路径，确保脚本可直接运行
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from infrastructure.database.models import Document, DocumentStatus
from infrastructure.database.session import AsyncSessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover stuck processing documents")
    parser.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="处理超时阈值（分钟），默认 30",
    )
    parser.add_argument(
        "--action",
        choices=("pending", "failed"),
        default="pending",
        help="回收动作：pending(重排队) 或 failed(标记失败)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="单次最多处理数量，默认 200",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    threshold = datetime.utcnow() - timedelta(minutes=args.minutes)
    to_status = DocumentStatus.PENDING if args.action == "pending" else DocumentStatus.FAILED

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document)
            .where(Document.status == DocumentStatus.PROCESSING)
            .where(Document.updated_at < threshold)
            .order_by(Document.updated_at.asc())
            .limit(args.limit)
        )
        docs = result.scalars().all()

        if not docs:
            print("没有发现需要回收的卡住任务。")
            return 0

        now_iso = datetime.utcnow().isoformat()
        for doc in docs:
            meta = doc.extra_metadata or {}
            processing = meta.get("processing", {}) or {}
            processing.update(
                {
                    "phase": "requeued" if to_status == DocumentStatus.PENDING else "failed",
                    "progress": 1 if to_status == DocumentStatus.PENDING else 0,
                    "updated_at": now_iso,
                    "recover_reason": f"stuck>{args.minutes}m",
                }
            )
            meta["processing"] = processing
            doc.extra_metadata = meta
            doc.status = to_status

        await session.commit()

        print(
            f"已回收 {len(docs)} 条任务: PROCESSING -> {to_status.value}, "
            f"阈值={args.minutes}分钟, limit={args.limit}"
        )
        for doc in docs[:20]:
            print(f"- {doc.id} | {doc.file_name} | updated_at={doc.updated_at}")
        if len(docs) > 20:
            print(f"... 其余 {len(docs) - 20} 条已省略")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
