"""管理员后台异步统计服务。"""

from utils.timeutil import utcnow
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from models.init_db import (
    Agent,
    AgentRun,
    BackgroundTask,
    Chat,
    Conversation,
    Knowledge,
    KnowledgeChunk,
    LLMConfig,
    Memory,
    Message,
    Role,
    Skill,
    User,
)
from service.admin_service import (
    ADMIN_ROLE_NAMES,
    ONLINE_WINDOW_SECONDS,
    _format_dt,
    _user_admin_payload,
    current_user_payload,
)
from service.auth_service import hash_password


async def _count(db, model) -> int:
    result = await db.execute(select(func.count(model.id)))
    return int(result.scalar() or 0)


async def _count_by_user(db, model) -> Dict[int, int]:
    result = await db.execute(select(model.user_id, func.count(model.id)).group_by(model.user_id))
    return {user_id: int(count or 0) for user_id, count in result.all()}


async def overview(db) -> Dict:
    online_cutoff = utcnow() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
    task_status_rows = await db.execute(
        select(BackgroundTask.status, func.count(BackgroundTask.id)).group_by(BackgroundTask.status)
    )
    knowledge_status_rows = await db.execute(
        select(Knowledge.status, func.count(Knowledge.id)).group_by(Knowledge.status)
    )
    online_users = await db.execute(
        select(func.count(User.id)).where(
            or_(User.is_disabled == 0, User.is_disabled.is_(None)),
            User.last_seen_at >= online_cutoff,
        )
    )
    return {
        "counts": {
            "users": await _count(db, User),
            "online_users": int(online_users.scalar() or 0),
            "agents": await _count(db, Agent),
            "skills": await _count(db, Skill),
            "llm_configs": await _count(db, LLMConfig),
            "knowledge_docs": await _count(db, Knowledge),
            "knowledge_chunks": await _count(db, KnowledgeChunk),
            "conversations": await _count(db, Conversation),
            "messages": await _count(db, Message),
            "runs": await _count(db, AgentRun),
            "background_tasks": await _count(db, BackgroundTask),
            "memories": await _count(db, Memory),
            "legacy_chats": await _count(db, Chat),
        },
        "task_status": {status or "unknown": int(count or 0) for status, count in task_status_rows.all()},
        "knowledge_status": {status or "unknown": int(count or 0) for status, count in knowledge_status_rows.all()},
    }


async def list_users(db) -> List[Dict]:
    result = await db.execute(
        select(User).options(selectinload(User.roles)).order_by(User.id.desc())
    )
    users = list(result.scalars().all())
    agent_counts = await _count_by_user(db, Agent)
    skill_counts = await _count_by_user(db, Skill)
    knowledge_counts = await _count_by_user(db, Knowledge)
    task_counts = await _count_by_user(db, BackgroundTask)
    return [
        _user_admin_payload(
            user,
            agent_count=agent_counts.get(user.id, 0),
            skill_count=skill_counts.get(user.id, 0),
            knowledge_count=knowledge_counts.get(user.id, 0),
            task_count=task_counts.get(user.id, 0),
        )
        for user in users
    ]


async def get_user_detail(db, user_id: int) -> Dict:
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    user = result.scalars().first()
    if not user:
        return {}
    data = _user_admin_payload(
        user,
        agent_count=await _count_for_user(db, Agent, user_id),
        skill_count=await _count_for_user(db, Skill, user_id),
        knowledge_count=await _count_for_user(db, Knowledge, user_id),
        task_count=await _count_for_user(db, BackgroundTask, user_id),
    )
    messages = await db.execute(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
    )
    data["counts"] = {
        "agents": data["agent_count"],
        "skills": data["skill_count"],
        "knowledge_docs": data["knowledge_count"],
        "background_tasks": data["task_count"],
        "llm_configs": await _count_for_user(db, LLMConfig, user_id),
        "conversations": await _count_for_user(db, Conversation, user_id),
        "messages": int(messages.scalar() or 0),
        "runs": await _count_for_user(db, AgentRun, user_id),
        "memories": await _count_for_user(db, Memory, user_id),
        "legacy_chats": await _count_for_user(db, Chat, user_id),
    }
    return data


async def _count_for_user(db, model, user_id: int) -> int:
    result = await db.execute(select(func.count(model.id)).where(model.user_id == user_id))
    return int(result.scalar() or 0)


async def list_recent_tasks(db, limit: int = 50) -> List[Dict]:
    result = await db.execute(
        select(BackgroundTask).order_by(BackgroundTask.created_at.desc()).limit(limit)
    )
    return [
        {
            "id": task.id,
            "user_id": task.user_id,
            "agent_id": task.agent_id,
            "task_type": task.task_type,
            "status": task.status,
            "title": task.title,
            "target_type": task.target_type,
            "target_id": task.target_id,
            "progress": task.progress,
            "error_msg": task.error_msg,
            "created_at": _format_dt(task.created_at),
            "started_at": _format_dt(task.started_at),
            "finished_at": _format_dt(task.finished_at),
            "next_run_at": _format_dt(getattr(task, "next_run_at", None)),
        }
        for task in result.scalars().all()
    ]


async def usage_stats(db, days: int = 14, top_limit: int = 8) -> Dict:
    days = max(1, min(days, 90))
    top_limit = max(1, min(top_limit, 20))
    start_dt = utcnow() - timedelta(days=days - 1)
    start_day = start_dt.date()

    run_rows = await db.execute(
        select(
            func.date(AgentRun.started_at),
            func.count(AgentRun.id),
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
        )
        .where(AgentRun.started_at >= start_dt)
        .group_by(func.date(AgentRun.started_at))
    )
    message_rows = await db.execute(
        select(func.date(Message.create_time), func.count(Message.id))
        .where(Message.create_time >= start_dt)
        .group_by(func.date(Message.create_time))
    )
    task_rows = await db.execute(
        select(BackgroundTask.status, func.count(BackgroundTask.id)).group_by(BackgroundTask.status)
    )
    top_run_rows = await db.execute(
        select(
            User.id,
            User.name,
            func.count(AgentRun.id),
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
        )
        .join(AgentRun, AgentRun.user_id == User.id)
        .group_by(User.id, User.name)
        .order_by(func.count(AgentRun.id).desc())
        .limit(top_limit)
    )

    run_map = {str(day): {"runs": int(count or 0), "tokens": int(tokens or 0)} for day, count, tokens in run_rows.all()}
    message_map = {str(day): int(count or 0) for day, count in message_rows.all()}
    daily = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        key = day.isoformat()
        run_item = run_map.get(key, {"runs": 0, "tokens": 0})
        daily.append({
            "date": key,
            "runs": run_item["runs"],
            "tokens": run_item["tokens"],
            "messages": message_map.get(key, 0),
        })

    total_runs = await _count(db, AgentRun)
    finished_runs = await _count_by_status(db, AgentRun, "finished")
    failed_runs = await _count_by_status(db, AgentRun, "failed")
    total_tokens = await db.execute(select(func.coalesce(func.sum(AgentRun.total_tokens), 0)))
    total_messages = await _count(db, Message)

    return {
        "summary": {
            "total_runs": total_runs,
            "finished_runs": finished_runs,
            "failed_runs": failed_runs,
            "success_rate": round((finished_runs / total_runs * 100), 1) if total_runs else 0,
            "total_tokens": int(total_tokens.scalar() or 0),
            "total_messages": total_messages,
        },
        "daily": daily,
        "task_status": {status or "unknown": int(count or 0) for status, count in task_rows.all()},
        "top_users": [
            {
                "user_id": user_id,
                "name": name,
                "run_count": int(run_count or 0),
                "tokens": int(tokens or 0),
            }
            for user_id, name, run_count, tokens in top_run_rows.all()
        ],
    }


async def _count_by_status(db, model, status: str) -> int:
    result = await db.execute(select(func.count(model.id)).where(model.status == status))
    return int(result.scalar() or 0)


async def set_user_roles(db, user_id: int, roles: List[str], operator_id: int = None) -> Dict:
    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.roles))
    )
    user = result.scalars().first()
    if not user:
        return {}
    clean_names = []
    for role in roles:
        name = (role or "").strip()
        if name and name not in clean_names:
            clean_names.append(name)
    role_models = []
    for name in clean_names:
        role_result = await db.execute(select(Role).where(Role.role_name == name))
        role_model = role_result.scalars().first()
        if not role_model:
            role_model = Role(role_name=name, description=f"{name} role")
            db.add(role_model)
            await db.flush()
        role_models.append(role_model)
    if user.name == "admin" and not any(role.role_name == "admin" for role in role_models):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能移除内置管理员账号的 admin 角色")
    if operator_id == user.id and not any(role.role_name in ADMIN_ROLE_NAMES for role in role_models):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能移除当前登录管理员自己的管理员角色")
    user.roles = role_models
    await db.flush()
    await db.commit()
    return current_user_payload(user)


async def set_user_disabled(db, user_id: int, disabled: bool, operator_id: int) -> Dict:
    result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.roles)))
    user = result.scalars().first()
    if not user:
        return {}
    if user.id == operator_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能禁用当前登录的管理员账号")
    if user.name == "admin" and disabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能禁用内置管理员账号")
    user.is_disabled = 1 if disabled else 0
    await db.flush()
    await db.commit()
    return current_user_payload(user)


async def reset_user_password(db, user_id: int, new_password: str) -> Dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        return {}
    if len(new_password or "") < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="密码至少需要 6 位")
    user.password = await run_in_threadpool(hash_password, new_password)
    await db.flush()
    await db.commit()
    return {"message": "密码已重置", "user_id": user.id}


async def delete_user(user_id: int, operator_id: int) -> Dict:
    """删除用户及其级联数据。

    级联删除逻辑（含逐个 agent 清理）较复杂且已在同步实现中验证过，
    这里用独立同步会话在线程池执行，避免重复维护两套删除逻辑。
    """
    from models.init_db import SessionLocal
    from service import admin_service

    def _run() -> Dict:
        session = SessionLocal()
        try:
            return admin_service.delete_user(session, user_id, operator_id)
        finally:
            session.close()

    return await run_in_threadpool(_run)
