"""网页监控异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import WebMonitor


async def list_monitors_by_user_async(db: AsyncSession, user_id: int) -> List[WebMonitor]:
    result = await db.execute(
        select(WebMonitor)
        .where(WebMonitor.user_id == user_id)
        .order_by(WebMonitor.updated_at.desc(), WebMonitor.id.desc())
    )
    return list(result.scalars().all())


async def get_owned_monitor_async(db: AsyncSession, user_id: int, monitor_id: int) -> Optional[WebMonitor]:
    result = await db.execute(
        select(WebMonitor).where(WebMonitor.id == monitor_id, WebMonitor.user_id == user_id)
    )
    return result.scalars().first()


async def create_monitor_async(
        db: AsyncSession,
        user_id: int,
        name: str,
        url: str,
        interval_minutes: int,
        agent_id: int = None,
) -> WebMonitor:
    monitor = WebMonitor(
        user_id=user_id,
        agent_id=agent_id,
        name=name,
        url=url,
        interval_minutes=interval_minutes,
    )
    db.add(monitor)
    await db.flush()
    await db.refresh(monitor)
    return monitor
