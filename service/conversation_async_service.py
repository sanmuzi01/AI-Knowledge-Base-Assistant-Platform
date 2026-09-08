"""会话异步服务。"""

from typing import Any, Dict, List, Optional

from models import conversation_async_dao as dao
from models.init_db import Conversation, Message
from utils.logger_handler import get_logger

logger = get_logger("conversation_async_service")


def _conv_to_dict(conv: Conversation) -> Dict[str, Any]:
    return {
        "id": conv.id,
        "user_id": conv.user_id,
        "agent_id": conv.agent_id,
        "title": conv.title,
        "is_pinned": conv.is_pinned or 0,
        "is_archived": conv.is_archived or 0,
        "create_time": conv.create_time.strftime("%Y-%m-%d %H:%M:%S") if conv.create_time else None,
        "update_time": conv.update_time.strftime("%Y-%m-%d %H:%M:%S") if conv.update_time else None,
    }


def _msg_to_dict(msg: Message) -> Dict[str, Any]:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role,
        "content": msg.content,
        "create_time": msg.create_time.strftime("%Y-%m-%d %H:%M:%S") if msg.create_time else None,
    }


async def list_conversations(
        db, user_id: int, agent_id: int, limit: int = 50,
) -> List[Dict[str, Any]]:
    """异步查询会话列表。"""

    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试列出助手 {agent_id} 的会话")
        return []
    convs = await dao.list_conversations_by_agent_async(db, user_id, agent_id, limit)
    return [_conv_to_dict(conv) for conv in convs]


async def create_conversation(
        db, user_id: int, agent_id: int, title: str = None,
) -> Optional[Dict[str, Any]]:
    """异步创建会话。"""
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试为助手 {agent_id} 创建会话")
        return None
    conv = await dao.create_conversation_async(
        db,
        user_id=user_id,
        agent_id=agent_id,
        title=title or "新会话",
    )
    await db.commit()
    return _conv_to_dict(conv)


async def get_conversation(db, user_id: int, conversation_id: int) -> Optional[Dict[str, Any]]:
    """异步查询单个会话。"""

    conv = await dao.get_owned_conversation_async(db, user_id, conversation_id)
    if not conv:
        logger.warning(f"权限拒绝：用户{user_id}尝试访问会话{conversation_id}")
        return None
    return _conv_to_dict(conv)


async def list_messages(
        db, user_id: int, conversation_id: int, limit: int = 100,
) -> Optional[List[Dict[str, Any]]]:
    """异步查询会话消息。"""

    conv = await dao.get_owned_conversation_async(db, user_id, conversation_id)
    if not conv:
        return None
    msgs = await dao.list_messages_by_conversation_async(db, conversation_id, limit)
    return [_msg_to_dict(msg) for msg in msgs]


async def update_conversation_title(
        db, user_id: int, conversation_id: int, title: str,
) -> Optional[Dict[str, Any]]:
    conv = await dao.get_owned_conversation_async(db, user_id, conversation_id)
    if not conv:
        return None
    conv = await dao.update_conversation_title_async(db, conv, title)
    await db.commit()
    return _conv_to_dict(conv)


async def update_conversation_flags(
        db,
        user_id: int,
        conversation_id: int,
        is_pinned: Optional[int] = None,
        is_archived: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    conv = await dao.get_owned_conversation_async(db, user_id, conversation_id)
    if not conv:
        return None
    if is_pinned is not None:
        is_pinned = 1 if is_pinned else 0
    if is_archived is not None:
        is_archived = 1 if is_archived else 0
    conv = await dao.update_conversation_flags_async(
        db,
        conv,
        is_pinned=is_pinned,
        is_archived=is_archived,
    )
    await db.commit()
    return _conv_to_dict(conv)


async def export_conversation(
        db, user_id: int, conversation_id: int, fmt: str = "markdown",
) -> Optional[Dict[str, str]]:
    """异步导出会话为 markdown / json（纯读 + 字符串拼装）。"""

    conv = await dao.get_owned_conversation_async(db, user_id, conversation_id)
    if not conv:
        return None
    messages = await dao.list_messages_by_conversation_async(db, conversation_id, 1000)
    safe_title = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (conv.title or "")
    ).strip("_") or "conversation"

    if fmt == "json":
        import json

        content = json.dumps(
            {
                "conversation": _conv_to_dict(conv),
                "messages": [_msg_to_dict(msg) for msg in messages],
            },
            ensure_ascii=False,
            indent=2,
        )
        return {
            "filename": f"{safe_title}_{conv.id}.json",
            "media_type": "application/json",
            "content": content,
        }

    lines = [f"# {conv.title}", "", f"- 会话ID: {conv.id}", f"- Agent ID: {conv.agent_id}", ""]
    for msg in messages:
        role = {"user": "用户", "assistant": "助手", "system": "系统"}.get(msg.role, msg.role)
        lines.extend([f"## {role}", "", msg.content or "", ""])
    return {
        "filename": f"{safe_title}_{conv.id}.md",
        "media_type": "text/markdown",
        "content": "\n".join(lines),
    }


async def delete_conversation(db, user_id: int, conversation_id: int) -> bool:
    conv = await dao.get_owned_conversation_async(db, user_id, conversation_id)
    if not conv:
        return False
    await dao.delete_conversation_async(db, conv)
    await db.commit()
    return True
