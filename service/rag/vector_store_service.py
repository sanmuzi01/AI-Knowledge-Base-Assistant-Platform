"""
向量存储服务：和 ChromaDB 交互
职责：只管向量的增删查，不关心向量怎么来的、文字内容怎么用
  rag_service.py (业务编排)
        ↓
  vector_store_service.py (向量库CRUD ← 你在这里)
        ↓
  ChromaDB (本地文件向量库)
向量库可能换（ChromaDB → Milvus → PGVector），
把"存向量/查向量"这步单独拆出来，换库时只改这个文件，其他代码零改动。

集合键（collection key）：
- 传 int：旧的「每个 Agent 一个集合」——`agent_{id}_knowledge`（存量数据 / 旧路径）
- 传 "space_<id>" / "agent_<id>"：知识库空间升级后的集合——`{key}_knowledge`
第一个参数历史上叫 agent_id，为兼容旧调用方（含 add_vectors(agent_id=...)）保留该名字，
实际语义是「集合键」。
"""
import os
from typing import Any, Dict, List

import chromadb
from dotenv import load_dotenv

from utils.logger_handler import get_logger
from utils.path_tool import get_abs_path

load_dotenv()
logger = get_logger("vector_store")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./vector_db")
_client = None


def space_collection_key(space_id: int) -> str:
    return f"space_{int(space_id)}"


def legacy_agent_key(agent_id: int) -> str:
    return f"agent_{int(agent_id)}"


def _collection_name(key) -> str:
    """把集合键规整成 ChromaDB 集合名。"""
    s = str(key)
    if s.startswith(("space_", "agent_")):
        return f"{s}_knowledge"
    return f"agent_{s}_knowledge"   # 兼容裸 agent_id（int / 数字串）


def _get_client() -> "chromadb.api.ClientAPI":
    global _client
    if _client is None:
        abs_path = get_abs_path(VECTOR_DB_PATH)
        os.makedirs(abs_path, exist_ok=True)
        _client = chromadb.PersistentClient(path=abs_path)
        logger.info(f"ChromaDB初始化完成，持久化路径: {abs_path}")
    return _client


def _get_collection(key):
    client = _get_client()
    return client.get_or_create_collection(
        name=_collection_name(key),
        metadata={"hnsw:space": "cosine"},
    )


def collection_exists(key) -> bool:
    try:
        _get_client().get_collection(name=_collection_name(key))
        return True
    except Exception:
        return False


def add_vectors(
        agent_id, vectors: List[List[float]],
        ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]] = None,
) -> None:
    """批量存入向量。`agent_id` 实为集合键（见模块 docstring）。"""
    collection = _get_collection(agent_id)
    BATCH = 100
    for i in range(0, len(vectors), BATCH):
        end = i + BATCH
        collection.add(
            embeddings=vectors[i:end],
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end] if metadatas else None,
        )
    logger.info(f"[{_collection_name(agent_id)}] 存入 {len(vectors)} 条向量")


def search_similar(
        agent_id, query_vector: List[float], top_k: int = 5, where: Dict = None,
) -> List[Dict[str, Any]]:
    """向量相似度检索。`agent_id` 实为集合键。集合不存在 / 为空时返回 []。"""
    try:
        collection = _get_collection(agent_id)
        count = collection.count()
        if count <= 0:
            return []
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, count),
            where=where,
        )
    except Exception as e:
        logger.error(f"[{_collection_name(agent_id)}] 向量检索失败: {e}")
        raise

    flattened = []
    if results and results.get("ids") and results["ids"][0]:
        ids_list = results["ids"][0]
        docs_list = results.get("documents", [[]])[0] if results.get("documents") else [None] * len(ids_list)
        dist_raw = results.get("distances")
        dist_list = dist_raw[0] if dist_raw and dist_raw[0] else [0.0] * len(ids_list)
        meta_raw = results.get("metadatas")
        meta_list = meta_raw[0] if meta_raw and meta_raw[0] else [None] * len(ids_list)
        for i, vid in enumerate(ids_list):
            dist = dist_list[i] if isinstance(dist_list[i], (int, float)) else 0.0
            flattened.append({
                "id": vid,
                "document": docs_list[i] if i < len(docs_list) else None,
                "distance": float(dist),
                "metadata": meta_list[i] if i < len(meta_list) else None,
            })
    return flattened


def delete_vectors_by_knowledge(agent_id, knowledge_id: int) -> None:
    """删除某文档对应的所有向量（按 metadata.knowledge_id 过滤）。`agent_id` 实为集合键。"""
    collection = _get_collection(agent_id)
    collection.delete(where={"knowledge_id": knowledge_id})
    logger.info(f"[{_collection_name(agent_id)}] 删除文档{knowledge_id} 的所有向量")


def delete_collection(agent_id) -> None:
    """删除整个向量集合。`agent_id` 实为集合键。集合不存在只记 warning。"""
    try:
        _get_client().delete_collection(name=_collection_name(agent_id))
        logger.info(f"删除向量集合 {_collection_name(agent_id)}")
    except Exception as e:
        logger.warning(f"删除向量集合失败（可能不存在）: {e}")
