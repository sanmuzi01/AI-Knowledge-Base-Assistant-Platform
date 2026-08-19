import os
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import func, or_
from fastapi import HTTPException, status

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


ADMIN_ROLE_NAMES = {"admin", "administrator", "管理员"}
ONLINE_WINDOW_SECONDS = int(os.getenv("ONLINE_WINDOW_SECONDS", "300"))


def role_names(user: User) -> List[str]:
    return [role.role_name for role in (user.roles or [])]


def is_admin_user(user: User) -> bool:
    names = {name.strip() for name in role_names(user)}
    if names.intersection(ADMIN_ROLE_NAMES):
        return True
    env_admins = {
        name.strip()
        for name in os.getenv("ADMIN_USER_NAMES", "admin").split(",")
        if name.strip()
    }
    return user.name in env_admins


def _format_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def is_online_user(user: User) -> bool:
    last_seen_at = getattr(user, "last_seen_at", None)
    if not last_seen_at:
        return False
    return datetime.utcnow() - last_seen_at <= timedelta(seconds=ONLINE_WINDOW_SECONDS)


def current_user_payload(user: User) -> Dict:
    roles = role_names(user)
    return {
        "user_id": user.id,
        "username": user.name,
        "age": user.age,
        "is_disabled": getattr(user, "is_disabled", 0),
        "last_login_at": _format_dt(getattr(user, "last_login_at", None)),
        "last_seen_at": _format_dt(getattr(user, "last_seen_at", None)),
        "is_online": is_online_user(user),
        "selected_agent_id": user.selected_agent_id,
        "roles": roles,
        "is_admin": is_admin_user(user),
    }


def _count(db, model) -> int:
    return db.query(func.count(model.id)).scalar() or 0


def overview(db) -> Dict:
    online_cutoff = datetime.utcnow() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
    task_status_rows = (
        db.query(BackgroundTask.status, func.count(BackgroundTask.id))
        .group_by(BackgroundTask.status)
        .all()
    )
    knowledge_status_rows = (
        db.query(Knowledge.status, func.count(Knowledge.id))
        .group_by(Knowledge.status)
        .all()
    )
    return {
        "counts": {
            "users": _count(db, User),
            "online_users": (
                db.query(func.count(User.id))
                .filter(or_(User.is_disabled == 0, User.is_disabled.is_(None)), User.last_seen_at >= online_cutoff)
                .scalar() or 0
            ),
            "agents": _count(db, Agent),
            "skills": _count(db, Skill),
            "llm_configs": _count(db, LLMConfig),
            "knowledge_docs": _count(db, Knowledge),
            "knowledge_chunks": _count(db, KnowledgeChunk),
            "conversations": _count(db, Conversation),
            "messages": _count(db, Message),
            "runs": _count(db, AgentRun),
            "background_tasks": _count(db, BackgroundTask),
            "memories": _count(db, Memory),
            "legacy_chats": _count(db, Chat),
        },
        "task_status": {status or "unknown": count for status, count in task_status_rows},
        "knowledge_status": {status or "unknown": count for status, count in knowledge_status_rows},
    }


def list_users(db) -> List[Dict]:
    users = db.query(User).order_by(User.id.desc()).all()
    rows = []
    for user in users:
        rows.append({
            "id": user.id,
            "name": user.name,
            "age": user.age,
            "is_disabled": getattr(user, "is_disabled", 0),
            "last_login_at": _format_dt(getattr(user, "last_login_at", None)),
            "last_seen_at": _format_dt(getattr(user, "last_seen_at", None)),
            "is_online": is_online_user(user),
            "selected_agent_id": user.selected_agent_id,
            "roles": role_names(user),
            "is_admin": is_admin_user(user),
            "agent_count": db.query(func.count(Agent.id)).filter(Agent.user_id == user.id).scalar() or 0,
            "skill_count": db.query(func.count(Skill.id)).filter(Skill.user_id == user.id).scalar() or 0,
            "knowledge_count": db.query(func.count(Knowledge.id)).filter(Knowledge.user_id == user.id).scalar() or 0,
            "task_count": db.query(func.count(BackgroundTask.id)).filter(BackgroundTask.user_id == user.id).scalar() or 0,
        })
    return rows


def set_user_roles(db, user_id: int, roles: List[str], operator_id: int = None) -> Dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}
    clean_names = []
    for role in roles:
        name = (role or "").strip()
        if name and name not in clean_names:
            clean_names.append(name)
    role_models = []
    for name in clean_names:
        role = db.query(Role).filter(Role.role_name == name).first()
        if not role:
            role = Role(role_name=name, description=f"{name} role")
            db.add(role)
            db.flush()
        role_models.append(role)
    if user.name == "admin" and not any(role.role_name == "admin" for role in role_models):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能移除内置管理员账号的 admin 角色")
    if operator_id == user.id and not any(role.role_name in ADMIN_ROLE_NAMES for role in role_models):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能移除当前登录管理员自己的管理员角色")
    user.roles = role_models
    db.flush()
    return current_user_payload(user)


def get_user_detail(db, user_id: int) -> Dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}
    data = next((item for item in list_users(db) if item["id"] == user_id), None)
    if not data:
        return {}
    data["counts"] = {
        "llm_configs": db.query(func.count(LLMConfig.id)).filter(LLMConfig.user_id == user_id).scalar() or 0,
        "conversations": db.query(func.count(Conversation.id)).filter(Conversation.user_id == user_id).scalar() or 0,
        "messages": (
            db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == user_id)
            .scalar() or 0
        ),
        "runs": db.query(func.count(AgentRun.id)).filter(AgentRun.user_id == user_id).scalar() or 0,
        "memories": db.query(func.count(Memory.id)).filter(Memory.user_id == user_id).scalar() or 0,
        "legacy_chats": db.query(func.count(Chat.id)).filter(Chat.user_id == user_id).scalar() or 0,
    }
    return data


def set_user_disabled(db, user_id: int, disabled: bool, operator_id: int) -> Dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}
    if user.id == operator_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能禁用当前登录的管理员账号")
    if user.name == "admin" and disabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能禁用内置管理员账号")
    user.is_disabled = 1 if disabled else 0
    db.flush()
    return current_user_payload(user)


def reset_user_password(db, user_id: int, new_password: str) -> Dict:
    import bcrypt

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}
    if len(new_password or "") < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="密码至少需要 6 位")
    user.password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db.flush()
    return {"message": "密码已重置", "user_id": user.id}


def delete_user(db, user_id: int, operator_id: int) -> Dict:
    from models.init_db import agent_skill, association_table
    from service import agent_service

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}
    if user.id == operator_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录的管理员账号")
    if user.name == "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能删除内置管理员账号")

    agents = db.query(Agent).filter(Agent.user_id == user.id).all()
    for agent in agents:
        agent_service.delete(db, user, agent.id)

    skill_ids = [row[0] for row in db.query(Skill.id).filter(Skill.user_id == user.id).all()]
    if skill_ids:
        db.execute(agent_skill.delete().where(agent_skill.c.skill_id.in_(skill_ids)))
        db.query(Skill).filter(Skill.id.in_(skill_ids)).delete(synchronize_session=False)

    db.query(LLMConfig).filter(LLMConfig.user_id == user.id).delete(synchronize_session=False)
    db.query(Memory).filter(Memory.user_id == user.id).delete(synchronize_session=False)
    db.query(BackgroundTask).filter(BackgroundTask.user_id == user.id).delete(synchronize_session=False)
    db.query(Chat).filter(Chat.user_id == user.id).delete(synchronize_session=False)
    db.execute(association_table.delete().where(association_table.c.user_id == user.id))
    db.delete(user)
    db.flush()
    return {"message": "用户已删除", "user_id": user_id}


def list_recent_tasks(db, limit: int = 50) -> List[Dict]:
    tasks = (
        db.query(BackgroundTask)
        .order_by(BackgroundTask.created_at.desc())
        .limit(limit)
        .all()
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
            "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
            "started_at": task.started_at.strftime("%Y-%m-%d %H:%M:%S") if task.started_at else None,
            "finished_at": task.finished_at.strftime("%Y-%m-%d %H:%M:%S") if task.finished_at else None,
        }
        for task in tasks
    ]
