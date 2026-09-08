"""会话异步 DAO。"""

from utils.timeutil import utcnow
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import Agent, Conversation, Message


async def agent_belongs_to_user_async(db: AsyncSession, user_id: int, agent_id: int) -> bool:
    """异步判断助手是否属于当前用户。"""

    result = await db.execute(
        select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None


async def get_conversation_by_id_async(
        db: AsyncSession, conversation_id: int,
) -> Optional[Conversation]:
    """异步按 ID 查询会话。"""

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    return result.scalars().first()


async def get_owned_conversation_async(
        db: AsyncSession, user_id: int, conversation_id: int, agent_id: int = None,
) -> Optional[Conversation]:
    """异步查询当前用户自己的会话。"""

    conditions = [
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    ]
    if agent_id is not None:
        conditions.append(Conversation.agent_id == agent_id)
    result = await db.execute(select(Conversation).where(*conditions))
    return result.scalars().first()


async def list_conversations_by_agent_async(
        db: AsyncSession, user_id: int, agent_id: int, limit: int = 50,
) -> List[Conversation]:
    """异步查询某用户某助手下的会话。"""

    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.agent_id == agent_id)
        .order_by(
            Conversation.is_archived.asc(),
            Conversation.is_pinned.desc(),
            Conversation.update_time.desc(),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_messages_by_conversation_async(
        db: AsyncSession, conversation_id: int, limit: int = 100,
) -> List[Message]:
    """异步查询会话消息，按时间正序返回。"""

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.create_time.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_conversation_async(
        db: AsyncSession,
        user_id: int,
        agent_id: int,
        title: str = "新会话",
) -> Conversation:
    conv = Conversation(
        user_id=user_id,
        agent_id=agent_id,
        title=title,
        create_time=utcnow(),
        update_time=utcnow(),
    )
    db.add(conv)
    await db.flush()
    return conv


async def update_conversation_title_async(
        db: AsyncSession,
        conv: Conversation,
        title: str,
) -> Conversation:
    conv.title = title
    conv.update_time = utcnow()
    await db.flush()
    return conv


async def update_conversation_flags_async(
        db: AsyncSession,
        conv: Conversation,
        is_pinned: int = None,
        is_archived: int = None,
) -> Conversation:
    if is_pinned is not None:
        conv.is_pinned = is_pinned
    if is_archived is not None:
        conv.is_archived = is_archived
    conv.update_time = utcnow()
    await db.flush()
    return conv


async def delete_conversation_async(db: AsyncSession, conv: Conversation) -> None:
    await db.delete(conv)
    await db.flush()
