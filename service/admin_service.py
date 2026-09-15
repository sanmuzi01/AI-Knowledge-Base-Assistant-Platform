from utils.timeutil import utcnow
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
    return utcnow() - last_seen_at <= timedelta(seconds=ONLINE_WINDOW_SECONDS)


def current_user_payload(user: User) -> Dict:
    roles = role_names(user)
    return {
        "user_id": user.id,
        "username": user.name,
        "phone": getattr(user, "phone", None),
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


def _count_by_user(db, model) -> Dict[int, int]:
    """按 user_id 批量统计数量，避免管理员用户列表出现 N+1 查询。"""

    return {
        user_id: int(count or 0)
        for user_id, count in db.query(model.user_id, func.count(model.id)).group_by(model.user_id).all()
    }


def _user_admin_payload(
    user: User,
    agent_count: int = 0,
    skill_count: int = 0,
    knowledge_count: int = 0,
    task_count: int = 0,
) -> Dict:
    """组装管理员后台用户摘要，保证列表和详情字段一致。"""

    return {
        "id": user.id,
        "name": user.name,
        "phone": getattr(user, "phone", None),
        "age": user.age,
        "is_disabled": getattr(user, "is_disabled", 0),
        "last_login_at": _format_dt(getattr(user, "last_login_at", None)),
        "last_seen_at": _format_dt(getattr(user, "last_seen_at", None)),
        "is_online": is_online_user(user),
        "selected_agent_id": user.selected_agent_id,
        "roles": role_names(user),
        "is_admin": is_admin_user(user),
        "agent_count": int(agent_count or 0),
        "skill_count": int(skill_count or 0),
        "knowledge_count": int(knowledge_count or 0),
        "task_count": int(task_count or 0),
    }


def overview(db) -> Dict:
    online_cutoff = utcnow() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
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
    agent_counts = _count_by_user(db, Agent)
    skill_counts = _count_by_user(db, Skill)
    knowledge_counts = _count_by_user(db, Knowledge)
    task_counts = _count_by_user(db, BackgroundTask)
    rows = []
    for user in users:
        rows.append(
            _user_admin_payload(
                user,
                agent_count=agent_counts.get(user.id, 0),
                skill_count=skill_counts.get(user.id, 0),
                knowledge_count=knowledge_counts.get(user.id, 0),
                task_count=task_counts.get(user.id, 0),
            )
        )
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
    db.commit()
    return current_user_payload(user)


def get_user_detail(db, user_id: int) -> Dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}
    data = _user_admin_payload(
        user,
        agent_count=db.query(func.count(Agent.id)).filter(Agent.user_id == user_id).scalar() or 0,
        skill_count=db.query(func.count(Skill.id)).filter(Skill.user_id == user_id).scalar() or 0,
        knowledge_count=db.query(func.count(Knowledge.id)).filter(Knowledge.user_id == user_id).scalar() or 0,
        task_count=db.query(func.count(BackgroundTask.id)).filter(BackgroundTask.user_id == user_id).scalar() or 0,
    )
    data["counts"] = {
        "agents": data["agent_count"],
        "skills": data["skill_count"],
        "knowledge_docs": data["knowledge_count"],
        "background_tasks": data["task_count"],
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
    db.commit()
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
    db.commit()
    return {"message": "密码已重置", "user_id": user.id}


def delete_user(db, user_id: int, operator_id: int) -> Dict:
    """删除用户及其全部级联数据。

    审计管理后台时发现：这个函数原来只清了 LLMConfig/Memory/BackgroundTask/Chat/角色
    这几张表——agent_service.delete() 循环能处理每个 Agent 名下的会话/运行记录/
    旧版私有知识库，但完全不知道"知识库空间"（现在所有新上传文档走的默认路径）、
    工作台组件、网页监控、操作日志这些表的存在。对任何真实用过产品的用户（几乎
    必然有至少一个 KnowledgeSpace），点"删除用户"会直接撞 FK 约束报 500，这个
    按钮实际上是坏的。现在按 tests/_route_client.py 里已经验证过的完整覆盖顺序补齐。
    """
    from sqlalchemy import text
    from models.init_db import agent_skill, association_table
    from service import agent_service

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {}
    if user.id == operator_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录的管理员账号")
    if user.name == "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="不能删除内置管理员账号")

    # 1. 企业接口连接器 / 固定评估集：agent_api_connector.agent_id 和 eval_set.agent_id
    #    都外键引用 agent.id，必须在删 Agent 之前先清掉，顺序反了会在下面 agent_service.delete()
    #    里报 FK 约束失败（这个坑真实踩过一次：写成放在 agent 循环后面，测试直接炸了）。
    db.execute(text("DELETE FROM agent_api_connector WHERE user_id = :uid"), {"uid": user.id})
    db.execute(text(
        "DELETE er FROM eval_run er JOIN eval_set es ON er.eval_set_id = es.id "
        "WHERE es.user_id = :uid"
    ), {"uid": user.id})
    db.execute(text("DELETE FROM eval_set WHERE user_id = :uid"), {"uid": user.id})

    # 2. 逐个 Agent 显式级联（会话/消息、运行轨迹、旧版私有知识库+向量、记忆/工具/旧聊天）
    agents = db.query(Agent).filter(Agent.user_id == user.id).all()
    for agent in agents:
        agent_service.delete(db, user, agent.id)

    # 3. 知识库空间体系（当前所有新上传文档的默认路径，agent_service.delete 管不到）
    #    子表在前、KnowledgeSpace 本身在后；同时清"这个用户是别人空间的成员"和
    #    "别人是这个用户空间的成员"两个方向。
    db.execute(text("DELETE FROM kb_audit_log WHERE user_id = :uid"), {"uid": user.id})
    db.execute(text("DELETE FROM space_members WHERE user_id = :uid"), {"uid": user.id})
    db.execute(text(
        "DELETE sm FROM space_members sm JOIN knowledge_spaces s ON sm.space_id = s.id "
        "WHERE s.user_id = :uid"
    ), {"uid": user.id})
    db.execute(text(
        "DELETE aks FROM agent_knowledge_space aks JOIN knowledge_spaces s ON aks.space_id = s.id "
        "WHERE s.user_id = :uid"
    ), {"uid": user.id})
    db.execute(text("DELETE FROM knowledge_spaces WHERE user_id = :uid"), {"uid": user.id})

    # 4. 工作台组件（先删数据点，widget_data_points.widget_id -> user_widgets.id）
    db.execute(text(
        "DELETE dp FROM widget_data_points dp JOIN user_widgets w ON dp.widget_id = w.id "
        "WHERE w.user_id = :uid"
    ), {"uid": user.id})
    db.execute(text("DELETE FROM user_widgets WHERE user_id = :uid"), {"uid": user.id})

    # 5. 其它按 user_id 直接挂的表
    db.execute(text("DELETE FROM rag_debug_samples WHERE user_id = :uid"), {"uid": user.id})
    db.execute(text("DELETE FROM web_monitor WHERE user_id = :uid"), {"uid": user.id})
    db.execute(text("DELETE FROM user_workspace WHERE user_id = :uid"), {"uid": user.id})
    db.execute(text("DELETE FROM operation_log WHERE user_id = :uid"), {"uid": user.id})
    db.execute(text("DELETE FROM user_profile WHERE user_id = :uid"), {"uid": user.id})

    # 6. Skill（agent_skill 绑定关系先清）
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
    db.commit()
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
            "next_run_at": task.next_run_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(task, "next_run_at", None) else None,
        }
        for task in tasks
    ]


def usage_stats(db, days: int = 14, top_limit: int = 8) -> Dict:
    days = max(1, min(days, 90))
    top_limit = max(1, min(top_limit, 20))
    start_dt = utcnow() - timedelta(days=days - 1)
    start_day = start_dt.date()

    run_rows = (
        db.query(
            func.date(AgentRun.started_at),
            func.count(AgentRun.id),
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
        )
        .filter(AgentRun.started_at >= start_dt)
        .group_by(func.date(AgentRun.started_at))
        .all()
    )
    message_rows = (
        db.query(func.date(Message.create_time), func.count(Message.id))
        .filter(Message.create_time >= start_dt)
        .group_by(func.date(Message.create_time))
        .all()
    )
    task_rows = (
        db.query(BackgroundTask.status, func.count(BackgroundTask.id))
        .group_by(BackgroundTask.status)
        .all()
    )
    top_run_rows = (
        db.query(
            User.id,
            User.name,
            func.count(AgentRun.id),
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
        )
        .join(AgentRun, AgentRun.user_id == User.id)
        .group_by(User.id, User.name)
        .order_by(func.count(AgentRun.id).desc())
        .limit(top_limit)
        .all()
    )

    run_map = {str(day): {"runs": int(count or 0), "tokens": int(tokens or 0)} for day, count, tokens in run_rows}
    message_map = {str(day): int(count or 0) for day, count in message_rows}
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

    total_runs = db.query(func.count(AgentRun.id)).scalar() or 0
    finished_runs = db.query(func.count(AgentRun.id)).filter(AgentRun.status == "finished").scalar() or 0
    failed_runs = db.query(func.count(AgentRun.id)).filter(AgentRun.status == "failed").scalar() or 0
    total_tokens = db.query(func.coalesce(func.sum(AgentRun.total_tokens), 0)).scalar() or 0
    total_messages = db.query(func.count(Message.id)).scalar() or 0

    return {
        "summary": {
            "total_runs": total_runs,
            "finished_runs": finished_runs,
            "failed_runs": failed_runs,
            "success_rate": round((finished_runs / total_runs * 100), 1) if total_runs else 0,
            "total_tokens": int(total_tokens or 0),
            "total_messages": total_messages,
        },
        "daily": daily,
        "task_status": {status or "unknown": int(count or 0) for status, count in task_rows},
        "top_users": [
            {
                "user_id": user_id,
                "name": name,
                "run_count": int(run_count or 0),
                "tokens": int(tokens or 0),
            }
            for user_id, name, run_count, tokens in top_run_rows
        ],
    }
