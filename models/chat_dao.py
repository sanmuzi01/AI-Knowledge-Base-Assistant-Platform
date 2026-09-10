from typing import List,Optional
from datetime import datetime
from models.init_db import Chat

def create_chat(
        db,user_id:int,agent_id:int,
        question:str,answer: str) -> Chat:
    """保存对话记录"""
    chat = Chat(
        user_id=user_id,
        agent_id=agent_id,
        question =question,
        answer = answer,
        create_time =datetime.now()
    )
    db.add(chat)
    db.flush()
    return chat
def list_chats_by_agent(
        db,user_id:int,agent_id:int,
        limit:int=20)->List[Chat]:
    """查询某智能体的对话历史（按时间倒序）"""
    return (
        db.query(Chat).filter
        (Chat.user_id == user_id,Chat.agent_id == agent_id).
        order_by(Chat.create_time.desc()).limit(limit).all()
    )
def get_chat_by_id(db,chat_id:int)->Optional[Chat]:
    """根据ID查询对话记录"""
    return db.query(Chat).filter(Chat.id == chat_id).first()
