"""工作台组件专用的 RAG 检索入口。

RAG 检索链路（向量化 + ChromaDB + 同步 DAO + rerank）是同步子系统。异步的组件
运行引擎通过 asyncio.to_thread 调用这里的 search_for_widget，不把同步 Session 泄漏进
service/widgets。单独成文件是为了不改动 rag_service.py（避免大范围行尾变更）。
"""

from typing import Any, Dict, List


def search_for_widget(user_id: int, agent_id: int, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """自带同步 Session + Agent 归属校验的检索。归属不符抛 PermissionError。"""
    from models.init_db import SessionLocal
    from models.agent_dao import get_agent_by_id
    from service.rag import rag_service

    db = SessionLocal()
    try:
        agent = get_agent_by_id(db, agent_id)
        if not agent or agent.user_id != user_id:
            raise PermissionError("知识库不存在或无权访问")
        hits = rag_service.search(db, user_id, agent_id, query, top_k=top_k)
        return [
            {
                "content": h.get("content", ""),
                "score": h.get("score"),
                "file_name": h.get("file_name", ""),
                "knowledge_id": h.get("knowledge_id"),
            }
            for h in hits
        ]
    finally:
        db.close()
