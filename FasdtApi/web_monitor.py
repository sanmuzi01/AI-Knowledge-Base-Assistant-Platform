from typing import Optional

from fastapi import APIRouter, Depends
from service.exceptions import NotFound
from pydantic import BaseModel, Field

from models.async_db import get_async_db
from models.init_db import User
from service import web_monitor_async_service
from service.dependencies import get_current_user_async

router = APIRouter(prefix="/web-monitor", tags=["网页监控"])


class WebMonitorCreateRequest(BaseModel):
    name: str = Field(default="", max_length=120)
    url: str = Field(min_length=4, max_length=1000)
    interval_minutes: int = Field(default=30, ge=5, le=1440)
    agent_id: Optional[int] = None


class WebMonitorUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    url: Optional[str] = Field(default=None, min_length=4, max_length=1000)
    interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    is_active: Optional[bool] = None
    agent_id: Optional[int] = None


@router.get("", summary="查询当前用户网页监控项")
async def list_monitors(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await web_monitor_async_service.list_user_monitors(async_db, current_user.id)


@router.post("", summary="创建网页监控项")
async def create_monitor(
        data: WebMonitorCreateRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await web_monitor_async_service.create_monitor(async_db, current_user.id, data.model_dump())


@router.patch("/{monitor_id}", summary="更新网页监控项")
async def update_monitor(
        monitor_id: int,
        data: WebMonitorUpdateRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    monitor = await web_monitor_async_service.update_monitor(
        async_db,
        current_user.id,
        monitor_id,
        data.model_dump(exclude_unset=True),
    )
    if not monitor:
        raise NotFound("网页监控项不存在或无权限")
    return monitor


@router.post("/{monitor_id}/check", summary="立即检查网页监控项")
async def check_monitor(
        monitor_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    monitor = await web_monitor_async_service.check_monitor(async_db, current_user.id, monitor_id)
    if not monitor:
        raise NotFound("网页监控项不存在或无权限")
    return monitor


@router.delete("/{monitor_id}", summary="删除网页监控项")
async def delete_monitor(
        monitor_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    ok = await web_monitor_async_service.delete_monitor(async_db, current_user.id, monitor_id)
    if not ok:
        raise NotFound("网页监控项不存在或无权限")
    return {"message": "删除成功"}
