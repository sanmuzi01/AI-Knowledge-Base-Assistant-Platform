"""知识库异步 DAO。"""

from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import Agent, Knowledge, KnowledgeChunk


async def agent_belongs_to_user_async(db: AsyncSession, user_id: int, agent_id: int) -> bool:
    """检查助手是否属于当前用户。"""

    result = await db.execute(
        select(Agent.id).where(Agent.id == agent_id, Agent.user_id == user_id)
    )
    return result.scalar() is not None


async def list_knowledge_with_agent_by_user_async(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Knowledge, Agent.name.label("agent_name"))
        .join(Agent, Knowledge.agent_id == Agent.id)
        .where(Knowledge.user_id == user_id, Agent.user_id == user_id)
        .order_by(Knowledge.created_at.desc())
    )
    return result.all()


async def list_knowledge_by_agent_async(db: AsyncSession, agent_id: int) -> List[Knowledge]:
    result = await db.execute(
        select(Knowledge)
        .where(Knowledge.agent_id == agent_id)
        .order_by(Knowledge.created_at.desc())
    )
    return list(result.scalars().all())


async def list_knowledge_by_space_async(
        db: AsyncSession, space_id: int, *,
        category: str = None, tag: str = None, status: str = None, is_enabled: int = None,
) -> List[Knowledge]:
    conds = [Knowledge.space_id == space_id]
    if category:
        conds.append(Knowledge.category == category)
    if status:
        conds.append(Knowledge.status == status)
    if is_enabled is not None:
        conds.append(Knowledge.is_enabled == is_enabled)
    if tag:
        conds.append(Knowledge.tags_json.like(f'%"{tag}"%'))
    result = await db.execute(
        select(Knowledge).where(*conds).order_by(Knowledge.created_at.desc())
    )
    return list(result.scalars().all())


async def get_owned_knowledge_in_space_async(
        db: AsyncSession, user_id: int, space_id: int, knowledge_id: int,
) -> Optional[Knowledge]:
    result = await db.execute(
        select(Knowledge).where(
            Knowledge.id == knowledge_id,
            Knowledge.user_id == user_id,
            Knowledge.space_id == space_id,
        )
    )
    return result.scalars().first()


async def get_owned_knowledge_async(
        db: AsyncSession, user_id: int, knowledge_id: int, agent_id: int = None,
) -> Optional[Knowledge]:
    conditions = [Knowledge.id == knowledge_id, Knowledge.user_id == user_id]
    if agent_id is not None:
        conditions.append(Knowledge.agent_id == agent_id)
    result = await db.execute(select(Knowledge).where(*conditions))
    return result.scalars().first()


async def list_chunks_by_knowledge_async(
        db: AsyncSession, knowledge_id: int,
) -> List[KnowledgeChunk]:
    result = await db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.knowledge_id == knowledge_id)
        .order_by(KnowledgeChunk.chunk_index.asc())
    )
    return list(result.scalars().all())


async def get_knowledge_by_id_async(db: AsyncSession, knowledge_id: int) -> Optional[Knowledge]:
    """按 id 取单篇文档（`knowledge_dao.get_knowledge_by_id` 的 async 版）。"""
    result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    return result.scalars().first()


async def get_knowledge_by_ids_async(db: AsyncSession, knowledge_ids) -> dict:
    """按一批 id 批量取文档，返回 {id: Knowledge}。

    检索热路径（每次聊天触发 RAG 都会走到）之前是循环调用 get_knowledge_by_id_async，
    命中几个文档就发几条 SELECT——这里改成一条 WHERE id IN (...)。
    """
    ids = list({i for i in knowledge_ids if i is not None})
    if not ids:
        return {}
    result = await db.execute(select(Knowledge).where(Knowledge.id.in_(ids)))
    return {k.id: k for k in result.scalars().all()}


async def get_chunks_by_vector_ids_async(
        db: AsyncSession, vector_ids: List[str],
) -> List[KnowledgeChunk]:
    """按向量库返回的 vector_id 批量反查 chunk（`knowledge_chunk_dao.get_chunks_by_vector_ids` 的 async 版）。"""
    if not vector_ids:
        return []
    result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.vector_id.in_(vector_ids))
    )
    return list(result.scalars().all())


async def search_chunks_by_keyword_async(
        db: AsyncSession, space_ids: List[int], tokens: List[str],
        exclude_chunk_ids=None, limit: int = 5,
) -> List[KnowledgeChunk]:
    """`knowledge_chunk_dao.search_chunks_by_keyword` 的 async 版。"""
    tokens = [t for t in dict.fromkeys(tokens or []) if t]
    ids = [int(s) for s in dict.fromkeys(space_ids or [])]
    if not tokens or not ids:
        return []
    conditions = [KnowledgeChunk.content.like(f"%{t}%") for t in tokens]
    stmt = (
        select(KnowledgeChunk)
        .join(Knowledge, Knowledge.id == KnowledgeChunk.knowledge_id)
        .where(Knowledge.space_id.in_(ids), Knowledge.is_enabled != 0)
        .where(or_(*conditions))
    )
    exclude = set(exclude_chunk_ids or [])
    if exclude:
        stmt = stmt.where(~KnowledgeChunk.id.in_(exclude))
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def sum_chunk_chars_by_knowledge_ids_async(
        db: AsyncSession, knowledge_ids: List[int],
) -> int:
    """命中文档的切块内容总字数（≈ 原文字数）。
    `knowledge_chunk_dao.sum_content_chars_by_knowledge_ids` 的 async 版。"""
    ids = [int(k) for k in dict.fromkeys(knowledge_ids or [])]
    if not ids:
        return 0
    result = await db.execute(
        select(func.coalesce(func.sum(func.char_length(KnowledgeChunk.content)), 0))
        .where(KnowledgeChunk.knowledge_id.in_(ids))
    )
    return int(result.scalar() or 0)
