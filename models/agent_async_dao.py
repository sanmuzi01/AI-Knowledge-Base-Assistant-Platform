"""Agent 异步 DAO。

先覆盖读多的查询接口，写操作继续使用现有同步 DAO，降低迁移风险。
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.init_db import Agent, Skill


async def list_agents_by_user_async(db: AsyncSession, user_id: int) -> List[Agent]:
    """异步查询指定用户下的所有助手，预加载技能避免 N+1 查询。"""

    result = await db.execute(
        select(Agent)
        .where(Agent.user_id == user_id)
        .options(selectinload(Agent.skills))
        .order_by(Agent.id.desc())
    )
    return list(result.scalars().all())


async def get_agent_by_id_async(db: AsyncSession, agent_id: int) -> Optional[Agent]:
    """异步按 ID 查询助手并预加载技能。"""

    result = await db.execute(
        select(Agent)
        .where(Agent.id == agent_id)
        .options(selectinload(Agent.skills))
    )
    return result.scalars().first()


async def get_selected_agent_by_user_async(db: AsyncSession, user) -> Optional[Agent]:
    """异步查询当前用户选中的助手。"""

    selected_id = getattr(user, "selected_agent_id", None)
    if not selected_id:
        return None
    result = await db.execute(
        select(Agent)
        .where(Agent.id == selected_id, Agent.user_id == user.id)
        .options(selectinload(Agent.skills))
    )
    return result.scalars().first()


def skill_to_dict(skill: Skill) -> dict:
    """把 Skill ORM 对象转成前端需要的结构。"""

    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "config_file": skill.config_file,
        "is_public": skill.is_public,
        "created_at": skill.created_at.strftime("%Y-%m-%d %H:%M:%S") if skill.created_at else None,
    }
