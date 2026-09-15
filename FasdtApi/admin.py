from typing import List

from fastapi import APIRouter, Depends, Query
from service.exceptions import NotFound
from pydantic import BaseModel, Field

from models.init_db import User
from models.async_db import get_async_db
from service import admin_async_service, admin_service
from service.dependencies import get_current_admin_user_async
from service import operation_log_async_service

router = APIRouter(prefix="/admin", tags=["管理员后台"])


class UserRolesUpdate(BaseModel):
    roles: List[str] = Field(default_factory=list)


class UserStatusUpdate(BaseModel):
    disabled: bool


class UserPasswordUpdate(BaseModel):
    new_password: str = Field(min_length=6)


@router.get("/me", summary="查询当前管理员信息")
async def admin_me(current_user: User = Depends(get_current_admin_user_async)):
    return admin_service.current_user_payload(current_user)


@router.get("/overview", summary="后台总览统计")
async def admin_overview(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    return await admin_async_service.overview(async_db)


@router.get("/users", summary="用户管控列表")
async def admin_users(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        search: str = Query(default=None, description="按用户名/手机号模糊搜索"),
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    return await admin_async_service.list_users(async_db, limit=limit, offset=offset, search=search)


@router.get("/users/{user_id}", summary="查询用户详情")
async def admin_user_detail(
        user_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    result = await admin_async_service.get_user_detail(async_db, user_id)
    if not result:
        raise NotFound("用户不存在")
    return result


@router.put("/users/{user_id}/roles", summary="更新用户角色")
async def admin_update_user_roles(
        user_id: int,
        data: UserRolesUpdate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    result = await admin_async_service.set_user_roles(async_db, user_id, data.roles, current_user.id)
    if not result:
        raise NotFound("用户不存在")
    return result


@router.patch("/users/{user_id}/status", summary="启用或禁用用户")
async def admin_update_user_status(
        user_id: int,
        data: UserStatusUpdate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    result = await admin_async_service.set_user_disabled(async_db, user_id, data.disabled, current_user.id)
    if not result:
        raise NotFound("用户不存在")
    return result


@router.put("/users/{user_id}/password", summary="重置用户密码")
async def admin_reset_user_password(
        user_id: int,
        data: UserPasswordUpdate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    result = await admin_async_service.reset_user_password(async_db, user_id, data.new_password)
    if not result:
        raise NotFound("用户不存在")
    return result


@router.delete("/users/{user_id}", summary="删除用户")
async def admin_delete_user(
        user_id: int,
        current_user: User = Depends(get_current_admin_user_async),
):
    result = await admin_async_service.delete_user(user_id, current_user.id)
    if not result:
        raise NotFound("用户不存在")
    return result


@router.get("/tasks", summary="查询全局后台任务")
async def admin_tasks(
        limit: int = Query(default=50, ge=1, le=200),
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    return await admin_async_service.list_recent_tasks(async_db, limit=limit)


@router.get("/usage", summary="查询系统使用情况")
async def admin_usage(
        days: int = Query(default=14, ge=1, le=90),
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    return await admin_async_service.usage_stats(async_db, days=days)


@router.get("/knowledge-spaces", summary="企业知识库空间总览")
async def admin_knowledge_spaces(
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    return await admin_async_service.list_knowledge_spaces(async_db, limit=limit, offset=offset)


class AdminSpaceStatusUpdate(BaseModel):
    is_enabled: bool | None = None
    status: str | None = None


@router.patch("/knowledge-spaces/{space_id}", summary="管理员直接改一个空间的启停/归档状态")
async def admin_update_knowledge_space(
        space_id: int,
        data: AdminSpaceStatusUpdate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    return await admin_async_service.admin_update_space(
        async_db, current_user.id, space_id, data.model_dump(exclude_unset=True),
    )


@router.get("/logs", summary="查询操作日志")
async def admin_logs(
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        days: int = Query(default=7, ge=1, le=90),
        keyword: str = Query(default=None),
        method: str = Query(default=None),
        status_group: str = Query(default=None),
        user_id: int = Query(default=None),
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_admin_user_async),
):
    return await operation_log_async_service.list_operation_logs(
        async_db,
        limit=limit,
        offset=offset,
        days=days,
        keyword=keyword,
        method=method,
        status_group=status_group,
        user_id=user_id,
    )
