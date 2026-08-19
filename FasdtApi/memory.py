from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.init_db import User, get_db
from service.dependencies import get_current_user
from service.memory import memory_service

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
def list_memories(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = memory_service.list_agent_memories(db, current_user.id, agent_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限")
    return result


@router.post("/agent/{agent_id:int}", summary="手动添加长期记忆", response_model=MemoryResponse)
def create_memory(
    agent_id: int,
    data: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = memory_service.add_memory(db, current_user.id, agent_id, data.memory_type, data.content)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限")
    db.commit()
    return result


@router.put("/{memory_id:int}", summary="编辑长期记忆", response_model=MemoryResponse)
def update_memory(
    memory_id: int,
    data: MemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.memory_type is None and data.content is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="没有可更新的字段")
    try:
        result = memory_service.edit_memory(
            db,
            current_user.id,
            memory_id,
            memory_type=data.memory_type,
            content=data.content,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="记忆不存在或无权限")
    db.commit()
    return result


@router.delete("/{memory_id:int}", summary="删除一条长期记忆")
def delete_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not memory_service.remove_memory(db, current_user.id, memory_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="记忆不存在或无权限")
    db.commit()
    return {"message": "删除成功"}


@router.delete("/agent/{agent_id:int}", summary="清空Agent长期记忆")
def clear_memories(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = memory_service.clear_agent_memories(db, current_user.id, agent_id)
    if count is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限")
    db.commit()
    return {"message": "清空成功", "count": count}
