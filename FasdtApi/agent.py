from fastapi import APIRouter,Depends,HTTPException,status
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from typing import Optional, List
from models.init_db import get_db, User
from service.dependencies import get_current_user
from service import agent_service
router = APIRouter(prefix="/agent", tags=["agent管理"])
class AgentResponse(BaseModel):
    id: int
    name: str
    prompt: dict | None
    model_name: str
    rag_enabled: int
    memory_enabled: int
    temperature: int
    skills: List[dict] = []
    class Config:
        from_attributes = True
class AgentWithSelectedResponse(AgentResponse):
    is_selected: bool
#创建智能体用
class AgentCreate(BaseModel):
    name:str = Field(min_length=1,max_length=255)
    model_name:str=Field(default="glm-4")
    role: Optional[str] = Field(default=None)
    task: Optional[str] = Field(default=None)
    constraints: Optional[str] = Field(default=None)
    output: Optional[str] = Field(default=None)
    rag_enabled: int =  Field(default=0, ge=0, le=1)
    memory_enabled: int = Field(default=1, ge=0, le=1)
    temperature:int = Field(default=70,ge=0,le=100)
    skill_ids: List[int] = Field(default=[])

# 更新用
class AgentUpdate(BaseModel):
    name:Optional[str] = Field(default=None,min_length=1,max_length=255)
    role: Optional[str] = Field(default=None)
    task: Optional[str] = Field(default=None)
    constraints: Optional[str] = Field(default=None)
    output: Optional[str] = Field(default=None)
    model_name:Optional[str]=Field(default=None)
    rag_enabled: Optional[int] = Field(default=None, ge=0, le=1)
    memory_enabled: Optional[int] = Field(default=None, ge=0, le=1)
    temperature:Optional[int] = Field(default=None,ge=0,le=100)
    skill_ids: Optional[List[int]] = Field(default=None)


class AgentDryRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    conversation_id: Optional[int] = Field(default=None, ge=1)

@router.get("/list",summary="查询用户的智能体列表",response_model=List[AgentWithSelectedResponse])
def list_agents(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)):
    """查询用户的智能体列表，每个智能体附带 is_selected 标记"""
    return agent_service.list_agent(db, current_user)
@router.get("/selected/me",summary="获取选中智能体")
def get_selected(
        db :Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    result  = agent_service.get_selected(db,current_user)
    return result
@router.get("/{agent_id:int}",summary="查询单个智能体信息",response_model=AgentWithSelectedResponse)
def get_agent(
        agent_id:int,
        db:Session = Depends(get_db),
        current_user: User =Depends(get_current_user) ):
    result = agent_service.get_agent(db, current_user,agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,detail = "智能体不存在或无权限")
    return result

@router.get("/{agent_id:int}/debug", summary="查看Agent运行调试信息")
def get_agent_debug(
        agent_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)):
    result = agent_service.get_agent_debug(db, current_user, agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限")
    return result


@router.post("/{agent_id:int}/dry-run", summary="Agent Dry Run调试")
def dry_run_agent(
        agent_id: int,
        data: AgentDryRunRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)):
    try:
        result = agent_service.dry_run_agent(
            db=db,
            user=current_user,
            agent_id=agent_id,
            user_message=data.message,
            conversation_id=data.conversation_id,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限")
    return result

@router.post("",summary="创建智能体")
def create_agent(
        agent:AgentCreate,
        db:Session = Depends(get_db),
        current_user:User = Depends(get_current_user)):
    result = agent_service.create(
        db=db,
        user=current_user,
        name=agent.name,
        role=agent.role,
        task=agent.task,
        constraints=agent.constraints,
        output=agent.output,
        model_name=agent.model_name,
        rag_enabled=agent.rag_enabled,
        memory_enabled=agent.memory_enabled,
        temperature=agent.temperature
    )
    # 2. 如果指定了skill_ids，绑定Skill
    if agent.skill_ids:
        from service.skill_service import update_agent_skills
        if not update_agent_skills(db, result["agent_id"], agent.skill_ids, user_id=current_user.id):
            db.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="绑定Skill失败，请检查Skill是否存在或有权限")
    db.commit()
    return result
@router.put("/{agent_id}",summary="更新智能体信息")
def update_agent(
        agent_id:int,
        agent_update:AgentUpdate,
        db:Session = Depends(get_db),
        current_user:User = Depends(get_current_user)):
    result = agent_service.get_agent(db, current_user, agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限更新")
    update_result = agent_service.update(
        db=db,
        user=current_user,
        agent_id=agent_id,
        name=agent_update.name,
        role=agent_update.role,
        task=agent_update.task,
        constraints=agent_update.constraints,
        output=agent_update.output,
        model_name=agent_update.model_name,
        rag_enabled=agent_update.rag_enabled,
        memory_enabled=agent_update.memory_enabled,
        temperature=agent_update.temperature
    )
    if agent_update.skill_ids is not None:
        from service.skill_service import update_agent_skills
        if not update_agent_skills(db, agent_id, agent_update.skill_ids, user_id=current_user.id):
            db.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="绑定Skill失败，请检查Skill是否存在或有权限")
        db.commit()
    return update_result
@router.get("/{agent_id}/delete_preview", summary="删除智能体预检（返回将被删除的数据量）")
def delete_preview_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """前端展示删除确认弹窗时先调这个，拿到影响范围再让用户确认"""
    result = agent_service.delete_preview(db, current_user, agent_id)
    if not result:
        raise HTTPException(status_code=404, detail="智能体不存在或无权限")
    return result
@router.delete("/{agent_id}",summary="删除智能体")
def delete_agent(
        agent_id:int,
        db:Session = Depends(get_db),
        current_user:User = Depends(get_current_user)
):
    result = agent_service.get_agent(db, current_user, agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,detail = "智能体不存在或无权限删除")
    return agent_service.delete(db, current_user, agent_id)
@router.post("/{agent_id}/select",summary="选中智能体")
def select_agent(
        agent_id :int,
        db:Session = Depends(get_db),
        current_user:User = Depends(get_current_user)
):
    result = agent_service.get_agent(db, current_user, agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限选中")
    return agent_service.select(
        db,current_user,agent_id
    )
