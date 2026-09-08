from fastapi import APIRouter,Depends,HTTPException,status
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from typing import Optional, List
from models.init_db import get_db, User
from models.async_db import get_async_db
from service.dependencies import get_current_user, get_current_user_async
from service import agent_service
from service import agent_async_service
from service.agent_templates import create_user_template, delete_user_template, list_templates_for_user
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

class AgentCloneRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)

class AgentTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    model_name: str = Field(default="glm-4", max_length=100)
    role: Optional[str] = Field(default="")
    task: Optional[str] = Field(default="")
    constraints: Optional[str] = Field(default="")
    output: Optional[str] = Field(default="")
    rag_enabled: int = Field(default=0, ge=0, le=1)
    memory_enabled: int = Field(default=1, ge=0, le=1)
    temperature: int = Field(default=70, ge=0, le=100)
    skill_names: List[str] = Field(default=[])

@router.get("/templates", summary="查询内置Agent模板")
def list_templates(
        current_user: User = Depends(get_current_user_async)):
    """返回内置和用户自定义Agent模板，前端用于一键预填创建表单。"""
    return list_templates_for_user(current_user.id)

@router.post("/templates", summary="保存自定义Agent模板")
def create_template(
        data: AgentTemplateCreate,
        current_user: User = Depends(get_current_user)):
    return create_user_template(current_user.id, data.model_dump())

@router.delete("/templates/{template_id}", summary="删除自定义Agent模板")
def delete_template(
        template_id: str,
        current_user: User = Depends(get_current_user)):
    if not template_id.startswith("custom_"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="内置模板不能删除")
    if not delete_user_template(current_user.id, template_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="模板不存在或无权限")
    return {"message": "删除成功", "template_id": template_id}

@router.get("/list",summary="查询用户的智能体列表",response_model=List[AgentWithSelectedResponse])
async def list_agents(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async)):
    """查询用户的智能体列表，每个智能体附带 is_selected 标记"""
    return await agent_async_service.list_agent(async_db, current_user)
@router.get("/selected/me",summary="获取选中智能体")
async def get_selected(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async)
):
    return await agent_async_service.get_selected(async_db, current_user)
@router.get("/{agent_id:int}",summary="查询单个智能体信息",response_model=AgentWithSelectedResponse)
async def get_agent(
        agent_id:int,
        async_db=Depends(get_async_db),
        current_user: User =Depends(get_current_user_async) ):
    result = await agent_async_service.get_agent(async_db, current_user, agent_id)
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

@router.post("/{agent_id:int}/clone", summary="复制Agent")
def clone_agent(
        agent_id: int,
        data: AgentCloneRequest = AgentCloneRequest(),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)):
    result = agent_service.clone(db, current_user, agent_id, name=data.name)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限复制")
    if "agent_id" not in result:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result.get("message", "复制失败"))
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
        temperature=agent.temperature,
        skill_ids=agent.skill_ids,
    )
    if "agent_id" not in result:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result.get("message", "创建失败"))
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
        temperature=agent_update.temperature,
        skill_ids=agent_update.skill_ids,
    )
    if update_result.get("message") != "更新成功":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=update_result.get("message", "更新失败"))
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
