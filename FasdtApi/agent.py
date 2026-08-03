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
    model_name: str
    rag_enabled: int
    temperature: int
    class Config:
        from_attributes = True
class AgentWithSelectedResponse(AgentResponse):
    is_selected: bool
#创建智能体用
class AgentCreate(BaseModel):
    name:str = Field(min_length=1,max_length=255)
    model_name:str=Field(default="glm-4")
    prompt_file: Optional[str] = Field(default=None)
    rag_enabled: int =  Field(default=0, ge=0, le=1)
    temperature:int = Field(default=70,ge=0,le=100)
# 更新用
class AgentUpdate(BaseModel):
    name:Optional[str] = Field(default=None,min_length=1,max_length=255)
    prompt_file: Optional[str] = Field(default=None)
    model_name:Optional[str]=Field(default=None)
    rag_enabled: Optional[int] = Field(default=None, ge=0, le=1)
    temperature:Optional[int] = Field(default=None,ge=0,le=100)

@router.get("/list",summary="查询用户的智能体列表",response_model=List[AgentWithSelectedResponse])
def list_agents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """查询用户的智能体列表，每个智能体附带 is_selected 标记"""
    return agent_service.list_agent(db, current_user)
@router.get("/selected/me",summary="获取选中智能体", response_model=AgentResponse)
def get_selected(
        db :Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    result  = agent_service.get_selected(db,current_user)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,detail="当前没有选中智能体")
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

@router.post("",summary="创建智能体")
def create_agent(
        agent:AgentCreate,
        db:Session = Depends(get_db),
        current_user:User = Depends(get_current_user)):
    return agent_service.create(
        db = db,
        user=current_user,
        name = agent.name,
        prompt_file=agent.prompt_file,
        model_name=agent.model_name,
        rag_enabled=agent.rag_enabled,
        temperature=agent.temperature
    )
@router.put("/{agent_id}",summary="更新智能体信息")
def update_agent(
        agent_id:int,
        agent_update:AgentUpdate,
        db:Session = Depends(get_db),
        current_user:User = Depends(get_current_user)):
    result = agent_service.get_agent(db, current_user, agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限更新")
    return agent_service.update(
        db=db,
        user=current_user,
        agent_id=agent_id,
        name=agent_update.name,
        prompt_file=agent_update.prompt_file,
        model_name=agent_update.model_name,
        rag_enabled=agent_update.rag_enabled,
        temperature=agent_update.temperature
    )
@router.delete("/{agent_id}",summary="删除智能体")
def delete_agent(
        agent_id:int,
        db:Session = Depends(get_db),
        current_user:User = Depends(get_current_user)
):
    result = agent_service.get_agent(db, current_user, agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,detail = "智能体不存在或无权限删除")
    return result
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


