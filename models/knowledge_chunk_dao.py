from typing import List,Optional
from models.init_db import KnowledgeChunk

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

def delete_chunks_by_knowledge(db,knowledge_id:int)->int:
     """删除某文档的所有知识块，返回删除条数"""
     result = (db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_id == knowledge_id)).delete(synchronize_session=False)
     db.flush()
     return result
