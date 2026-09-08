"""长期记忆异步服务。"""

from typing import Dict, List, Optional

from models import memory_async_dao as dao
from service.memory.memory_service import _normalize_memory_type, memory_to_dict


async def list_agent_memories(db, user_id: int, agent_id: int) -> Optional[List[Dict]]:
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        return None
    memories = await dao.list_memories_by_agent_async(db, user_id, agent_id)
    return [memory_to_dict(memory) for memory in memories]


async def add_memory(db, user_id: int, agent_id: int, memory_type: str, content: str) -> Optional[Dict]:
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        return None
    normalized_type = _normalize_memory_type(memory_type)
    memory = await dao.create_memory_async(
        db=db,
        user_id=user_id,
        agent_id=agent_id,
        memory_type=normalized_type,
        content=content.strip(),
        chat_count=0,
    )
    await db.commit()
    return memory_to_dict(memory)


async def edit_memory(db, user_id: int, memory_id: int,
                      memory_type: str = None, content: str = None) -> Optional[Dict]:
    memory = await dao.get_owned_memory_async(db, user_id, memory_id)
    if not memory or not await dao.agent_belongs_to_user_async(db, user_id, memory.agent_id):
        return None
    normalized_type = _normalize_memory_type(memory_type) if memory_type is not None else None
    next_content = content.strip() if content is not None else None
    updated = await dao.update_memory_async(
        db,
        memory,
        memory_type=normalized_type,
        content=next_content,
    )
    await db.commit()
    return memory_to_dict(updated)


async def remove_memory(db, user_id: int, memory_id: int) -> bool:
    memory = await dao.get_owned_memory_async(db, user_id, memory_id)
    if not memory or not await dao.agent_belongs_to_user_async(db, user_id, memory.agent_id):
        return False
    await dao.delete_memory_async(db, memory)
    await db.commit()
    return True


async def clear_agent_memories(db, user_id: int, agent_id: int) -> Optional[int]:
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        return None
    count = await dao.delete_memories_by_user_agent_async(db, user_id, agent_id)
    await db.commit()
    return count
