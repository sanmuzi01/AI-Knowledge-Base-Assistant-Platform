"""Skill 异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.init_db import Agent, Skill


async def get_skill_by_id_async(db: AsyncSession, skill_id: int) -> Optional[Skill]:
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalars().first()


async def list_skills_by_user_async(db: AsyncSession, user_id: int) -> List[Skill]:
    result = await db.execute(select(Skill).where(Skill.user_id == user_id).order_by(Skill.id.desc()))
    return list(result.unique().scalars().all())


async def list_public_skills_async(db: AsyncSession) -> List[Skill]:
    result = await db.execute(select(Skill).where(Skill.is_public == 1).order_by(Skill.id.desc()))
    return list(result.unique().scalars().all())


async def list_skills_by_agent_async(db: AsyncSession, agent_id: int) -> List[Skill]:
    result = await db.execute(
        select(Agent)
        .where(Agent.id == agent_id)
        .options(selectinload(Agent.skills))
    )
    agent = result.unique().scalars().first()
    return list(agent.skills) if agent else []


async def agent_belongs_to_user_async(db: AsyncSession, user_id: int, agent_id: int) -> bool:
    result = await db.execute(select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id))
    return result.scalar_one_or_none() is not None
