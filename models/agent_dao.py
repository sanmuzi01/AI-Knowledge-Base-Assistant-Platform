from typing import Optional,List
from models.init_db import Agent

def get_agent_by_id(db, agent_id: int) -> Optional[Agent]:
    """根据 ID 查询智能体"""
    return db.query(Agent).filter(Agent.id == agent_id).first()

def list_agents_by_user(db,user_id:int)->List[Agent]:
    """查询指定用户下的所有智能体（按 ID 倒序，新的在前）"""
    return db.query(Agent).filter(Agent.user_id == user_id).order_by(Agent.id.desc()).all()

def create_agent(db,name:str,user_id:int,prompt_file:str=None,model_name:str="glm-4",rag_enabled:int=0,memory_enabled:int=1,temperature:int=70)->Agent:
    """创建智能体"""
    agent = Agent(
        name=name,
        user_id=user_id,
        prompt_file=prompt_file,
        model_name=model_name,
        rag_enabled=rag_enabled,
        memory_enabled=memory_enabled,
        temperature=temperature
    )
    db.add(agent)
    db.flush()
    return agent

def update_agent(db,agent:Agent,name:str=None,prompt_file:str=None,model_name:str=None,rag_enabled:int=None,memory_enabled:int=None,temperature:int=None)->Agent:
    """更新智能体"""
    if name is not None:
        agent.name = name
    if prompt_file is not None:
        agent.prompt_file = prompt_file
    if model_name is not None:
        agent.model_name = model_name
    if rag_enabled is not None:
        agent.rag_enabled = rag_enabled
    if memory_enabled is not None:
        agent.memory_enabled = memory_enabled
    if temperature is not None:
        agent.temperature = temperature
    db.flush()
    return agent

def delete_agent(db, agent: Agent) -> None:
    """删除智能体"""
    db.delete(agent)
    db.flush()

def get_selected_agent_by_user(db, user) -> Optional[Agent]:
    """获取用户当前选中的智能体"""
    if not user.selected_agent_id:
        return None
    return db.query(Agent).filter(Agent.id == user.selected_agent_id).first()