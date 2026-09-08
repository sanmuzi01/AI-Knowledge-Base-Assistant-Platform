"""旧版聊天记录异步 DAO。"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import Chat


async def list_chats_by_agent_async(
        db: AsyncSession, user_id: int, agent_id: int, limit: int = 20,
) -> List[Chat]:
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == user_id, Chat.agent_id == agent_id)
        .order_by(Chat.create_time.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
