"""组件定时调度入口。

到点的组件由后台 Worker 周期性调用 run_due_widgets() 批量运行；运维脚本 / 一次性
定时任务也可以调同一个函数。所有路径最终都走 runner.run_widget(widget_id)，与手动
运行完全一致。

多 Worker 安全：每个组件运行前先用乐观锁抢占（claim_widget_async 把 next_run_at 推到
一个租约时间），只有抢到的进程才执行，避免同一次到点被重复跑。runner 执行完会把
next_run_at 覆盖成真正的下次运行时间；如果进程在租约期内崩了，租约到期后会被重新捡起。

开关：WIDGET_SCHEDULER_ENABLED，默认开启（设成 0 / false 关闭）。
"""

import os
from datetime import datetime, timedelta
from typing import List

from utils.logger_handler import get_logger
from utils.timeutil import utcnow
from models import user_widget_async_dao as dao
from service.widgets.runner import run_widget

logger = get_logger("widget_scheduler")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def scheduler_enabled() -> bool:
    return os.getenv("WIDGET_SCHEDULER_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off", ""}


def _lease_minutes() -> int:
    return _env_int("WIDGET_SCHEDULER_LEASE_MINUTES", 10)


def _max_per_tick() -> int:
    return _env_int("WIDGET_SCHEDULER_MAX_PER_TICK", 50)


async def due_widgets(db, now: datetime = None, limit: int = None) -> List:
    """取到点该运行的组件（enabled 且 next_run_at <= now）。"""
    now = now or utcnow()
    return await dao.due_widgets_async(db, now, limit or _max_per_tick())


async def run_due_widgets(db, now: datetime = None, limit: int = None) -> dict:
    """运行所有到点组件，返回执行概况。每个组件抢占成功后单独提交，互不影响。"""
    now = now or utcnow()
    widgets = await due_widgets(db, now=now, limit=limit)
    lease_until = now + timedelta(minutes=_lease_minutes())

    due = len(widgets)
    ran = skipped = failed = 0

    for widget in widgets:
        widget_id = widget.id
        user_id = widget.user_id
        expected = widget.next_run_at
        try:
            won = await dao.claim_widget_async(db, widget_id, expected, lease_until)
            if not won:
                skipped += 1
                await db.rollback()
                continue
            result = await run_widget(db, user_id, widget_id, trigger="schedule")
            await db.commit()
            ran += 1
            if not result.ok:
                failed += 1
        except Exception as exc:  # noqa: BLE001 - 单个组件失败不影响其它
            failed += 1
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
            logger.warning(f"调度运行组件失败: widget_id={widget_id}, error={exc}")

    summary = {"due": due, "ran": ran, "skipped": skipped, "failed": failed}
    if due:
        logger.info(f"组件调度一轮: {summary}")
    return summary
