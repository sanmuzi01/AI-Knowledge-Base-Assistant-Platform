"""带归属校验的 RAG 检索入口（同步，自带同步 Session）。

RAG 检索链路（向量化配置查询 + ChromaDB + 同步 DAO + rerank）目前整体是同步的。
异步调用方——FastAPI 请求处理器、组件运行引擎——应通过 `asyncio.to_thread` 调用这里，
不要把同步 `Session` 泄漏进路由 / `service/widgets`。

单独成文件（不改 `rag_service.py`）是为了避免那个文件的大范围行尾变更。
"""

from typing import Any, Dict, List, Optional


def search_scoped(
    user_id: int,
    agent_id: int,
    query: str,
    top_k: int = 5,
    knowledge_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """校验 agent 归属（及可选的单文档归属 / 启用状态）后做一次检索。

    - 归属不符 -> PermissionError
    - query 为空 / 指定文档已禁用 -> ValueError
    """
    from models.init_db import SessionLocal
    from models.agent_dao import get_agent_by_id
    from models.knowledge_dao import get_knowledge_by_id
    from service.rag import rag_service

    if not query or not query.strip():
        raise ValueError("检索关键词不能为空")

    db = SessionLocal()
    try:
        agent = get_agent_by_id(db, agent_id)
        if not agent or agent.user_id != user_id:
            raise PermissionError("智能体不存在或无权限")
        if knowledge_id is not None:
            doc = get_knowledge_by_id(db, knowledge_id)
            if not doc or doc.agent_id != agent_id:
                raise PermissionError("文档不存在或无权限")
            if doc.is_enabled == 0:
                raise ValueError("该文档已禁用，不参与检索")
        return rag_service.search(db, user_id, agent_id, query, top_k=top_k, knowledge_id=knowledge_id)
    finally:
        db.close()


def search_for_widget(user_id: int, agent_id: int, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """工作台组件用的检索入口（无 knowledge_id 维度）。"""
    hits = search_scoped(user_id, agent_id, query, top_k=top_k)
    return [
        {
            "content": h.get("content", ""),
            "score": h.get("score"),
            "file_name": h.get("file_name", ""),
            "knowledge_id": h.get("knowledge_id"),
        }
        for h in hits
    ]
