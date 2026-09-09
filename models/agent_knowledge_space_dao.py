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


def set_agent_spaces(db, agent_id: int, space_ids: List[int], commit: bool = True) -> None:
    """整体替换某 Agent 的绑定空间。调用方需已校验 space 归属。

    commit=False 供 agent create/update 在同一事务里收尾（避免半提交）。
    """
    db.query(AgentKnowledgeSpace).filter(AgentKnowledgeSpace.agent_id == agent_id).delete()
    for sid in dict.fromkeys(int(s) for s in space_ids):
        db.add(AgentKnowledgeSpace(agent_id=agent_id, space_id=sid))
    if commit:
        db.commit()
    else:
        db.flush()


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


async def map_space_ids_by_agents_async(db: AsyncSession, agent_ids: List[int]) -> dict:
    """{agent_id: [space_id, ...]}，一次查完（列表页避免 N 次查询）。"""
    ids = [int(a) for a in dict.fromkeys(agent_ids or [])]
    if not ids:
        return {}
    res = await db.execute(
        select(AgentKnowledgeSpace.agent_id, AgentKnowledgeSpace.space_id)
        .where(AgentKnowledgeSpace.agent_id.in_(ids))
    )
    out: dict = {a: [] for a in ids}
    for agent_id, space_id in res.all():
        out.setdefault(agent_id, []).append(space_id)
    return out
