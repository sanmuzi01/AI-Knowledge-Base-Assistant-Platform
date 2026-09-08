"""Agent 运行轨迹异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import Agent, AgentRun, AgentStep


async def agent_belongs_to_user_async(db: AsyncSession, user_id: int, agent_id: int) -> bool:
    result = await db.execute(
        select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    return result.scalar() is not None


async def get_owned_run_async(
        db: AsyncSession, user_id: int, run_id: int, agent_id: int = None,
) -> Optional[AgentRun]:
    conditions = [AgentRun.id == run_id, AgentRun.user_id == user_id]
    if agent_id is not None:
        conditions.append(AgentRun.agent_id == agent_id)
    result = await db.execute(select(AgentRun).where(*conditions))
    return result.scalars().first()


async def list_runs_by_agent_async(
        db: AsyncSession,
        agent_id: int,
        limit: int = 50,
        conversation_id: Optional[int] = None,
) -> List[AgentRun]:
    conditions = [AgentRun.agent_id == agent_id]
    if conversation_id is not None:
        conditions.append(AgentRun.conversation_id == conversation_id)
    result = await db.execute(
        select(AgentRun)
        .where(*conditions)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_steps_by_run_async(db: AsyncSession, run_id: int) -> List[AgentStep]:
    result = await db.execute(
        select(AgentStep)
        .where(AgentStep.run_id == run_id)
        .order_by(AgentStep.step_no.asc())
    )
    return list(result.scalars().all())
