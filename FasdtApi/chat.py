"""
聊天对话路由层
接口：
  POST /chat/{agent_id}                  同步对话（兼容旧版 + conversation_id 可选）
  POST /chat/{agent_id}/stream           SSE 流式对话（兼容旧版 + conversation_id 可选）
  GET  /chat/{agent_id}/history          旧版（查询Chat表），保留向后兼容
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional
from models.init_db import get_db, User
from service.dependencies import get_current_user
from service import chat_service
from models.chat_dao import list_chats_by_agent
from fastapi.responses import StreamingResponse
from service.runtime.sse_events import SSE_HEADERS

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

@router.post("/{agent_id}", summary="发送对话（同步）")
def chat(
        agent_id: int,
        request: ChatRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """同步对话。conversation_id=None 时自动新建会话并返回 conversation_id。"""
    try:
        result = chat_service.chat_with_agent(
            db=db,
            user=current_user,
            agent_id=agent_id,
            user_message=request.message,
            conversation_id=request.conversation_id,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    if "message" in result and "answer" not in result:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result["message"])
    db.commit()   # chat_service 内部用了 flush，这里统一 commit（含消息和会话标题）
    return result

@router.post("/{agent_id}/stream", summary="发送对话（SSE流式）")
def chat_stream(
        agent_id: int,
        request: ChatRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """SSE 流式对话。conversation_id=None 时自动新建会话。
    事务：流式无法像同步那样在路由层统一 commit，所以 chat_service 内部每步 flush，
    保存AI消息后会 commit 一次。
    """
    generator = chat_service.chat_with_agent_stream(
        db=db,
        user=current_user,
        agent_id=agent_id,
        user_message=request.message,
        conversation_id=request.conversation_id,
    )
    return StreamingResponse(
        generator,
        headers=SSE_HEADERS,
        media_type="text/event-stream",
    )

@router.get("/{agent_id}/history", summary="获取对话历史（旧版Chat表，兼容）")
def get_history(
        agent_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """旧版历史（从Chat表查），保留向后兼容。新版请用：
    GET /conversation/{agent_id} → 会话列表
    GET /conversation/{conversation_id}/messages → 消息历史
    """
    chats = list_chats_by_agent(db, current_user.id, agent_id, limit=20)
    return [
        {
            "id": c.id,
            "question": c.question,
            "answer": c.answer,
            "create_time": c.create_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        for c in reversed(chats)
    ]