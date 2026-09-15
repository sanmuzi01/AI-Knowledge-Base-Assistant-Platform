"""后台任务异步 DAO。"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import BackgroundTask


async def get_task_by_id_async(db: AsyncSession, task_id: int) -> Optional[BackgroundTask]:
    result = await db.execute(select(BackgroundTask).where(BackgroundTask.id == task_id))
    return result.scalars().first()


async def get_owned_task_async(
        db: AsyncSession, user_id: int, task_id: int, agent_id: int = None,
) -> Optional[BackgroundTask]:
    conditions = [BackgroundTask.id == task_id, BackgroundTask.user_id == user_id]
    if agent_id is not None:
        conditions.append(BackgroundTask.agent_id == agent_id)
    result = await db.execute(select(BackgroundTask).where(*conditions))
    return result.scalars().first()


async def list_tasks_by_user_async(
        db: AsyncSession,
        user_id: int,
        limit: int = 30,
        status: str = None,
        task_type: str = None,
) -> List[BackgroundTask]:
    conditions = [BackgroundTask.user_id == user_id]
    if status:
        conditions.append(BackgroundTask.status == status)
    if task_type:
        conditions.append(BackgroundTask.task_type == task_type)
    result = await db.execute(
        select(BackgroundTask)
        .where(*conditions)
        .order_by(BackgroundTask.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _all_tasks_conditions(status: str = None, task_type: str = None) -> list:
    conditions = []
    if status:
        conditions.append(BackgroundTask.status == status)
    if task_type:
        conditions.append(BackgroundTask.task_type == task_type)
    return conditions


async def list_all_tasks_async(
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        status: str = None,
        task_type: str = None,
) -> List[BackgroundTask]:
    conditions = _all_tasks_conditions(status, task_type)
    statement = select(BackgroundTask).order_by(BackgroundTask.created_at.desc()).limit(limit).offset(offset)
    if conditions:
        statement = statement.where(*conditions)
    result = await db.execute(statement)
    return list(result.scalars().all())


async def count_all_tasks_async(
        db: AsyncSession, status: str = None, task_type: str = None,
) -> int:
    conditions = _all_tasks_conditions(status, task_type)
    statement = select(func.count(BackgroundTask.id))
    if conditions:
        statement = statement.where(*conditions)
    result = await db.execute(statement)
    return int(result.scalar() or 0)
