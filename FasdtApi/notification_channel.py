"""外部告警推送通道路由。

route -> service.notification_service -> models.notification_channel_async_dao
全部 async，全部按当前登录用户隔离。
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from models.async_db import get_async_db
from models.init_db import User
from service import notification_service
from service.dependencies import get_current_user_async

router = APIRouter(prefix="/notification-channels", tags=["告警通知"])


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    webhook_url: str = Field(min_length=1, max_length=1000)


class ChannelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    webhook_url: Optional[str] = Field(default=None, max_length=1000)
    is_enabled: Optional[bool] = None


@router.get("", summary="查询我的告警通知通道")
async def list_channels(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await notification_service.list_channels(async_db, current_user.id)


@router.post("", summary="新增告警通知通道（Webhook）")
async def create_channel(
        data: ChannelCreate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await notification_service.create_channel(async_db, current_user.id, data.name, data.webhook_url)


@router.patch("/{channel_id}", summary="更新告警通知通道")
async def update_channel(
        channel_id: int,
        data: ChannelUpdate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await notification_service.update_channel(
        async_db, current_user.id, channel_id, data.model_dump(exclude_unset=True),
    )


@router.delete("/{channel_id}", summary="删除告警通知通道")
async def delete_channel(
        channel_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await notification_service.delete_channel(async_db, current_user.id, channel_id)


@router.post("/{channel_id}/test", summary="发送一条测试通知")
async def test_channel(
        channel_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await notification_service.send_test(async_db, current_user.id, channel_id)
