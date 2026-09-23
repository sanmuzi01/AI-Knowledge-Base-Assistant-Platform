"""
会话系统 Service 业务层
职责：
  1. 权限校验（会话必须属于当前用户）
  2. 业务逻辑（标题自动生成、活跃时间更新）
  3. 组装返回数据给路由层（转 dict，不暴露 ORM 对象）
  4. 提供 chat_service 需要的辅助方法（保存消息、加载历史）
遵循四层架构约束：写操作由 Service 统一提交事务，路由层只负责 HTTP 编排。
"""
from typing import List, Optional, Dict, Any
from models.init_db import Conversation, Message
from models import conversation_dao as dao
from service.access_control import get_owned_agent, get_owned_conversation
from utils.logger_handler import get_logger

logger = get_logger("conversation_service")

# ========== 会话 CRUD ==========

def create_conversation(
        db, user_id: int, agent_id: int, title: str = None
) -> Dict[str, Any]:
    """创建新会话
    :param title: 可选，为空时默认"新会话"
    :return: 会话信息字典
    """
    if not get_owned_agent(db, user_id, agent_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试为Agent {agent_id}创建会话")
        return None
    conv = dao.create_conversation(
        db, user_id=user_id, agent_id=agent_id,
        title=title or "新会话"
    )
    db.commit()
    logger.info(f"创建会话: id={conv.id}, agent_id={agent_id}, user_id={user_id}")
    return _conv_to_dict(conv)

def get_conversation(db, user_id: int, conversation_id: int) -> Optional[Dict[str, Any]]:
    """查询单个会话（含权限校验：必须属于当前用户）"""
    conv = get_owned_conversation(db, user_id, conversation_id)
    if not conv:
        logger.warning(f"权限拒绝：用户{user_id}尝试访问会话{conversation_id}")
        return None
    return _conv_to_dict(conv)

def list_conversations(
        db, user_id: int, agent_id: int, limit: int = 50
) -> List[Dict[str, Any]]:
    """查询某用户某Agent下的所有会话（按最近活跃倒序）"""
    if not get_owned_agent(db, user_id, agent_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试列出Agent {agent_id}的会话")
        return []
    convs = dao.list_conversations_by_agent(db, user_id, agent_id, limit)
    return [_conv_to_dict(c) for c in convs]

def update_conversation_title(
        db, user_id: int, conversation_id: int, title: str
) -> Optional[Dict[str, Any]]:
    """更新会话标题（含权限校验）"""
    conv = get_owned_conversation(db, user_id, conversation_id)
    if not conv:
        return None
    conv = dao.update_conversation_title(db, conv, title)
    db.commit()
    logger.info(f"更新会话标题: id={conversation_id}, title={title}")
    return _conv_to_dict(conv)


def update_conversation_flags(
        db, user_id: int, conversation_id: int,
        is_pinned: Optional[int] = None, is_archived: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """更新会话置顶/归档状态（含权限校验）。"""
    conv = get_owned_conversation(db, user_id, conversation_id)
    if not conv:
        return None
    if is_pinned is not None:
        is_pinned = 1 if is_pinned else 0
    if is_archived is not None:
        is_archived = 1 if is_archived else 0
    conv = dao.update_conversation_flags(db, conv, is_pinned=is_pinned, is_archived=is_archived)
    db.commit()
    logger.info(f"更新会话标记: id={conversation_id}, pinned={is_pinned}, archived={is_archived}")
    return _conv_to_dict(conv)

def delete_conversation(db, user_id: int, conversation_id: int) -> bool:
    """删除会话（含权限校验，级联删除消息）"""
    conv = get_owned_conversation(db, user_id, conversation_id)
    if not conv:
        return False
    dao.delete_conversation(db, conv)
    db.commit()
    logger.info(f"删除会话: id={conversation_id}, 级联删除其下所有消息")
    return True

# ========== 消息查询 ==========

def list_messages(
        db, user_id: int, conversation_id: int, limit: int = 100
) -> Optional[List[Dict[str, Any]]]:
    """查询会话下的所有消息（正序，用于聊天历史展示）
    含权限校验：会话必须属于当前用户
    """
    conv = get_owned_conversation(db, user_id, conversation_id)
    if not conv:
        return None
    msgs = dao.list_messages_by_conversation(db, conversation_id, limit)
    return [_msg_to_dict(m) for m in msgs]


def export_conversation(db, user_id: int, conversation_id: int, fmt: str = "markdown") -> Optional[Dict[str, str]]:
    conv = get_owned_conversation(db, user_id, conversation_id)
    if not conv:
        return None
    messages = dao.list_messages_by_conversation(db, conversation_id, limit=1000)
    safe_title = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in conv.title).strip("_") or "conversation"
    if fmt == "json":
        import json
        content = json.dumps({
            "conversation": _conv_to_dict(conv),
            "messages": [_msg_to_dict(msg) for msg in messages],
        }, ensure_ascii=False, indent=2)
        return {"filename": f"{safe_title}_{conv.id}.json", "media_type": "application/json", "content": content}

    lines = [f"# {conv.title}", "", f"- 会话ID: {conv.id}", f"- Agent ID: {conv.agent_id}", ""]
    for msg in messages:
        role = {"user": "用户", "assistant": "助手", "system": "系统"}.get(msg.role, msg.role)
        lines.extend([f"## {role}", "", msg.content or "", ""])
    return {"filename": f"{safe_title}_{conv.id}.md", "media_type": "text/markdown", "content": "\n".join(lines)}

# ========== 供 chat_service 调用的辅助方法 ==========

def save_message(
        db, conversation_id: int, role: str, content: str
) -> Message:
    """保存一条消息，并更新会话活跃时间（供 chat_service 调用）"""
    msg = dao.create_message(db, conversation_id, role, content)
    # 更新会话活跃时间
    conv = dao.get_conversation_by_id(db, conversation_id)
    if conv:
        dao.touch_conversation(db, conv)
    return msg

def load_history_for_llm(
        db, conversation_id: int, limit: int = 20
) -> List[Dict[str, str]]:
    """加载最近N条消息作为 LLM 上下文（供 chat_service/agent_runtime 调用）
    返回格式：[{"role": "user", "content": "..."}, ...]
    只取 user 和 assistant 消息，过滤 system
    """
    msgs = dao.list_messages_for_history(db, conversation_id, limit)
    history = []
    for m in msgs:
        if m.role in ("user", "assistant"):
            history.append({"role": m.role, "content": m.content})
    return history

def auto_generate_title(message: str, max_len: int = 20) -> str:
    """根据首条用户消息自动生成会话标题
    简单实现：截取前 max_len 个字符 + "..."
    后续可改成调用 LLM 生成更优雅的标题
    """
    msg = message.strip().replace("\n", " ")
    if len(msg) <= max_len:
        return msg
    return msg[:max_len] + "..."

def maybe_update_title_by_first_message(
        db, conversation_id: int, user_message: str
) -> None:
    """如果是会话的第一条消息，用消息内容自动生成标题"""
    conv = dao.get_conversation_by_id(db, conversation_id)
    if not conv:
        return
    # 标题还是默认"新会话" → 说明是第一条消息，自动生成标题
    if conv.title == "新会话":
        new_title = auto_generate_title(user_message)
        dao.update_conversation_title(db, conv, new_title)
        logger.info(f"会话{conversation_id}自动生成标题: {new_title}")

# ========== 内部转换工具 ==========

def _conv_to_dict(conv: Conversation) -> Dict[str, Any]:
    """ORM 对象转字典（给路由层返回 JSON 用）"""
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
    """ORM 对象转字典"""
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role,
        "content": msg.content,
        "create_time": msg.create_time.strftime("%Y-%m-%d %H:%M:%S") if msg.create_time else None,
    }
