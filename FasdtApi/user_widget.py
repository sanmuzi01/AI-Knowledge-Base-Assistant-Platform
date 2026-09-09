"""自定义工作台组件路由。

route -> service.widget_async_service -> models.user_widget_async_dao / service.widgets.*
全部 async，全部按当前登录用户隔离。
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from models.async_db import get_async_db
from models.init_db import User
from service import widget_async_service
from service.dependencies import get_current_user_async

router = APIRouter(prefix="/user/widgets", tags=["工作台组件"])


class DesignRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)


class CreateWidgetRequest(BaseModel):
    draft: Dict[str, Any]


class UpdateWidgetRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None
    spec: Optional[Dict[str, Any]] = None


class ImportWidgetRequest(BaseModel):
    payload: Dict[str, Any]


@router.post("/design", summary="用自然语言生成组件草稿")
async def design_widget_route(
        data: DesignRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.design(async_db, current_user, data.prompt)


@router.post("/preview", summary="按草稿真实跑一次（不保存）")
async def preview_widget_route(
        data: CreateWidgetRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.preview_widget(async_db, current_user, data.draft)


@router.post("", summary="根据草稿创建组件")
async def create_widget_route(
        data: CreateWidgetRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.create_widget(async_db, current_user, data.draft)


@router.get("", summary="获取当前用户全部组件")
async def list_widgets_route(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.list_widgets(async_db, current_user.id)


@router.post("/import", summary="从导出的 JSON 导入组件")
async def import_widget_route(
        data: ImportWidgetRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.import_widget(async_db, current_user, data.payload)


@router.get("/{widget_id:int}/export", summary="导出组件配置")
async def export_widget_route(
        widget_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.export_widget(async_db, current_user, widget_id)


@router.patch("/{widget_id:int}", summary="修改组件（名称/显示/排序/配置）")
async def update_widget_route(
        widget_id: int,
        data: UpdateWidgetRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.update_widget(
        async_db, current_user, widget_id, data.model_dump(exclude_unset=True)
    )


@router.delete("/{widget_id:int}", summary="删除组件")
async def delete_widget_route(
        widget_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.delete_widget(async_db, current_user, widget_id)


@router.post("/{widget_id:int}/run", summary="手动运行组件并保存结果")
async def run_widget_route(
        widget_id: int,
        request: Request,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    request_id = request.headers.get("X-Request-ID")
    return await widget_async_service.run_widget_now(async_db, current_user, widget_id, request_id)


@router.get("/{widget_id:int}/data", summary="获取组件最新结果（可含历史序列）")
async def widget_data_route(
        widget_id: int,
        with_series: bool = False,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await widget_async_service.get_widget_data(async_db, current_user, widget_id, with_series)
