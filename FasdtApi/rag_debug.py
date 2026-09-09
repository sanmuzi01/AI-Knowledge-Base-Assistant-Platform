"""知识库调试台路由（阶段4）。

route -> service/rag/debug_service.py -> space_search / search_entry + llm_service
        + models/rag_debug_dao.py

- POST /rag-debug/run       跑一次检索快照（可选带 LLM 回答），限流
- POST /rag-debug/samples   把快照存成测试样例
- GET  /rag-debug/samples   我的样例列表（可按 space / 评估集筛）
- PATCH/DELETE /samples/{id} 标注 useful/useless、勾进评估集、删除
- GET  /rag-debug/samples/export  评估集样例 -> rag_eval 的 cases

隔离：全部按当前登录用户；space/agent 归属在 debug_service 内校验（越权 403/404）。
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.async_db import get_async_db
from models.init_db import User, get_db
from service.dependencies import get_current_user_async
from service.rag import debug_service
from utils.rate_limit import LimitExceeded, require_limit

router = APIRouter(prefix="/rag-debug", tags=["知识库调试台"])


def _limit_error(exc: LimitExceeded) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.message,
        headers={"Retry-After": str(exc.retry_after)},
    )


class RagDebugRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    space_ids: List[int] = Field(default_factory=list, max_length=20)
    agent_id: Optional[int] = Field(default=None, ge=1)
    top_k: int = Field(default=5, ge=1, le=20)
    rerank: Optional[bool] = None
    refuse_when_empty: bool = True
    with_answer: bool = False
    model_name: Optional[str] = Field(default=None, max_length=100)


class RagDebugSaveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    result: Dict[str, Any] = Field(default_factory=dict)
    space_ids: List[int] = Field(default_factory=list, max_length=20)
    agent_id: Optional[int] = Field(default=None, ge=1)
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    rerank: Optional[bool] = None
    verdict: Optional[str] = Field(default=None, max_length=10)
    in_eval_set: bool = False


class RagDebugSamplePatch(BaseModel):
    verdict: Optional[str] = Field(default=None, max_length=10)
    in_eval_set: Optional[bool] = None


@router.post("/run", summary="跑一次检索快照（可选带 LLM 回答）")
async def run_debug_route(
        data: RagDebugRunRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_async),
):
    try:
        require_limit(
            key=f"rag_debug:user:{current_user.id}",
            limit_env="RAG_DEBUG_RATE_LIMIT", default_limit=60,
            window_env="RAG_DEBUG_RATE_WINDOW_SECONDS", default_window=3600,
            label="知识库调试",
        )
    except LimitExceeded as e:
        raise _limit_error(e)

    trace = await asyncio.to_thread(
        debug_service.run_retrieval,
        current_user.id,
        query=data.query,
        space_ids=data.space_ids,
        agent_id=data.agent_id,
        top_k=data.top_k,
        rerank=data.rerank,
        refuse_when_empty=data.refuse_when_empty,
    )
    if data.with_answer and data.model_name:
        trace = await debug_service.attach_answer(db, current_user.id, trace, data.model_name)
    return trace


@router.post("/samples", summary="把检索快照存为测试样例")
async def save_sample_route(
        data: RagDebugSaveRequest,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await debug_service.save_sample(async_db, current_user.id, data.model_dump())


@router.get("/samples", summary="我的调试样例")
async def list_samples_route(
        space_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        eval_only: bool = False,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await debug_service.list_samples(
        async_db, current_user.id, space_id=space_id, agent_id=agent_id, eval_only=eval_only,
    )


@router.get("/samples/export", summary="评估集样例导出为 rag_eval cases")
async def export_samples_route(
        space_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await debug_service.export_eval_cases(
        async_db, current_user.id, space_id=space_id, agent_id=agent_id,
    )


@router.patch("/samples/{sample_id:int}", summary="标注样例 / 勾进评估集")
async def patch_sample_route(
        sample_id: int,
        data: RagDebugSamplePatch,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await debug_service.update_sample(
        async_db, current_user.id, sample_id, data.model_dump(exclude_unset=True),
    )


@router.delete("/samples/{sample_id:int}", summary="删除调试样例")
async def delete_sample_route(
        sample_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await debug_service.delete_sample(async_db, current_user.id, sample_id)
