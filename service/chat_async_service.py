"""旧版聊天记录异步读服务。"""

from typing import Dict, List

from models.chat_async_dao import list_chats_by_agent_async


async def list_legacy_history(db, user_id: int, agent_id: int, limit: int = 20) -> List[Dict]:
    chats = await list_chats_by_agent_async(db, user_id, agent_id, limit=limit)
    return [
        {
            "id": chat.id,
            "question": chat.question,
            "answer": chat.answer,
            "create_time": chat.create_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for chat in reversed(chats)
    ]
