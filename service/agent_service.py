from typing import List, Optional,Dict,Any
from sqlalchemy.exc import IntegrityError

from models.agent_dao import get_agent_by_id, list_agents_by_user, create_agent, update_agent, delete_agent, get_selected_agent_by_user
from models.user_dao import update_selected_agent
from models.init_db import Agent
from sqlalchemy.exc import SQLAlchemyError
# 1. 获取某用户的全部智能体列表（带选中标记）
def list_agent(db,user)->List[Dict[str,Any]]:
    """
    查询用户的智能体列表，每个智能体附带 is_selected 标记
    :param db: 数据库会话
    :param user: 当前用户对象（由 get_current_user 得到）
    :return: 字典列表，每个元素包含 agent 字段 + is_selected
    """
    agents : List[Agent] = list_agents_by_user(db,user.id)
    selected_id = user.selected_agent_id
    result = []
    for agent in agents:
        result.append({
            "id": agent.id,
            "name": agent.name,
            "prompt_file": agent.prompt_file,
            "model_name": agent.model_name,
            "rag_enabled": agent.rag_enabled,
            "temperature": agent.temperature,
            "is_selected": (agent.id == selected_id)
        })
    return result

#获取单个智能体信息(验证归属）
def get_agent(db,user,agent_id:int)->Optional[Dict[str,Any]]:
    """查询单个智能体，必须是当前用户的，否则返回 None（防止越权）"""
    agent = get_agent_by_id(db, agent_id)
    if not agent or agent.user_id != user.id:
        return None
    return {
        "id": agent.id,
        "name": agent.name,
        "prompt_file": agent.prompt_file,
        "model_name": agent.model_name,
        "rag_enabled": agent.rag_enabled,
        "temperature": agent.temperature,
        "is_selected": (agent.id == user.selected_agent_id)
    }
#创建智能体（创建后为自动选中）
def create(db,user,name:str,prompt_file:str = None, model_name: str = "glm-4",
           rag_enabled: int = 0, temperature: int = 70)->Dict[str,Any]:
    """创建智能体，创建后自动选中"""
    try:
        agent =create_agent(
            db=db, name=name, user_id=user.id,
            prompt_file=prompt_file,
            model_name=model_name, rag_enabled=rag_enabled,
            temperature=temperature
        )
        # 创建后自动设为当前选中
        update_selected_agent(db, user, agent.id)
        db.commit()
        return {
            "message": "创建成功",
            "agent_id": agent.id,
            "name": agent.name
        }
    except IntegrityError:
        db.rollback()
        return {
            "message": "创建失败，智能体名称已存在"
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise e
# 4. 更新智能体（只能改自己的）
def update(db, user, agent_id: int, name: str = None,prompt_file: str = None, model_name: str = None, rag_enabled: int = None,temperature: int = None) -> Dict[str, Any]:
    """更新智能体，先验证归属"""
    agent = get_agent_by_id(db, agent_id)
    if not agent or agent.user_id != user.id:
        return {"message": "智能体不存在或不属于当前用户"}
    try:
        agent = update_agent(
            db=db, agent=agent, name=name,prompt_file=prompt_file,
            model_name=model_name,
            rag_enabled=rag_enabled, temperature=temperature
        )
        db.commit()
        return {"message":"更新成功","Agent_ID:":agent_id}
    except SQLAlchemyError as e:
        db.rollback()
        raise e
## 5. 删除智能体（只能删自己的）
def delete(db,user,agent_id:int)->Dict[str,Any]:
    """删除智能体，先验证归属"""
    agent = get_agent_by_id(db,agent_id)
    if not agent or agent.user_id != user.id:
        return {"message":"智能体不存在或无权限删除"}
    # 如果删的是当前选中的，清空用户的 selected_agent_id
    try:
        if user.selected_agent_id == agent.id:
            update_selected_agent(db, user, None)
        delete_agent(db, agent)
        db.commit()
        return {"message":"删除成功","Agent_ID:":agent_id}
    except SQLAlchemyError as e:
        db.rollback()
        raise e


# 6. 选中某个智能体
def select(db,user,agent_id:int)->Optional[Dict[str,Any]]:
     """将某个智能体设为当前选中；必须是自己的"""
     agent = get_agent_by_id(db,agent_id)
     if not agent or agent.user_id != user.id:
         return {"message":"智能体不存在或无权限选中"}
     update_selected_agent(db, user, agent.id)
     db.commit()
     return {"message":"选中成功","Agent_ID:":agent_id}

# 7. 获取当前选中的智能体详情
def get_selected(db,user)->Optional[Dict[str,Any]]:
    """获取当前选中的智能体详情"""
    agent = get_selected_agent_by_user(db, user)
    if not agent:
        return None
    return {
        "id": agent.id,
        "name": agent.name,
        "prompt_file": agent.prompt_file,
        "model_name": agent.model_name,
        "rag_enabled": agent.rag_enabled,
        "temperature": agent.temperature
    }




