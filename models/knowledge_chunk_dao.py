from typing import List,Optional
from sqlalchemy import func, or_
from models.init_db import Knowledge, KnowledgeChunk


def sum_content_chars_by_knowledge_ids(db, knowledge_ids: List[int]) -> int:
    """命中文档的切块内容总字数（≈ 原文字数），用于 RAG 上下文压缩统计。"""
    ids = [int(k) for k in dict.fromkeys(knowledge_ids or [])]
    if not ids:
        return 0
    total = (
        db.query(func.coalesce(func.sum(func.char_length(KnowledgeChunk.content)), 0))
        .filter(KnowledgeChunk.knowledge_id.in_(ids))
        .scalar()
    )
    return int(total or 0)

def create_chunks_batch(db,chunks:List[dict])->List[KnowledgeChunk]:
    """
      批量插入知识块
      :param chunks: [{"knowledge_id":1,"chunk_index":0,"content":"...","vector_id":"v_0","token_count":120}, ...]
      """
    objects = [KnowledgeChunk(**c)for c in chunks]#字典解包
    db.add_all(objects)
    db.flush()
    return objects

def get_chunk_by_id(db,chunk_id:int)->Optional[KnowledgeChunk]:
    """根据ID查询单个知识块"""
    return db.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first()

def list_chunks_by_knowledge(db,knowledge_id:int)->List[KnowledgeChunk]:
    """查询某文档的所有知识块（按chunk_index正序）"""
    return (db.query(KnowledgeChunk).
            filter(KnowledgeChunk.knowledge_id == knowledge_id).
            order_by(KnowledgeChunk.chunk_index.asc()).all())

def get_chunks_by_vector_ids(db,vector_ids:List[str])->List[KnowledgeChunk]:
    """根据向量库返回的vector_id列表，批量查询知识块完整内容"""
    if not vector_ids:
        return []
    return (db.query(KnowledgeChunk).filter(KnowledgeChunk.vector_id.in_(vector_ids)).all())

def search_chunks_by_keyword(
        db, space_ids: List[int], tokens: List[str],
        exclude_chunk_ids=None, limit: int = 5,
) -> List[KnowledgeChunk]:
    """按关键词直接在 chunk 内容里找命中，补向量检索之外的召回。

    只在给定空间下、已启用的文档里找；token 之间是 OR 关系（命中任意一个即可）。
    只覆盖已迁移到"空间"模型的文档（Knowledge.space_id 有值）——这是新上传文档的
    默认路径，存量走 legacy per-agent 集合的文档不在这条补充召回里，向量检索仍照常工作。
    """
    tokens = [t for t in dict.fromkeys(tokens or []) if t]
    ids = [int(s) for s in dict.fromkeys(space_ids or [])]
    if not tokens or not ids:
        return []
    conditions = [KnowledgeChunk.content.like(f"%{t}%") for t in tokens]
    query = (
        db.query(KnowledgeChunk)
        .join(Knowledge, Knowledge.id == KnowledgeChunk.knowledge_id)
        .filter(Knowledge.space_id.in_(ids), Knowledge.is_enabled != 0)
        .filter(or_(*conditions))
    )
    exclude = set(exclude_chunk_ids or [])
    if exclude:
        query = query.filter(~KnowledgeChunk.id.in_(exclude))
    return query.limit(limit).all()


def delete_chunks_by_knowledge(db,knowledge_id:int)->int:
     """删除某文档的所有知识块，返回删除条数"""
     result = (db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_id == knowledge_id)).delete(synchronize_session=False)
     db.flush()
     return result
