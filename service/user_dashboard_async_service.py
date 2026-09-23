"""用户工作台异步服务。"""

from utils.timeutil import utcnow
from datetime import timedelta
from typing import Dict, List

from sqlalchemy import func, select

from models.init_db import Agent, AgentRun, BackgroundTask, Conversation, Knowledge, LLMConfig, Memory, Message, Skill, UserProfile
from service.user_dashboard_service import _build_recommendations


def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


async def _count(db, model, user_id: int) -> int:
    result = await db.execute(select(func.count(model.id)).where(model.user_id == user_id))
    return int(result.scalar() or 0)


async def _status_counts(db, model, user_id: int) -> Dict[str, int]:
    result = await db.execute(
        select(model.status, func.count(model.id))
        .where(model.user_id == user_id)
        .group_by(model.status)
    )
    return {status or "unknown": int(count or 0) for status, count in result.all()}


async def _list_recent_runs(db, user_id: int, limit: int = 6) -> List[Dict]:
    result = await db.execute(
        select(AgentRun, Agent.name.label("agent_name"))
        .join(Agent, AgentRun.agent_id == Agent.id)
        .where(AgentRun.user_id == user_id, Agent.user_id == user_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": run.id,
            "agent_id": run.agent_id,
            "agent_name": agent_name,
            "status": run.status,
            "question": run.user_message,
            "answer_preview": (run.final_answer or run.error_msg or "")[:160],
            "total_steps": run.total_steps or 0,
            "total_tokens": run.total_tokens or 0,
            "started_at": _format_dt(run.started_at),
            "finished_at": _format_dt(run.finished_at),
        }
        for run, agent_name in result.all()
    ]


async def _list_recent_tasks(db, user_id: int, limit: int = 5) -> List[Dict]:
    result = await db.execute(
        select(BackgroundTask)
        .where(BackgroundTask.user_id == user_id)
        .order_by(BackgroundTask.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": task.id,
            "agent_id": task.agent_id,
            "task_type": task.task_type,
            "title": task.title,
            "status": task.status,
            "progress": task.progress or 0,
            "error_msg": task.error_msg,
            "created_at": _format_dt(task.created_at),
        }
        for task in result.scalars().all()
    ]


async def get_user_dashboard(db, user_id: int) -> Dict:
    """异步查询当前用户工作台概览。"""

    agents_result = await db.execute(select(Agent).where(Agent.user_id == user_id))
    configs_result = await db.execute(
        select(LLMConfig).where(LLMConfig.user_id == user_id, LLMConfig.is_active == 1)
    )
    agents = list(
        agents_result.unique().scalars().all()
    )
    configs = list(configs_result.scalars().all())

    configured_models = {config.model_name.strip().lower() for config in configs}
    embedding_model_count = len([
        name for name in configured_models
        if "embedding" in name or name.startswith("baai/") or name == "glm-4"
    ])
    chat_model_count = max(0, len(configured_models) - len([
        name for name in configured_models if "embedding" in name or name.startswith("baai/")
    ]))

    ready_agent_count = 0
    for agent in agents:
        model_ready = (agent.model_name or "").strip().lower() in configured_models
        rag_ready = agent.rag_enabled != 1 or embedding_model_count > 0
        if model_ready and rag_ready:
            ready_agent_count += 1

    now = utcnow()
    seven_days_ago = now - timedelta(days=7)
    run_status = await _status_counts(db, AgentRun, user_id)
    task_status = await _status_counts(db, BackgroundTask, user_id)
    knowledge_status = await _status_counts(db, Knowledge, user_id)

    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = profile_result.scalars().first()
    profile_ready = bool(profile and (
        (profile.occupation or "").strip()
        or (profile.preferences or "").strip()
        or (profile.auto_summary or "").strip()
    ))

    total_messages_result = await db.execute(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
    )
    total_tokens_result = await db.execute(
        select(func.coalesce(func.sum(AgentRun.total_tokens), 0))
        .where(AgentRun.user_id == user_id)
    )
    failed_runs_7d_result = await db.execute(
        select(func.count(AgentRun.id))
        .where(
            AgentRun.user_id == user_id,
            AgentRun.status == "failed",
            AgentRun.started_at >= seven_days_ago,
        )
    )

    counts = {
        "agents": len(agents),
        "ready_agents": ready_agent_count,
        "llm_configs": len(configs),
        "chat_models": chat_model_count,
        "embedding_models": embedding_model_count,
        "skills": await _count(db, Skill, user_id),
        "knowledge_docs": await _count(db, Knowledge, user_id),
        "knowledge_done": knowledge_status.get("done", 0),
        "conversations": await _count(db, Conversation, user_id),
        "messages": int(total_messages_result.scalar() or 0),
        "runs": await _count(db, AgentRun, user_id),
        "tasks": await _count(db, BackgroundTask, user_id),
        "memories": await _count(db, Memory, user_id),
        "tokens": int(total_tokens_result.scalar() or 0),
    }
    recommendations = _build_recommendations(
        agent_count=counts["agents"],
        ready_agent_count=ready_agent_count,
        chat_model_count=chat_model_count,
        embedding_model_count=embedding_model_count,
        knowledge_done_count=counts["knowledge_done"],
        skill_count=counts["skills"],
        profile_ready=profile_ready,
        failed_tasks=task_status.get("failed", 0),
        failed_runs_7d=int(failed_runs_7d_result.scalar() or 0),
    )
    health_score = 100 - sum({"danger": 25, "warn": 14, "info": 6}.get(item["level"], 0) for item in recommendations)
    health_score = max(0, min(100, health_score))

    return {
        "counts": counts,
        "status": {
            "runs": run_status,
            "tasks": task_status,
            "knowledge": knowledge_status,
            "profile_ready": profile_ready,
            "health_score": health_score,
        },
        "recent_runs": await _list_recent_runs(db, user_id),
        "recent_tasks": await _list_recent_tasks(db, user_id),
        "recommendations": recommendations,
    }
