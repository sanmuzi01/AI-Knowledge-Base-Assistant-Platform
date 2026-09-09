from typing import List, Optional

from fastapi import APIRouter, Depends
from service.exceptions import InvalidInput, NotFound
from pydantic import BaseModel, Field

from models.async_db import get_async_db
from models.init_db import User
from service import memory_async_service
from service.dependencies import get_current_user_async

router = APIRouter(prefix="/memory", tags=["memory管理"])


class MemoryResponse(BaseModel):
    id: int
    user_id: int
    agent_id: int
    memory_type: str
    content: str
    chat_count: int
    created_at: Optional[str] = None


class MemoryCreate(BaseModel):
    memory_type: str = Field(default="fact", max_length=20)
    content: str = Field(min_length=1, max_length=5000)


class MemoryUpdate(BaseModel):
    memory_type: Optional[str] = Field(default=None, max_length=20)
    content: Optional[str] = Field(default=None, min_length=1, max_length=5000)


@router.get("/agent/{agent_id:int}", summary="获取Agent长期记忆", response_model=List[MemoryResponse])
async def list_memories(
    agent_id: int,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    result = await memory_async_service.list_agent_memories(async_db, current_user.id, agent_id)
    if result is None:
        raise NotFound("智能体不存在或无权限")
    return result


@router.post("/agent/{agent_id:int}", summary="手动添加长期记忆", response_model=MemoryResponse)
async def create_memory(
    agent_id: int,
    data: MemoryCreate,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    try:
        result = await memory_async_service.add_memory(
            async_db,
            current_user.id,
            agent_id,
            data.memory_type,
            data.content,
        )
    except ValueError as e:
        raise InvalidInput(str(e))
    if result is None:
        raise NotFound("智能体不存在或无权限")
    return result


@router.put("/{memory_id:int}", summary="编辑长期记忆", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    data: MemoryUpdate,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    if data.memory_type is None and data.content is None:
        raise InvalidInput("没有可更新的字段")
    try:
        result = await memory_async_service.edit_memory(
            async_db,
            current_user.id,
            memory_id,
            memory_type=data.memory_type,
            content=data.content,
        )
    except ValueError as e:
        raise InvalidInput(str(e))
    if result is None:
        raise NotFound("记忆不存在或无权限")
    return result


@router.delete("/{memory_id:int}", summary="删除一条长期记忆")
async def delete_memory(
    memory_id: int,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    success = await memory_async_service.remove_memory(async_db, current_user.id, memory_id)
    if not success:
        raise NotFound("记忆不存在或无权限")
    return {"message": "删除成功"}


@router.delete("/agent/{agent_id:int}", summary="清空Agent长期记忆")
async def clear_memories(
    agent_id: int,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    count = await memory_async_service.clear_agent_memories(async_db, current_user.id, agent_id)
    if count is None:
        raise NotFound("智能体不存在或无权限")
    return {"message": "清空成功", "count": count}
