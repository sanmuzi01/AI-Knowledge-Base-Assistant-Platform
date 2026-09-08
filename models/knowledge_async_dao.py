"""知识库异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import Agent, Knowledge, KnowledgeChunk


async def agent_belongs_to_user_async(db: AsyncSession, user_id: int, agent_id: int) -> bool:
    """检查助手是否属于当前用户。"""

    result = await db.execute(
        select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    return result.scalar() is not None


async def list_knowledge_with_agent_by_user_async(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Knowledge, Agent.name.label("agent_name"))
        .join(Agent, Knowledge.agent_id == Agent.id)
        .where(Knowledge.user_id == user_id, Agent.user_id == user_id)
        .order_by(Knowledge.created_at.desc())
    )
    return result.all()


async def list_knowledge_by_agent_async(db: AsyncSession, agent_id: int) -> List[Knowledge]:
    result = await db.execute(
        select(Knowledge)
        .where(Knowledge.agent_id == agent_id)
        .order_by(Knowledge.created_at.desc())
    )
    return list(result.scalars().all())


async def get_owned_knowledge_async(
        db: AsyncSession, user_id: int, knowledge_id: int, agent_id: int = None,
) -> Optional[Knowledge]:
    conditions = [Knowledge.id == knowledge_id, Knowledge.user_id == user_id]
    if agent_id is not None:
        conditions.append(Knowledge.agent_id == agent_id)
    result = await db.execute(select(Knowledge).where(*conditions))
    return result.scalars().first()


async def list_chunks_by_knowledge_async(
        db: AsyncSession, knowledge_id: int,
) -> List[KnowledgeChunk]:
    result = await db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.knowledge_id == knowledge_id)
        .order_by(KnowledgeChunk.chunk_index.asc())
    )
    return list(result.scalars().all())
