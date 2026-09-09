"""自定义工作台组件异步 DAO。"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import UserWidget, WidgetDataPoint


async def list_widgets_by_user_async(db: AsyncSession, user_id: int) -> List[UserWidget]:
    result = await db.execute(
        select(UserWidget)
        .where(UserWidget.user_id == user_id)
        .order_by(UserWidget.sort_order.asc(), UserWidget.id.asc())
    )
    return list(result.scalars().all())


async def get_owned_widget_async(db: AsyncSession, user_id: int, widget_id: int) -> Optional[UserWidget]:
    result = await db.execute(
        select(UserWidget).where(UserWidget.id == widget_id, UserWidget.user_id == user_id)
    )
    return result.scalars().first()


async def due_widgets_async(db: AsyncSession, now: datetime, limit: int = 50) -> List[UserWidget]:
    """取到点该运行的组件：enabled 且 next_run_at <= now。按 next_run_at 升序。"""
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


async def claim_widget_async(
        db: AsyncSession,
        widget_id: int,
        expected_next_run_at: Optional[datetime],
        lease_until: datetime,
) -> bool:
    """乐观锁抢占：仅当 next_run_at 仍是我看到的值时，把它推到 lease_until。

    多个 Worker 同时跑时，只有抢到（rowcount==1）的那个才真正执行该组件，
    避免同一次到点被重复运行。runner 执行完会把 next_run_at 覆盖成真正的下次时间。
    """
    result = await db.execute(
        update(UserWidget)
        .where(
            UserWidget.id == widget_id,
            UserWidget.next_run_at == expected_next_run_at,
        )
        .values(next_run_at=lease_until)
    )
    return (result.rowcount or 0) == 1


async def next_sort_order_async(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(UserWidget.sort_order), -1)).where(UserWidget.user_id == user_id)
    )
    return int(result.scalar() or -1) + 1


async def create_widget_async(db: AsyncSession, user_id: int, fields: dict) -> UserWidget:
    widget = UserWidget(user_id=user_id, **fields)
    db.add(widget)
    await db.flush()
    await db.refresh(widget)
    return widget


async def update_widget_async(db: AsyncSession, widget: UserWidget, fields: dict) -> UserWidget:
    for key, value in fields.items():
        setattr(widget, key, value)
    await db.flush()
    await db.refresh(widget)
    return widget


async def delete_widget_async(db: AsyncSession, widget: UserWidget) -> None:
    await db.execute(delete(WidgetDataPoint).where(WidgetDataPoint.widget_id == widget.id))
    await db.delete(widget)
    await db.flush()


# ---------------------------------------------------------------------------
# 数据点
# ---------------------------------------------------------------------------

async def add_data_point_async(
        db: AsyncSession,
        widget_id: int,
        *,
        ok: int = 1,
        label: str = None,
        value: float = None,
        payload_json: str = None,
        error: str = None,
        duration_ms: int = None,
) -> WidgetDataPoint:
    point = WidgetDataPoint(
        widget_id=widget_id,
        ok=ok,
        label=label,
        value=value,
        payload_json=payload_json,
        error=error,
        duration_ms=duration_ms,
    )
    db.add(point)
    await db.flush()
    return point


async def list_data_points_async(db: AsyncSession, widget_id: int, limit: int = 60) -> List[WidgetDataPoint]:
    result = await db.execute(
        select(WidgetDataPoint)
        .where(WidgetDataPoint.widget_id == widget_id)
        .order_by(WidgetDataPoint.recorded_at.desc(), WidgetDataPoint.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def latest_data_point_async(db: AsyncSession, widget_id: int) -> Optional[WidgetDataPoint]:
    result = await db.execute(
        select(WidgetDataPoint)
        .where(WidgetDataPoint.widget_id == widget_id)
        .order_by(WidgetDataPoint.recorded_at.desc(), WidgetDataPoint.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def prune_data_points_async(db: AsyncSession, widget_id: int, keep: int) -> int:
    """只保留最近 keep 条数据点，返回删除条数。"""
    keep_ids_result = await db.execute(
        select(WidgetDataPoint.id)
        .where(WidgetDataPoint.widget_id == widget_id)
        .order_by(WidgetDataPoint.recorded_at.desc(), WidgetDataPoint.id.desc())
        .limit(keep)
    )
    keep_ids = [row[0] for row in keep_ids_result.all()]
    if not keep_ids:
        return 0
    deleted = await db.execute(
        delete(WidgetDataPoint).where(
            WidgetDataPoint.widget_id == widget_id,
            WidgetDataPoint.id.not_in(keep_ids),
        )
    )
    return deleted.rowcount or 0


async def apply_retention_async(
        db: AsyncSession,
        widget_id: int,
        *,
        now,
        keep_points: int,
        keep_days: int,
        keep_error_points: int,
) -> int:
    """按 service.widgets.retention 的完整保留策略裁剪数据点，返回删除条数。"""
    from service.widgets.retention import select_ids_to_delete

    rows = await db.execute(
        select(WidgetDataPoint.id, WidgetDataPoint.recorded_at, WidgetDataPoint.ok)
        .where(WidgetDataPoint.widget_id == widget_id)
    )
    points = [{"id": r[0], "recorded_at": r[1], "ok": r[2]} for r in rows.all()]
    to_delete = select_ids_to_delete(
        points,
        now=now,
        keep_points=keep_points,
        keep_days=keep_days,
        keep_error_points=keep_error_points,
    )
    if not to_delete:
        return 0
    deleted = await db.execute(
        delete(WidgetDataPoint).where(
            WidgetDataPoint.widget_id == widget_id,
            WidgetDataPoint.id.in_(list(to_delete)),
        )
    )
    return deleted.rowcount or 0
