"""
聊天对话路由层
接口：
  POST /chat/{agent_id}                  同步对话（兼容旧版 + conversation_id 可选）
  POST /chat/{agent_id}/stream           SSE 流式对话（兼容旧版 + conversation_id 可选）
  GET  /chat/{agent_id}/history          旧版（查询Chat表），保留向后兼容

迁移边界：整个 chat 路由已收口到 AsyncSession（阶段 2/3）——
  - history 纯读            → get_async_db + chat_async_service
  - POST /chat/{id}         → get_async_db → chat_service.chat_with_agent → run_with_history_async
  - POST /chat/{id}/stream  → get_async_db → chat_service.chat_with_agent_stream_async
                              → run_stream_with_history_async（LangGraph 同步流经 worker 线程 + Queue 桥回）
ReAct 引擎（含 ToolExecutor 装配）整段跑在 asyncio.to_thread + 自带同步 Session。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from service.exceptions import InvalidInput, PermissionDenied
from pydantic import BaseModel, Field
from typing import Optional
from models.async_db import get_async_db
from models.init_db import User
from service.dependencies import get_current_user_async
from service import chat_async_service, chat_service, quota_service
from fastapi.responses import StreamingResponse
from service.runtime.sse_events import SSE_HEADERS
from utils.rate_limit import LimitExceeded, concurrency_guard, require_limit

router = APIRouter(prefix="/chat", tags=["聊天对话"])

class ChatRequest(BaseModel):
    """对话请求体
    :param message: 用户消息（必填）
    :param conversation_id: 会话ID（可选）
        None = 自动新建会话，向后兼容旧调用方
        有值 = 复用已有会话，追加消息 + 历史上下文
    """
    message: str = Field(min_length=1, max_length=5000)
    conversation_id: Optional[int] = Field(default=None, ge=1)


def _limit_error(exc: LimitExceeded) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=exc.message,
        headers={"Retry-After": str(exc.retry_after)},
    )


@router.post("/{agent_id}", summary="发送对话（同步）")
async def chat(
        agent_id: int,
        request: ChatRequest,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    """同步对话。conversation_id=None 时自动新建会话并返回 conversation_id。"""
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
    quota_before = await quota_service.enforce_quota_async(db, current_user.id)
    try:
        with concurrency_guard(
            key=f"agent_run:user:{current_user.id}",
            limit_env="USER_MAX_CONCURRENT_AGENT_RUNS",
            default_limit=2,
            ttl_env="AGENT_RUN_CONCURRENCY_TTL_SECONDS",
            default_ttl=300,
            label="Agent",
        ):
            result =  await chat_service.chat_with_agent(
                db=db,
                user=current_user,
                agent_id=agent_id,
                user_message=request.message,
                conversation_id=request.conversation_id,
            )
    except LimitExceeded as e:
        raise _limit_error(e)
    except ValueError as e:
        raise PermissionDenied(str(e))
    if "message" in result and "answer" not in result:
        raise InvalidInput(result["message"])
    await quota_service.check_and_notify_threshold_async(db, current_user.id, quota_before["used_tokens"])
    return result

@router.post("/{agent_id}/stream", summary="发送对话（SSE流式）")
async def chat_stream(
        agent_id: int,
        request: ChatRequest,
        db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    """SSE 流式对话（阶段 3：AsyncSession + 异步生成器）。conversation_id=None 时自动新建会话。
    事务：路由层不统一 commit，chat_service 内部每步 flush、存 AI 消息后 commit 一次；
    LangGraph 同步流经 worker 线程 + asyncio.Queue 桥回。
    """
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
    quota_before = await quota_service.enforce_quota_async(db, current_user.id)
    try:
        lease_guard = concurrency_guard(
            key=f"agent_run:user:{current_user.id}",
            limit_env="USER_MAX_CONCURRENT_AGENT_RUNS",
            default_limit=2,
            ttl_env="AGENT_RUN_CONCURRENCY_TTL_SECONDS",
            default_ttl=300,
            label="Agent",
        )
        lease_guard.__enter__()
    except LimitExceeded as e:
        raise _limit_error(e)

    generator = chat_service.chat_with_agent_stream_async(
        db=db,
        user=current_user,
        agent_id=agent_id,
        user_message=request.message,
        conversation_id=request.conversation_id,
    )

    async def limited_generator():
        try:
            async for event in generator:
                yield event
        finally:
            try:
                await generator.aclose()
            finally:
                lease_guard.__exit__(None, None, None)
            await quota_service.check_and_notify_threshold_async(db, current_user.id, quota_before["used_tokens"])

    return StreamingResponse(
        limited_generator(),
        headers=SSE_HEADERS,
        media_type="text/event-stream",
    )

@router.get("/{agent_id}/history", summary="获取对话历史（旧版Chat表，兼容）")
async def get_history(
        agent_id: int,
        async_db=Depends(get_async_db),
        current_user: User = Depends(get_current_user_async),
):
    """旧版历史（从Chat表查），保留向后兼容。新版请用：
    GET /conversation/{agent_id} → 会话列表
    GET /conversation/{conversation_id}/messages → 消息历史
    """
    return await chat_async_service.list_legacy_history(async_db, current_user.id, agent_id, limit=20)
