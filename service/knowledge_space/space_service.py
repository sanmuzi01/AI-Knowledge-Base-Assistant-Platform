"""知识库空间：同步辅助（迁移脚本 / 后台任务 / 无 space 上传时兜底用）。"""


from models import knowledge_space_dao as dao


def ensure_default_space_for_agent(db, user_id: int, agent_id: int, agent_name: str = "") -> int:
    """确保某 Agent 有一个「默认空间」，返回 space_id。

    - 已有（按 legacy_agent_id 命中）则复用
    - 否则新建，name 取「{agent_name} 的知识库」，legacy_agent_id=agent_id，vector_migrated=0
    """
    existing = dao.find_legacy_space(db, user_id, agent_id)
    if existing:
        return existing.id
    name = (f"{agent_name} 的知识库" if agent_name else f"Agent {agent_id} 的知识库")[:120]
    space = dao.create_space(
        db, user_id,
        {
            "name": name,
            "description": "由 Agent 私有知识库自动升级而来",
            "purpose": "other",
            "legacy_agent_id": agent_id,
            "vector_migrated": 0,
        },
    )
    return space.id


def recount_space(db, space_id: int) -> dict:
    """按 knowledge 表实际数据重算某空间的 doc_count / chunk_count。"""
    from models.init_db import Knowledge

    rows = db.query(Knowledge).filter(Knowledge.space_id == space_id).all()
    doc_count = len(rows)
    chunk_count = sum(int(r.chunk_count or 0) for r in rows)
    dao.set_stats(db, space_id, doc_count=doc_count, chunk_count=chunk_count)
    return {"space_id": space_id, "doc_count": doc_count, "chunk_count": chunk_count}
