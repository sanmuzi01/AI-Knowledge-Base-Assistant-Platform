"""
Memory 记忆表 DAO（数据访问层）
Service层（memory_service.py）只调DAO，不直接碰ORM
DAO层只管CRUD，不管业务逻辑
"""
from typing import List,Optional
from models.init_db import Memory
def create_memory(
        db, user_id: int, agent_id: int,
        memory_type: str, content: str, chat_count: int = 0
) -> Memory:
    """新建一条记忆记录"""
    memory = Memory(
        user_id=user_id,
        agent_id=agent_id,
        memory_type=memory_type,
        content=content,
        chat_count=chat_count,
    )
    db.add(memory)
    db.flush()
    return memory

def get_latest_summary(db, user_id: int, agent_id: int) -> Optional[Memory]:
    #获取最新的会话摘要（只取1条，因为每次总结会覆盖旧的）
    return (db.query(Memory).filter(
        Memory.user_id == user_id,
        Memory.agent_id == agent_id,
        Memory.memory_type == "summary"
    ).order_by(Memory.created_at.desc()).first())

def get_memory_by_id(db, memory_id: int) -> Optional[Memory]:
    """按ID获取记忆记录"""
    return db.query(Memory).filter(Memory.id == memory_id).first()

def list_memories_by_agent(db, user_id: int, agent_id: int) -> List[Memory]:
    """获取某用户某Agent的全部长期记忆"""
    return (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.agent_id == agent_id)
        .order_by(Memory.created_at.desc(), Memory.id.desc())
        .all()
    )

def get_all_facts(db,user_id:int,agent_id:int)->List[Memory]:
    #获取所有关键事实（类型=fact）
    return (db.query(Memory).filter(
        Memory.user_id == user_id,
        Memory.agent_id == agent_id,
        Memory.memory_type == "fact"
    ).order_by(Memory.created_at.desc()).all())
def delete_memory(db,memory:Memory)->None:
    """删除一条记忆"""
    db.delete(memory)
    db.flush()
def delete_all_memory_by_agent(db,agent_id:int)->int:
    #删除某Agent的所有记忆（删Agent时调用）
    memories = (
        db.query(Memory).filter(Memory.agent_id == agent_id).all()
    )
    count = len(memories)
    for m in memories:
        db.delete(m)
    db.flush()
    return count

def delete_memories_by_user_agent(db, user_id: int, agent_id: int) -> int:
    """删除当前用户某Agent的全部记忆"""
    memories = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.agent_id == agent_id)
        .all()
    )
    count = len(memories)
    for memory in memories:
        db.delete(memory)
    db.flush()
    return count

def update_memory(db, memory: Memory, memory_type: str = None, content: str = None) -> Memory:
    """更新记忆内容"""
    if memory_type is not None:
        memory.memory_type = memory_type
    if content is not None:
        memory.content = content
    db.flush()
    return memory
