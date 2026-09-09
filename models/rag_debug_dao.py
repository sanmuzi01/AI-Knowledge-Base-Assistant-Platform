"""知识库调试台样例 DAO（异步为主，走 AsyncSession）。

只做数据访问，不含权限判断（权限在 service/rag/debug_service.py 走
access_control.user_space_ids / get_owned_space_async / get_owned_agent_async）。
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import RagDebugSample
from utils.timeutil import utcnow


async def create_sample_async(db: AsyncSession, user_id: int, fields: dict) -> RagDebugSample:
    sample = RagDebugSample(user_id=user_id, **fields)
    db.add(sample)
    await db.commit()
    await db.refresh(sample)
    return sample


async def get_owned_sample_async(db: AsyncSession, user_id: int, sample_id: int) -> Optional[RagDebugSample]:
    res = await db.execute(
        select(RagDebugSample).where(
            RagDebugSample.id == sample_id, RagDebugSample.user_id == user_id
        )
    )
    return res.scalars().first()


async def list_samples_async(
    db: AsyncSession,
    user_id: int,
    *,
    space_id: Optional[int] = None,
    agent_id: Optional[int] = None,
    eval_only: bool = False,
    limit: int = 200,
) -> List[RagDebugSample]:
    stmt = select(RagDebugSample).where(RagDebugSample.user_id == user_id)
    if space_id is not None:
        stmt = stmt.where(RagDebugSample.space_id == space_id)
    if agent_id is not None:
        stmt = stmt.where(RagDebugSample.agent_id == agent_id)
    if eval_only:
        stmt = stmt.where(RagDebugSample.in_eval_set == 1)
    res = await db.execute(stmt.order_by(RagDebugSample.id.desc()).limit(limit))
    return list(res.scalars().all())


async def update_sample_async(db: AsyncSession, sample: RagDebugSample, fields: dict) -> RagDebugSample:
    for k, v in fields.items():
        setattr(sample, k, v)
    sample.updated_at = utcnow()
    await db.commit()
    await db.refresh(sample)
    return sample


async def delete_sample_async(db: AsyncSession, sample: RagDebugSample) -> None:
    await db.delete(sample)
    await db.commit()
