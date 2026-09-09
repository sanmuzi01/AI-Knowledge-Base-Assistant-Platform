from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from service.exceptions import InvalidInput, NotFound
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.init_db import User, get_db
from service.access_control import get_owned_agent, get_owned_knowledge, get_owned_space
from service.dependencies import get_current_user_async
from service.evaluation.rag_eval_service import evaluate_rag_dataset, run_for_space
from utils.rate_limit import LimitExceeded, concurrency_guard, require_limit


router = APIRouter(prefix="/evaluation", tags=["评估"])

# 迁移边界：端点是 async def，但 db 仍用同步 get_db。
# evaluate_rag_dataset -> rag_service.async_search 内部注释已说明：向量化用异步
# HTTP 客户端，ChromaDB 和 SQLAlchemy DAO 仍是同步调用。换 AsyncSession 会直接
# 打断 _build_search_results。待 RAG 检索管线整体 async 化后再迁。


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
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_async),
):
    agent = get_owned_agent(db, current_user.id, agent_id)
    if not agent:
        raise NotFound("智能体不存在或无权限")

    knowledge_ids = [data.knowledge_id] if data.knowledge_id is not None else []
    knowledge_ids.extend([case.knowledge_id for case in data.cases if case.knowledge_id is not None])
    for item in set(knowledge_ids):
        doc = get_owned_knowledge(db, current_user.id, item, agent_id=agent_id)
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
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user_async),
):
    if get_owned_space(db, current_user.id, space_id) is None:
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
