"""Agent 流水线路由：把多个 Agent 串成一条固定顺序的处理链。

/run 复用和 /chat 一样的限流桶和并发守卫——流水线本质是连续跑好几次聊天，
不应该绕开"聊天请求"的既有节流配置，另开一套等于给用户留了个绕过限流的后门。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from models.async_db import get_async_db
from models.init_db import User
from service import agent_pipeline_service
from service.dependencies import get_current_user_async
from utils.rate_limit import LimitExceeded, concurrency_guard, require_limit

router = APIRouter(prefix="/pipelines", tags=["Agent 流水线"])


def _limit_error(exc: LimitExceeded):
    from fastapi import HTTPException, status
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.message,
        headers={"Retry-After": str(exc.retry_after)},
    )


class PipelineStep(BaseModel):
    agent_id: int
    label: Optional[str] = Field(default=None, max_length=60)


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    steps: List[PipelineStep]


class PipelineUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    steps: Optional[List[PipelineStep]] = None
    is_enabled: Optional[bool] = None


class PipelineRun(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


@router.get("", summary="列出我的 Agent 流水线")
async def list_pipelines(
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await agent_pipeline_service.list_pipelines_async(async_db, current_user.id)


@router.post("", summary="新建 Agent 流水线")
async def create_pipeline(
        data: PipelineCreate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await agent_pipeline_service.create_pipeline_async(
        async_db, current_user.id, data.name, data.description,
        [s.model_dump() for s in data.steps],
    )


@router.patch("/{pipeline_id}", summary="更新 Agent 流水线")
async def update_pipeline(
        pipeline_id: int,
        data: PipelineUpdate,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    patch: Dict[str, Any] = data.model_dump(exclude_unset=True)
    if "steps" in patch and patch["steps"] is not None:
        patch["steps"] = [dict(s) for s in patch["steps"]]
    return await agent_pipeline_service.update_pipeline_async(async_db, current_user.id, pipeline_id, patch)


@router.delete("/{pipeline_id}", summary="删除 Agent 流水线")
async def delete_pipeline(
        pipeline_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await agent_pipeline_service.delete_pipeline_async(async_db, current_user.id, pipeline_id)


@router.post("/{pipeline_id}/run", summary="按顺序跑一次流水线")
async def run_pipeline(
        pipeline_id: int,
        data: PipelineRun,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    try:
        require_limit(
            key=f"chat:user:{current_user.id}",
            limit_env="CHAT_RATE_LIMIT",
            default_limit=20,
            window_env="CHAT_RATE_WINDOW_SECONDS",
            default_window=60,
            label="聊天请求",
        )
    except LimitExceeded as e:
        raise _limit_error(e)
    try:
        with concurrency_guard(
            key=f"agent_run:user:{current_user.id}",
            limit_env="USER_MAX_CONCURRENT_AGENT_RUNS",
            default_limit=2,
            ttl_env="AGENT_RUN_CONCURRENCY_TTL_SECONDS",
            default_ttl=300,
            label="Agent",
        ):
            return await agent_pipeline_service.run_pipeline_async(
                async_db, current_user, pipeline_id, data.message,
            )
    except LimitExceeded as e:
        raise _limit_error(e)
