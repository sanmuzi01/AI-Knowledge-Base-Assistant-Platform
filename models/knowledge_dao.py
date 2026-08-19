from typing import List,Optional
from models.init_db import Knowledge       # ✅ 对
def create_knowledge(
        db,user_id:int,agent_id:int,file_name:str,
        file_path:str,file_type:str,file_size:int)->Knowledge:

    knowledge = Knowledge(
        user_id = user_id,
        agent_id = agent_id,
        file_name = file_name,
        file_path = file_path,
        file_type = file_type,
        file_size = file_size
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


def delete_knowledge(db,knowledge :Knowledge)->None:
    """删除知识库文档记录"""
    db.delete(knowledge)
    db.flush()
