"""Agent ↔ 知识库空间 绑定 DAO（同步 + 异步）。"""

from typing import List

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import AgentKnowledgeSpace


# ---------------- 同步 ----------------

def list_space_ids_by_agent(db, agent_id: int) -> List[int]:
    rows = (
        db.query(AgentKnowledgeSpace.space_id)
        .filter(AgentKnowledgeSpace.agent_id == agent_id)
        .all()
    )
    return [r[0] for r in rows]


def set_agent_spaces(db, agent_id: int, space_ids: List[int]) -> None:
    """整体替换某 Agent 的绑定空间。调用方需已校验 space 归属。"""
    db.query(AgentKnowledgeSpace).filter(AgentKnowledgeSpace.agent_id == agent_id).delete()
    for sid in dict.fromkeys(int(s) for s in space_ids):
        db.add(AgentKnowledgeSpace(agent_id=agent_id, space_id=sid))
    db.commit()


# ---------------- 异步 ----------------

async def list_space_ids_by_agent_async(db: AsyncSession, agent_id: int) -> List[int]:
    res = await db.execute(
        select(AgentKnowledgeSpace.space_id).where(AgentKnowledgeSpace.agent_id == agent_id)
    )
    return [row[0] for row in res.all()]


async def set_agent_spaces_async(db: AsyncSession, agent_id: int, space_ids: List[int]) -> None:
    await db.execute(sa_delete(AgentKnowledgeSpace).where(AgentKnowledgeSpace.agent_id == agent_id))
    for sid in dict.fromkeys(int(s) for s in space_ids):
        db.add(AgentKnowledgeSpace(agent_id=agent_id, space_id=sid))
    await db.commit()


async def list_agent_ids_by_space_async(db: AsyncSession, space_id: int) -> List[int]:
    res = await db.execute(
        select(AgentKnowledgeSpace.agent_id).where(AgentKnowledgeSpace.space_id == space_id)
    )
    return [row[0] for row in res.all()]
