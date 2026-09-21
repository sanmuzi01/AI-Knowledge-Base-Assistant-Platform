"""Skill 异步读服务。"""

from typing import Dict, List, Optional

from starlette.concurrency import run_in_threadpool

from models import skill_async_dao as dao
from service.access_control import can_read_skill
from service.skill_service import _skill_to_dict, validate_skill_config_file
from service.skills.loader import load_skill_config
from utils.logger_handler import get_logger

logger = get_logger("skill_async_service")


async def list_user_skills(db, user_id: int) -> List[Dict]:
    skills = await dao.list_skills_by_user_async(db, user_id)
    return [_skill_to_dict(skill) for skill in skills]


async def list_all_skills(db) -> List[Dict]:
    skills = await dao.list_all_skills_async(db)
    return [_skill_to_dict(skill) for skill in skills]


async def list_public_skills(db) -> List[Dict]:
    """能力商店列表。is_official：发布者是管理员（= 经管理员审核上架）。
    以前普通用户也能公开，那批老数据发布者不是管理员，所以不能一概当官方。"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from models.init_db import User
    from service.admin_service import is_admin_user

    skills = await dao.list_public_skills_async(db)
    owner_ids = {s.user_id for s in skills}
    admin_ids = set()
    if owner_ids:
        result = await db.execute(select(User).where(User.id.in_(owner_ids)).options(selectinload(User.roles)))
        admin_ids = {u.id for u in result.unique().scalars().all() if is_admin_user(u)}
    items = []
    for skill in skills:
        item = _skill_to_dict(skill)
        item["is_official"] = skill.user_id in admin_ids
        items.append(item)
    return items


async def get_skill(db, skill_id: int, user_id: int = None) -> Optional[Dict]:
    skill = await dao.get_skill_by_id_async(db, skill_id)
    if skill and user_id is not None and not can_read_skill(skill, user_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试查看私有Skill {skill_id}")
        return None
    return _skill_to_dict(skill) if skill else None


async def get_skill_with_config(db, skill_id: int, user_id: int, allow_admin: bool = False) -> Optional[Dict]:
    """异步查 Skill，配置文件读取放到线程池执行。"""

    skill_model = await dao.get_skill_by_id_async(db, skill_id)
    if skill_model is None or (not allow_admin and not can_read_skill(skill_model, user_id)):
        return None
    skill = _skill_to_dict(skill_model)
    cfg = await run_in_threadpool(load_skill_config, skill_model.config_file)
    skill["config"] = {
        "name": cfg.get("name", skill_model.name),
        "description": cfg.get("description", skill_model.description or ""),
        "version": cfg.get("version", "1.0"),
        "tools": cfg.get("tools", []),
        "tool_names": cfg.get("tool_names", []),
        "system_prompt": cfg.get("system_prompt", ""),
        "permissions": cfg.get("permissions", {"network": False, "file_read": [], "exec": False}),
        "resources": cfg.get("resources", []),
    }
    return skill


async def validate_skill(db, skill_id: int, user_id: int, allow_admin: bool = False) -> Optional[Dict]:
    skill = await dao.get_skill_by_id_async(db, skill_id)
    if skill is None or (not allow_admin and not can_read_skill(skill, user_id)):
        return None
    result = await run_in_threadpool(validate_skill_config_file, skill.config_file)
    result.update({
        "skill_id": skill.id,
        "name": skill.name,
        "config_file": skill.config_file,
        "is_public": skill.is_public,
    })
    return result


async def list_agent_skills(db, agent_id: int, user_id: int = None) -> List[Dict]:
    if user_id is not None and not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        logger.warning(f"权限拒绝：用户{user_id}无权查看Agent {agent_id}的Skill")
        return []
    skills = await dao.list_skills_by_agent_async(db, agent_id)
    return [_skill_to_dict(skill) for skill in skills]
