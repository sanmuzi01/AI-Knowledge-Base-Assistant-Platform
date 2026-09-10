from typing import List, Optional

from models.init_db import Agent, Knowledge
from utils.timeutil import utcnow


def create_knowledge(
        db, user_id: int, agent_id, file_name: str,
        file_path: str, file_type: str, file_size: int,
        *, space_id: int = None, category: str = None, tags_json: str = None,
        version: str = None, source_type: str = "upload", source_url: str = None,
        chunk_size: int = None) -> Knowledge:

    knowledge = Knowledge(
        user_id=user_id,
        agent_id=agent_id,
        file_name=file_name,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        space_id=space_id,
        category=category,
        tags_json=tags_json,
        version=version,
        source_type=source_type or "upload",
        source_url=source_url,
        chunk_size=chunk_size,
        updated_at=utcnow(),
    )
    db.add(knowledge)
    db.flush()
    return knowledge


def set_knowledge_chunk_size(db, knowledge: Knowledge, chunk_size: int = None) -> Knowledge:
    """重建索引前更新切块大小（None=恢复默认）。"""
    knowledge.chunk_size = chunk_size
    knowledge.updated_at = utcnow()
    db.flush()
    return knowledge


def list_knowledge_by_space(db, space_id: int) -> List[Knowledge]:
    return (
        db.query(Knowledge)
        .filter(Knowledge.space_id == space_id)
        .order_by(Knowledge.created_at.desc())
        .all()
    )


def get_owned_knowledge_in_space(db, user_id: int, space_id: int, knowledge_id: int) -> Optional[Knowledge]:
    return (
        db.query(Knowledge)
        .filter(
            Knowledge.id == knowledge_id,
            Knowledge.user_id == user_id,
            Knowledge.space_id == space_id,
        )
        .first()
    )


def get_knowledge_in_space(db, space_id: int, knowledge_id: int) -> Optional[Knowledge]:
    """文档定位到空间（不按 user_id 过滤）—— 空间级访问已由 access_control 校验。

    共享空间里 knowledge.user_id 是空间所有者，成员操作时按这个查。
    """
    return (
        db.query(Knowledge)
        .filter(Knowledge.id == knowledge_id, Knowledge.space_id == space_id)
        .first()
    )


def update_knowledge_meta(db, knowledge: Knowledge, *, category=None, tags_json=None, version=None) -> Knowledge:
    if category is not None:
        knowledge.category = category or None
    if tags_json is not None:
        knowledge.tags_json = tags_json or None
    if version is not None:
        knowledge.version = version or None
    knowledge.updated_at = utcnow()
    db.flush()
    return knowledge


def clone_knowledge_for_agent(db, source: Knowledge, target_agent_id: int) -> Knowledge:
    """把用户已有资料挂到另一个 Agent，复用原文件，并重新生成目标 Agent 的向量索引。"""
    knowledge = Knowledge(
        user_id=source.user_id,
        agent_id=target_agent_id,
        file_name=source.file_name,
        file_path=source.file_path,
        file_type=source.file_type,
        file_size=source.file_size,
        status="pending",
        chunk_count=0,
        is_enabled=1,
    )
    db.add(knowledge)
    db.flush()
    return knowledge

def get_knowledge_by_id(db,knowledge_id:int)->Optional[Knowledge]:
    """根据ID查询知识库文档"""
    return (db.query(Knowledge).filter(Knowledge.id == knowledge_id).first())
def list_knowledge_by_agent(db,agent_id:int)->List[Knowledge]:
    """查询某个Agent下的所有文档（按上传时间倒序）"""
    return (db.query(Knowledge).
            filter(Knowledge.agent_id == agent_id).
            order_by(Knowledge.created_at.desc()).all())

def list_knowledge_by_user(db,user_id:int)->List[Knowledge]:
    """查询某个用户的所有文档（跨Agent）"""
    return(db.query(Knowledge).
           filter(Knowledge.user_id == user_id).
           order_by(Knowledge.created_at.desc()).all())


def list_knowledge_with_agent_by_user(db, user_id: int):
    """查询用户全部资料，并带上所属 Agent 名称。"""
    return (
        db.query(Knowledge, Agent.name.label("agent_name"))
        .join(Agent, Knowledge.agent_id == Agent.id)
        .filter(Knowledge.user_id == user_id, Agent.user_id == user_id)
        .order_by(Knowledge.created_at.desc())
        .all()
    )

def update_knowledge_status(db,knowledge:Knowledge,status:str,chunk_count:int=None,error_msg:str=None)->Knowledge:
    """更新文档处理状态和切块数"""
    knowledge.status = status
    if chunk_count is not None:
        knowledge.chunk_count = chunk_count
    if error_msg is not None:
        knowledge.error_msg = error_msg
    if status in {"processing", "done"}:
        knowledge.error_msg = None
    db.flush()
    return knowledge


def update_knowledge_enabled(db, knowledge: Knowledge, is_enabled: int) -> Knowledge:
    """更新文档是否参与RAG检索。"""
    knowledge.is_enabled = 1 if is_enabled else 0
    db.flush()
    return knowledge


def delete_knowledge(db,knowledge :Knowledge)->None:
    """删除知识库文档记录"""
    db.delete(knowledge)
    db.flush()
