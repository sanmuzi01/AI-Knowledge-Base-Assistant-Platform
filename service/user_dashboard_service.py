from utils.timeutil import utcnow
from datetime import timedelta
from typing import Dict, List

from sqlalchemy import func

from models.init_db import Agent, AgentRun, BackgroundTask, Conversation, Knowledge, LLMConfig, Memory, Message, Skill, UserProfile


def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _count(db, model, user_id: int) -> int:
    return db.query(func.count(model.id)).filter(model.user_id == user_id).scalar() or 0


def _status_counts(db, model, user_id: int) -> Dict[str, int]:
    return {
        status or "unknown": int(count or 0)
        for status, count in (
            db.query(model.status, func.count(model.id))
            .filter(model.user_id == user_id)
            .group_by(model.status)
            .all()
        )
    }


def _list_recent_runs(db, user_id: int, limit: int = 6) -> List[Dict]:
    rows = (
        db.query(AgentRun, Agent.name.label("agent_name"))
        .join(Agent, AgentRun.agent_id == Agent.id)
        .filter(AgentRun.user_id == user_id, Agent.user_id == user_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
        .all()
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
        for run, agent_name in rows
    ]


def _list_recent_tasks(db, user_id: int, limit: int = 5) -> List[Dict]:
    tasks = (
        db.query(BackgroundTask)
        .filter(BackgroundTask.user_id == user_id)
        .order_by(BackgroundTask.created_at.desc())
        .limit(limit)
        .all()
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
        for task in tasks
    ]


def _build_recommendations(
    *,
    agent_count: int,
    ready_agent_count: int,
    chat_model_count: int,
    embedding_model_count: int,
    knowledge_done_count: int,
    skill_count: int,
    profile_ready: bool,
    failed_tasks: int,
    failed_runs_7d: int,
) -> List[Dict]:
    items = []
    if chat_model_count == 0:
        items.append({
            "key": "connect-chat-model",
            "level": "danger",
            "title": "先连接聊天模型",
            "description": "没有聊天模型 API Key 时，助手无法稳定回答问题。",
            "action_path": "/llm-configs",
            "action_text": "连接模型",
        })
    if agent_count == 0:
        items.append({
            "key": "create-agent",
            "level": "warn",
            "title": "创建第一个助手",
            "description": "助手会承载角色、模型、资料库和 Skill，是用户真正开始使用的平台入口。",
            "action_path": "/agents",
            "action_text": "创建助手",
        })
    if agent_count > 0 and ready_agent_count == 0:
        items.append({
            "key": "fix-agent",
            "level": "danger",
            "title": "补齐助手配置",
            "description": "已有助手但没有可直接使用的助手，请检查模型连接或资料库向量模型。",
            "action_path": "/agents",
            "action_text": "检查助手",
        })
    if embedding_model_count == 0:
        items.append({
            "key": "connect-embedding",
            "level": "warn",
            "title": "连接知识库向量模型",
            "description": "上传文档、网页抓取和 RAG 检索都需要向量模型支持。",
            "action_path": "/llm-configs",
            "action_text": "配置向量模型",
        })
    if knowledge_done_count == 0 and agent_count > 0:
        items.append({
            "key": "add-knowledge",
            "level": "info",
            "title": "添加个人资料",
            "description": "让助手可以基于你的文档和网页内容回答，而不是只靠通用模型。",
            "action_path": "/agents",
            "action_text": "进入资料库",
        })
    if skill_count == 0:
        items.append({
            "key": "install-skill",
            "level": "info",
            "title": "安装或创建 Skill",
            "description": "Skill 可以沉淀固定流程、工具权限和回答规则，适合把常用工作变成能力。",
            "action_path": "/skills",
            "action_text": "打开能力库",
        })
    if not profile_ready:
        items.append({
            "key": "complete-profile",
            "level": "info",
            "title": "完善 AI 个性化画像",
            "description": "填写职业、偏好和回答风格后，所有助手都会更贴近你的使用习惯。",
            "action_path": "/settings",
            "action_text": "完善画像",
        })
    if failed_tasks > 0:
        items.append({
            "key": "failed-tasks",
            "level": "warn",
            "title": "处理失败的后台任务",
            "description": f"当前有 {failed_tasks} 个失败任务，可能影响资料入库或索引重建。",
            "action_path": "/tasks",
            "action_text": "查看任务",
        })
    if failed_runs_7d > 0:
        items.append({
            "key": "failed-runs",
            "level": "warn",
            "title": "排查近期对话失败",
            "description": f"最近 7 天有 {failed_runs_7d} 次助手运行失败，建议查看调试页和模型配置。",
            "action_path": "/agents",
            "action_text": "查看助手",
        })
    return items[:6]


def get_user_dashboard(db, user_id: int) -> Dict:
    agents = db.query(Agent).filter(Agent.user_id == user_id).all()
    configs = db.query(LLMConfig).filter(LLMConfig.user_id == user_id, LLMConfig.is_active == 1).all()
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
    run_status = _status_counts(db, AgentRun, user_id)
    task_status = _status_counts(db, BackgroundTask, user_id)
    knowledge_status = _status_counts(db, Knowledge, user_id)
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    profile_ready = bool(profile and (
        (profile.occupation or "").strip()
        or (profile.preferences or "").strip()
        or (profile.auto_summary or "").strip()
    ))
    total_messages = (
        db.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id)
        .scalar() or 0
    )
    total_tokens = (
        db.query(func.coalesce(func.sum(AgentRun.total_tokens), 0))
        .filter(AgentRun.user_id == user_id)
        .scalar() or 0
    )
    failed_runs_7d = (
        db.query(func.count(AgentRun.id))
        .filter(AgentRun.user_id == user_id, AgentRun.status == "failed", AgentRun.started_at >= seven_days_ago)
        .scalar() or 0
    )

    counts = {
        "agents": len(agents),
        "ready_agents": ready_agent_count,
        "llm_configs": len(configs),
        "chat_models": chat_model_count,
        "embedding_models": embedding_model_count,
        "skills": _count(db, Skill, user_id),
        "knowledge_docs": _count(db, Knowledge, user_id),
        "knowledge_done": knowledge_status.get("done", 0),
        "conversations": _count(db, Conversation, user_id),
        "messages": int(total_messages),
        "runs": _count(db, AgentRun, user_id),
        "tasks": _count(db, BackgroundTask, user_id),
        "memories": _count(db, Memory, user_id),
        "tokens": int(total_tokens or 0),
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
        failed_runs_7d=int(failed_runs_7d or 0),
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
        "recent_runs": _list_recent_runs(db, user_id),
        "recent_tasks": _list_recent_tasks(db, user_id),
        "recommendations": recommendations,
    }

