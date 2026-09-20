from fastapi import APIRouter, BackgroundTasks, Depends, Query
from service.exceptions import InvalidInput, NotFound, PermissionDenied

from models.init_db import User
from models.async_db import get_async_db
from service import background_task_async_service, background_task_service
from service.admin_service import is_admin_user
from service.dependencies import get_current_user_async

router = APIRouter(prefix="/task", tags=["后台任务"])


def _require_admin(current_user: User):
    if not is_admin_user(current_user):
        raise PermissionDenied("需要管理员权限")


@router.get("/", summary="查询当前用户后台任务（支持筛选）")
async def list_tasks(
    limit: int = Query(default=30, ge=1, le=200),
    status: str = None,
    task_type: str = None,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    return await background_task_async_service.list_user_tasks(
        async_db, current_user.id, limit=limit, status=status, task_type=task_type
    )


@router.get("/all", summary="管理员查询全局后台任务")
async def list_all_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = 0,
    status: str = None,
    task_type: str = None,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    _require_admin(current_user)
    return await background_task_async_service.list_all_tasks(
        async_db, limit=limit, offset=offset, status=status, task_type=task_type
    )


@router.get("/{task_id}", summary="查询后台任务详情")
async def get_task(
    task_id: int,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    task = await background_task_async_service.get_user_task(async_db, current_user.id, task_id)
    if not task:
        raise NotFound("任务不存在或无权限")
    return task


@router.post("/{task_id}/retry", summary="重试后台任务")
async def retry_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_async),
):
    # 1. 创建重试任务（service 层校验权限 + 状态 + 复制参数）
    new_task = await background_task_async_service.retry_task(
        current_user.id, task_id, is_admin=is_admin_user(current_user)
    )
    if not new_task:
        raise InvalidInput("任务不存在、无权限，或当前状态不允许重试（仅 failed/cancelled 可重试）")
    background_task_service.schedule_task(new_task, background_tasks)
    return {
        "code": 200,
        "msg": "已创建重试任务",
        "data": new_task,
    }


@router.post("/{task_id}/cancel", summary="取消后台任务")
async def cancel_task(
    task_id: int,
    current_user: User = Depends(get_current_user_async),
):
    task = await background_task_async_service.cancel_task(
        current_user.id, task_id, is_admin=is_admin_user(current_user)
    )
    if not task:
        raise InvalidInput("任务不存在、无权限，或当前状态不允许取消（仅 queued 可取消；running 无法中断）")
    return {
        "code": 200,
        "msg": "已取消任务",
        "data": task,
    }
