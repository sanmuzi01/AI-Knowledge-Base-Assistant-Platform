"""知识库空间路由。

route -> service/knowledge_space/space_async_service -> models/knowledge_space_async_dao
全部 async，按当前登录用户隔离（get_owned_space_async / user_space_ids_async）。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from models.async_db import get_async_db
from models.init_db import User
from service.dependencies import get_current_user_async
from service.knowledge_space import space_async_service

router = APIRouter(prefix="/knowledge-spaces", tags=["知识库空间"])


class SpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    purpose: Optional[str] = Field(default=None, max_length=60)
    tags: List[str] = Field(default_factory=list)


class SpaceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    purpose: Optional[str] = Field(default=None, max_length=60)
    tags: Optional[List[str]] = None
    is_enabled: Optional[bool] = None
    status: Optional[str] = Field(default=None, max_length=20)


@router.get("", summary="我的知识库空间列表 + 用途目录")
async def list_spaces_route(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await space_async_service.list_spaces(async_db, current_user.id)


@router.post("", summary="创建知识库空间")
async def create_space_route(
        data: SpaceCreate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await space_async_service.create_space(async_db, current_user.id, data.model_dump())


@router.get("/{space_id:int}", summary="知识库空间详情")
async def get_space_route(
        space_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await space_async_service.get_space(async_db, current_user.id, space_id)


@router.patch("/{space_id:int}", summary="修改知识库空间")
async def update_space_route(
        space_id: int,
        data: SpaceUpdate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await space_async_service.update_space(
        async_db, current_user.id, space_id, data.model_dump(exclude_unset=True)
    )


@router.delete("/{space_id:int}", summary="删除知识库空间（空间下无文档时）")
async def delete_space_route(
        space_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await space_async_service.delete_space(async_db, current_user.id, space_id)
