"""组件定时调度入口（P1 预留 + 已实现 due 查询与批量运行）。

P1：不在 Worker 里默认开启循环。提供 run_due_widgets()，可被：
  - 后台 Worker（TASK 循环里加一行，受 WIDGET_SCHEDULER_ENABLED 控制）
  - 运维脚本 / 定时任务
调用。所有路径最终都走 runner.run_widget(widget_id)，与手动运行完全一致。
"""

import os
from datetime import datetime
from typing import List

from sqlalchemy import select

from utils.logger_handler import get_logger
from utils.timeutil import utcnow
from service.widgets.runner import run_widget

logger = get_logger("widget_scheduler")


def scheduler_enabled() -> bool:
    return os.getenv("WIDGET_SCHEDULER_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


async def due_widgets(db, now: datetime = None, limit: int = 50) -> List:
    """取到点该运行的组件（enabled 且 next_run_at <= now）。"""
    from models.init_db import UserWidget

    now = now or utcnow()
    result = await db.execute(
        select(UserWidget)
        .where(
            UserWidget.enabled == 1,
            UserWidget.next_run_at.is_not(None),
            UserWidget.next_run_at <= now,
        )
        .order_by(UserWidget.next_run_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def run_due_widgets(db, now: datetime = None, limit: int = 50) -> dict:
    """运行所有到点组件，返回执行概况。"""
    widgets = await due_widgets(db, now=now, limit=limit)
    ran, failed = 0, 0
    for widget in widgets:
        try:
            result = await run_widget(db, widget.user_id, widget.id, trigger="schedule")
            ran += 1
            failed += 0 if result.ok else 1
        except Exception as exc:  # noqa: BLE001 - 单个组件失败不影响其它
            failed += 1
            logger.warning(f"调度运行组件失败: widget_id={widget.id}, error={exc}")
    if widgets:
        await db.commit()
    return {"due": len(widgets), "ran": ran, "failed": failed}
