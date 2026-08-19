
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models.init_db import get_db, User
from service.dependencies import get_current_user
from models.agent_run_dao import list_runs_by_agent, list_steps_by_run
from service.access_control import get_owned_agent, get_owned_run
from typing import Optional


router = APIRouter(prefix="/run", tags=["Agent运行轨迹"])


@router.get("/{agent_id}/list", summary="查看Agent运行历史（支持按会话过滤）")
def list_runs(
        agent_id: int,
        limit: int = 20,
        conversation_id: Optional[int] = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """支持会话隔离：传 conversation_id 只返回该会话下的运行记录"""
    agent = get_owned_agent(db, current_user.id, agent_id)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="智能体不存在或无权限")

    runs = list_runs_by_agent(db, agent_id, limit=limit, conversation_id=conversation_id)
    return [
        {
            "id": r.id,
            "agent_id": r.agent_id,
            "conversation_id": r.conversation_id,
            "user_message": r.user_message,
            "status": r.status,
            "total_steps": r.total_steps,
            "final_answer": r.final_answer[:200] + "..." if r.final_answer and len(r.final_answer) > 200 else r.final_answer,
            "error_msg": r.error_msg,
            "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else None,
            "finished_at": r.finished_at.strftime("%Y-%m-%d %H:%M:%S") if r.finished_at else None,
        }
        for r in runs
    ]

@router.get("/{run_id}/steps", summary="查看运行详细步骤")
def get_steps(
        run_id: int,
        full: int = 0,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    # 先查run存不存在
    run = get_owned_run(db, current_user.id, run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="运行记录不存在")

    def maybe_truncate(value: str, limit: int = 300):
        if value is None or full == 1:
            return value
        return value[:limit] + "..." if len(value) > limit else value

    steps = list_steps_by_run(db, run_id)
    return {
        "run_id": run_id,
        "status": run.status,
        "user_message": run.user_message,
        "final_answer": run.final_answer,
        "total_steps": run.total_steps,
        "started_at": run.started_at.strftime("%Y-%m-%d %H:%M:%S") if run.started_at else None,
        "finished_at": run.finished_at.strftime("%Y-%m-%d %H:%M:%S") if run.finished_at else None,
        "steps": [
            {
                "step_no": s.step_no,
                "step_type": s.step_type,
                "thought": s.thought,
                "tool_name": s.tool_name,
                "tool_args": s.tool_args,
                "tool_result": maybe_truncate(s.tool_result),
                "tokens": s.tokens,
                "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else None,
            }
            for s in steps
        ]
    }
