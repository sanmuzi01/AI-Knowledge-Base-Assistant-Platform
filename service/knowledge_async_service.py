"""知识库异步读服务。"""

from typing import Dict

from models import knowledge_async_dao as dao


def doc_to_dict(doc, agent_name: str = None):
    return {
        "id": doc.id,
        "agent_id": doc.agent_id,
        "agent_name": agent_name,
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "is_enabled": doc.is_enabled if doc.is_enabled is not None else 1,
        "error_msg": doc.error_msg,
        "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if doc.created_at else None,
    }


async def list_my_documents(db, user_id: int):
    rows = await dao.list_knowledge_with_agent_by_user_async(db, user_id)
    return [doc_to_dict(doc, agent_name=agent_name) for doc, agent_name in rows]


async def list_documents(db, agent_id: int):
    docs = await dao.list_knowledge_by_agent_async(db, agent_id)
    return [doc_to_dict(doc) for doc in docs]


async def list_owned_documents(db, user_id: int, agent_id: int):
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        return None
    return await list_documents(db, agent_id)


async def get_document(db, user_id: int, agent_id: int, knowledge_id: int) -> Dict:
    doc = await dao.get_owned_knowledge_async(db, user_id, knowledge_id, agent_id=agent_id)
    if not doc:
        return {}
    return doc_to_dict(doc)


async def list_document_chunks(db, user_id: int, agent_id: int, knowledge_id: int):
    doc = await dao.get_owned_knowledge_async(db, user_id, knowledge_id, agent_id=agent_id)
    if not doc:
        return None
    chunks = await dao.list_chunks_by_knowledge_async(db, knowledge_id)
    return {
        "knowledge_id": knowledge_id,
        "count": len(chunks),
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "token_count": c.token_count,
                "vector_id": c.vector_id,
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None,
            }
            for c in chunks
        ],
    }
