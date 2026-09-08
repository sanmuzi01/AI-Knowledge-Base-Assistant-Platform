"""长期记忆异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import Agent, Memory


async def agent_belongs_to_user_async(db: AsyncSession, user_id: int, agent_id: int) -> bool:
    result = await db.execute(
        select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    return result.scalar() is not None


async def list_memories_by_agent_async(
        db: AsyncSession, user_id: int, agent_id: int,
) -> List[Memory]:
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == user_id, Memory.agent_id == agent_id)
        .order_by(Memory.created_at.desc(), Memory.id.desc())
    )
    return list(result.scalars().all())


async def create_memory_async(
        db: AsyncSession,
        user_id: int,
        agent_id: int,
        memory_type: str,
        content: str,
        chat_count: int = 0,
) -> Memory:
    memory = Memory(
        user_id=user_id,
        agent_id=agent_id,
        memory_type=memory_type,
        content=content,
        chat_count=chat_count,
    )
    db.add(memory)
    await db.flush()
    return memory


async def get_memory_by_id_async(db: AsyncSession, memory_id: int) -> Optional[Memory]:
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    return result.scalars().first()


async def get_owned_memory_async(
        db: AsyncSession,
        user_id: int,
        memory_id: int,
        agent_id: int = None,
) -> Optional[Memory]:
    conditions = [Memory.id == memory_id, Memory.user_id == user_id]
    if agent_id is not None:
        conditions.append(Memory.agent_id == agent_id)
    result = await db.execute(select(Memory).where(*conditions))
    return result.scalars().first()


async def update_memory_async(
        db: AsyncSession,
        memory: Memory,
        memory_type: str = None,
        content: str = None,
) -> Memory:
    if memory_type is not None:
        memory.memory_type = memory_type
    if content is not None:
        memory.content = content
    await db.flush()
    return memory


async def delete_memory_async(db: AsyncSession, memory: Memory) -> None:
    await db.delete(memory)
    await db.flush()


async def delete_memories_by_user_agent_async(
        db: AsyncSession,
        user_id: int,
        agent_id: int,
) -> int:
    memories = await list_memories_by_agent_async(db, user_id, agent_id)
    count = len(memories)
    for memory in memories:
        await db.delete(memory)
    await db.flush()
    return count
