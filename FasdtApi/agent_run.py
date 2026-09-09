
from fastapi import APIRouter, Depends
from service.exceptions import NotFound
from models.async_db import get_async_db
from models.init_db import User
from service import agent_run_async_service
from service.dependencies import get_current_user_async
from typing import Optional


router = APIRouter(prefix="/run", tags=["Agent运行轨迹"])


@router.get("/{agent_id}/list", summary="查看Agent运行历史（支持按会话过滤）")
async def list_runs(
        agent_id: int,
        limit: int = 20,
        conversation_id: Optional[int] = None,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    """支持会话隔离：传 conversation_id 只返回该会话下的运行记录"""
    result = await agent_run_async_service.list_runs(
        async_db,
        current_user.id,
        agent_id,
        limit=limit,
        conversation_id=conversation_id,
    )
    if result is None:
        raise NotFound("智能体不存在或无权限")
    return result

@router.get("/{run_id}/steps", summary="查看运行详细步骤")
async def get_steps(
        run_id: int,
        full: int = 0,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    result = await agent_run_async_service.get_steps(async_db, current_user.id, run_id, full=full)
    if not result:
        raise NotFound("运行记录不存在")
    return result
