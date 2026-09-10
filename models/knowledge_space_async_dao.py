"""知识库空间 异步 DAO（读为主，走 AsyncSession）。"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import AgentKnowledgeSpace, Knowledge, KnowledgeSpace, SpaceMember
from utils.timeutil import utcnow


async def get_owned_space_async(db: AsyncSession, user_id: int, space_id: int) -> Optional[KnowledgeSpace]:
    res = await db.execute(
        select(KnowledgeSpace).where(
            KnowledgeSpace.id == space_id, KnowledgeSpace.user_id == user_id
        )
    )
    return res.scalars().first()


async def get_space_by_id_async(db: AsyncSession, space_id: int) -> Optional[KnowledgeSpace]:
    res = await db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id == space_id))
    return res.scalars().first()


async def list_spaces_by_user_async(
    db: AsyncSession, user_id: int, include_archived: bool = True
) -> List[KnowledgeSpace]:
    stmt = select(KnowledgeSpace).where(KnowledgeSpace.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(KnowledgeSpace.status == "active")
    res = await db.execute(stmt.order_by(KnowledgeSpace.id.desc()))
    return list(res.scalars().all())


async def list_spaces_by_ids_async(db: AsyncSession, space_ids: List[int]) -> List[KnowledgeSpace]:
    """按 id 批量取空间（检索编排用，调用方需先做归属校验）。
    `knowledge_space_dao.list_spaces_by_ids` 的 async 版。"""
    ids = [int(s) for s in dict.fromkeys(space_ids or [])]
    if not ids:
        return []
    res = await db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id.in_(ids)))
    return list(res.scalars().all())


async def user_space_ids_async(db: AsyncSession, user_id: int) -> List[int]:
    """自己拥有的 space id（成员空间由 access_control.user_space_ids_async 合并进来）。"""
    res = await db.execute(
        select(KnowledgeSpace.id).where(KnowledgeSpace.user_id == user_id)
    )
    return [row[0] for row in res.all()]


async def list_accessible_spaces_async(
    db: AsyncSession, user_id: int, include_archived: bool = True
) -> List[KnowledgeSpace]:
    """自己拥有的 + 作为成员加入的空间（列表页用）。"""
    member_ids = select(SpaceMember.space_id).where(SpaceMember.user_id == user_id)
    stmt = select(KnowledgeSpace).where(
        (KnowledgeSpace.user_id == user_id) | (KnowledgeSpace.id.in_(member_ids))
    )
    if not include_archived:
        stmt = stmt.where(KnowledgeSpace.status == "active")
    res = await db.execute(stmt.order_by(KnowledgeSpace.id.desc()))
    return list(res.scalars().all())


async def create_space_async(db: AsyncSession, user_id: int, fields: dict) -> KnowledgeSpace:
    space = KnowledgeSpace(user_id=user_id, **fields)
    db.add(space)
    await db.commit()
    await db.refresh(space)
    return space


async def update_space_async(db: AsyncSession, space: KnowledgeSpace, fields: dict) -> KnowledgeSpace:
    for k, v in fields.items():
        setattr(space, k, v)
    space.updated_at = utcnow()
    await db.commit()
    await db.refresh(space)
    return space


async def delete_space_async(db: AsyncSession, space: KnowledgeSpace) -> None:
    await db.delete(space)
    await db.commit()


async def live_stats_async(db: AsyncSession, space_id: int) -> dict:
    """实时算一个空间的文档数 / 片段数（列表页展示用，量不大可接受）。"""
    docs = await db.execute(
        select(func.count(Knowledge.id)).where(Knowledge.space_id == space_id)
    )
    chunks = await db.execute(
        select(func.coalesce(func.sum(Knowledge.chunk_count), 0)).where(Knowledge.space_id == space_id)
    )
    bound = await db.execute(
        select(func.count(AgentKnowledgeSpace.id)).where(AgentKnowledgeSpace.space_id == space_id)
    )
    return {
        "doc_count": int(docs.scalar() or 0),
        "chunk_count": int(chunks.scalar() or 0),
        "bound_agent_count": int(bound.scalar() or 0),
    }
