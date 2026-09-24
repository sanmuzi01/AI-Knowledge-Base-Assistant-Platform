from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from service.exceptions import InvalidInput, NotFound
from pydantic import BaseModel, Field

from models.async_db import get_async_db
from models.init_db import User
from service.access_control import get_owned_agent_async, get_owned_knowledge_async, get_owned_space_async
from service.dependencies import get_current_user_async
from service.evaluation.rag_eval_service import evaluate_rag_dataset, run_for_space
from service.evaluation import eval_set_service
from utils.rate_limit import LimitExceeded, concurrency_guard, require_limit


router = APIRouter(prefix="/evaluation", tags=["评估"])

# Phase 3 收尾（docs/sync-async-boundary.md）：整条路由已经全量 AsyncSession。
# evaluate_rag_dataset 走 rag_service.search_async（原生 async，不再是向量化 async、
# DAO 反查同步的 rag_service.async_search——那个半异步版本已经退役）。


class RagEvalCase(BaseModel):
    question: str = Field(min_length=1)
    expected_chunk_ids: List[int] = Field(default_factory=list)
    expected_knowledge_ids: List[int] = Field(default_factory=list)
    expected_texts: List[str] = Field(default_factory=list)
    answer: Optional[str] = None
    knowledge_id: Optional[int] = None


class RagEvalRequest(BaseModel):
    cases: List[RagEvalCase] = Field(min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)
    knowledge_id: Optional[int] = None
    text_match_threshold: float = Field(default=0.35, ge=0, le=1)
    faithfulness_threshold: float = Field(default=0.25, ge=0, le=1)
    faithfulness_judge_model: Optional[str] = None


class SpaceRagEvalRequest(BaseModel):
    cases: List[RagEvalCase] = Field(min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)
    rerank: Optional[bool] = None
    text_match_threshold: float = Field(default=0.35, ge=0, le=1)
    faithfulness_threshold: float = Field(default=0.25, ge=0, le=1)


def _limit_error(exc: LimitExceeded) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.message,
        headers={"Retry-After": str(exc.retry_after)},
    )


@router.post("/{agent_id}/rag", summary="评估 RAG 命中率、召回率和忠诚度")
async def evaluate_rag(
        agent_id: int,
        data: RagEvalRequest,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    agent = await get_owned_agent_async(db, current_user.id, agent_id)
    if not agent:
        raise NotFound("智能体不存在或无权限")

    knowledge_ids = [data.knowledge_id] if data.knowledge_id is not None else []
    knowledge_ids.extend([case.knowledge_id for case in data.cases if case.knowledge_id is not None])
    for item in set(knowledge_ids):
        doc = await get_owned_knowledge_async(db, current_user.id, item, agent_id=agent_id)
        if not doc:
            raise NotFound(f"文档不存在或无权限: {item}")
        if doc.is_enabled == 0:
            raise InvalidInput(f"文档已禁用，不参与评估: {item}")

    _rate_limit_rag_eval(current_user.id)

    try:
        with _rag_eval_concurrency(current_user.id):
            return await evaluate_rag_dataset(
                db=db,
                user_id=current_user.id,
                agent_id=agent_id,
                cases=[case.model_dump() for case in data.cases],
                top_k=data.top_k,
                knowledge_id=data.knowledge_id,
                text_match_threshold=data.text_match_threshold,
                faithfulness_threshold=data.faithfulness_threshold,
                faithfulness_judge_model=data.faithfulness_judge_model,
            )
    except LimitExceeded as e:
        raise _limit_error(e)
    except ValueError as e:
        raise InvalidInput(str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"评估失败: {str(e)}")


def _rate_limit_rag_eval(user_id: int) -> None:
    try:
        require_limit(
            key=f"rag_eval:user:{user_id}",
            limit_env="RAG_EVAL_RATE_LIMIT", default_limit=10,
            window_env="RAG_EVAL_RATE_WINDOW_SECONDS", default_window=3600,
            label="RAG评估",
        )
    except LimitExceeded as e:
        raise _limit_error(e)


def _rag_eval_concurrency(user_id: int):
    return concurrency_guard(
        key=f"rag_eval:user:{user_id}",
        limit_env="USER_MAX_CONCURRENT_RAG_EVALS", default_limit=1,
        ttl_env="RAG_EVAL_CONCURRENCY_TTL_SECONDS", default_ttl=600,
        label="RAG评估",
    )


@router.post("/space/{space_id}/rag", summary="按知识库空间评估 RAG（多空间联合检索）")
async def evaluate_space_rag(
        space_id: int,
        data: SpaceRagEvalRequest,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    if await get_owned_space_async(db, current_user.id, space_id) is None:
        raise NotFound("知识库空间不存在或无权限")

    _rate_limit_rag_eval(current_user.id)
    try:
        with _rag_eval_concurrency(current_user.id):
            return await run_for_space(
                user_id=current_user.id,
                space_ids=[space_id],
                cases=[case.model_dump() for case in data.cases],
                top_k=data.top_k,
                rerank=data.rerank,
                text_match_threshold=data.text_match_threshold,
                faithfulness_threshold=data.faithfulness_threshold,
            )
    except LimitExceeded as e:
        raise _limit_error(e)
    except PermissionError as e:
        raise NotFound(str(e) or "知识库空间不存在或无权限")
    except ValueError as e:
        raise InvalidInput(str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"评估失败: {str(e)}")


# ============================================================================
# 固定评估集：建一次问题集，之后随时重跑，自动跟上一轮比对回归/变好的问题
# ============================================================================

class CreateEvalSetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    agent_id: Optional[int] = None
    space_id: Optional[int] = None
    cases: List[RagEvalCase] = Field(min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)
    rerank: Optional[bool] = None
    text_match_threshold: float = Field(default=0.35, ge=0, le=1)
    faithfulness_threshold: float = Field(default=0.25, ge=0, le=1)
    faithfulness_judge_model: Optional[str] = None


@router.post("/sets", summary="创建固定评估集")
async def create_eval_set_route(
        data: CreateEvalSetRequest,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    if data.agent_id is not None and await get_owned_agent_async(db, current_user.id, data.agent_id) is None:
        raise NotFound("智能体不存在或无权限")
    if data.space_id is not None and await get_owned_space_async(db, current_user.id, data.space_id) is None:
        raise NotFound("知识库空间不存在或无权限")

    settings = {
        "top_k": data.top_k,
        "rerank": data.rerank,
        "text_match_threshold": data.text_match_threshold,
        "faithfulness_threshold": data.faithfulness_threshold,
        "faithfulness_judge_model": data.faithfulness_judge_model,
    }
    try:
        return await eval_set_service.create_eval_set(
            db, current_user.id, data.name,
            [case.model_dump() for case in data.cases],
            agent_id=data.agent_id, space_id=data.space_id, settings=settings,
        )
    except ValueError as e:
        raise InvalidInput(str(e))


@router.get("/sets", summary="列出我的固定评估集")
async def list_eval_sets_route(
        agent_id: Optional[int] = None,
        space_id: Optional[int] = None,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    return await eval_set_service.list_eval_sets(db, current_user.id, agent_id=agent_id, space_id=space_id)


@router.get("/sets/{eval_set_id}", summary="查看评估集详情（含问题列表）")
async def get_eval_set_route(
        eval_set_id: int,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    try:
        return await eval_set_service.get_eval_set(db, current_user.id, eval_set_id)
    except ValueError as e:
        raise NotFound(str(e))


@router.delete("/sets/{eval_set_id}", summary="删除评估集（含历史运行记录）")
async def delete_eval_set_route(
        eval_set_id: int,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    try:
        await eval_set_service.delete_eval_set(db, current_user.id, eval_set_id)
    except ValueError as e:
        raise NotFound(str(e))
    return {"message": "删除成功"}


@router.post("/sets/{eval_set_id}/run", summary="跑一次评估集，并和上一轮自动比较")
async def run_eval_set_route(
        eval_set_id: int,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    _rate_limit_rag_eval(current_user.id)
    try:
        with _rag_eval_concurrency(current_user.id):
            return await eval_set_service.run_eval_set(db, current_user.id, eval_set_id)
    except LimitExceeded as e:
        raise _limit_error(e)
    except ValueError as e:
        raise NotFound(str(e))
    except PermissionError as e:
        raise NotFound(str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"评估失败: {str(e)}")


@router.get("/sets/{eval_set_id}/runs", summary="评估集历史运行记录")
async def list_eval_runs_route(
        eval_set_id: int,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    try:
        return await eval_set_service.list_eval_runs(db, current_user.id, eval_set_id)
    except ValueError as e:
        raise NotFound(str(e))
