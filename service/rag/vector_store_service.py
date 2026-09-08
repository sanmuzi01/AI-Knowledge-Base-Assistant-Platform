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
"""
import os
from typing import List,Dict,Any
from dotenv import load_dotenv
import chromadb
from utils.path_tool import get_abs_path
from utils.logger_handler import get_logger
load_dotenv()
logger=get_logger("vector_store")
# 从 .env 读向量库持久化路径
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH","./vector_db")
# ========== ChromaDB 客户端（单例懒加载） ==========
_client = None   # 全局变量，第一次调用时初始化

def _get_client()->chromadb.api.ClientAPI:
    """获取ChromaDB客户端（单例懒加载）:第一次使用时才使用
       ChromaDB初始化会读磁盘索引文件，开销很大，
    """
    global _client#全局变量声明
    if _client is None:
        # 把 .env 里的相对路径转成绝对路径，保证任何目录启动都能找到
        abs_path = get_abs_path(VECTOR_DB_PATH)
        os.makedirs(abs_path,exist_ok=True)#创建一个目录（文件夹），如果目录已经存在，就不要报错
        _client = chromadb.PersistentClient(path=abs_path)#持久化存储，创建chromadb的客户端
                                                          #client = chromadb.Client():临时存储
        logger.info(f"ChromaDB初始化完成，持久化路径: {abs_path}")
    return _client
def _get_collection(agent_id:int):
    """获取某Agent的向量集合（每个Agent一个独立的 collection）
        ┌────────────┬──────────────────────┬──────────────────────┐
        │            │ 每个Agent一个collection │ 共享+metadata过滤    │
        ├────────────┼──────────────────────┼──────────────────────┤
        │ 数据隔离    │ 物理隔离，绝对安全     │ 逻辑隔离，容易写漏过滤  │
        │ 删除Agent   │ 直接删collection，快   │ metadata删除，慢且漏   │
        │ 检索性能    │ 每个collection小，检索快│ 集合越来越大，检索变慢 │
        └────────────┴──────────────────────┴──────────────────────┘。"""
    client =  _get_client()
    # ChromaDB的collection名只允许 字母/数字/下划线/横线
    collection_name = f"agent_{agent_id}_knowledge"
    # get_or_create：存在就取，不存在就建（幂等，重复调用不报错）
    collection = client.get_or_create_collection(
        name = collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return collection
def add_vectors(
        agent_id:int,vectors:List[List[float]],
        ids:List[str],documents:List[str],metadatas:List[Dict[str,Any]]=None
)->None:
    """批量存入向量
    :param agent_id: 哪个Agent的知识库（决定存到哪个collection）
    :param vectors: 向量列表（256维float列表的列表）
    :param ids: 每个向量的唯一ID，和 knowledge_chunk.vector_id 一一对应
    :param documents: 原始文本（ChromaDB会存一份，调试和直接取内容方便）
    :param metadatas: 元数据列表，如 [{"knowledge_id":1,"chunk_index":0}, ...]
    主要用于按文档删除"""
    collection =_get_collection(agent_id)
    # ChromaDB单次add有限制（内存限制），每100条一批
    BATCH =100
    for i in range(0,len(vectors),BATCH):
        end = i+BATCH
        collection.add(
            embeddings=vectors[i:end],
            ids = ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end] if metadatas else None,
        )
    logger.info(f"Agent{agent_id} 存入 {len(vectors)} 条向量")
def search_similar(
        agent_id:int,query_vector:List[float],top_k:int=5,where:Dict=None
)->List[Dict[str,Any]]:
    """向量相似度检索
    :param agent_id: 在哪个Agent的知识库里查
    :param query_vector: 用户问题的向量（256维）
    :param top_k: 返回最相似的K条，默认5条
    :param where: metadata过滤条件，如 {"knowledge_id": 1} 只在某个文档内查
    :return: 按相似度排序的结果列表，每条含 id/document/distance/metadata
    distance越小 = 越相似（余弦距离范围0~2，0=完全相同）"""
    collection = _get_collection(agent_id)
    try:
        count = collection.count()
        if count <= 0:
            logger.info(f"Agent{agent_id} 向量集合为空，跳过检索")
            return []
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, count),
            where = where
        )
    except Exception as e:
        logger.error(f"Agent{agent_id} 向量检索失败: {e}")
        raise
    # ChromaDB返回格式比较深（嵌套list），这里拍平成方便用的结构
    flattened = []
    if results and results.get("ids") and results["ids"][0]:
        ids_list = results["ids"][0]
        docs_list = results.get("documents", [[]])[0] if results.get("documents") else [None] * len(ids_list)
        # distances 可能为 None 或不存在，用 0.0 兜底
        dist_raw = results.get("distances")
        dist_list = dist_raw[0] if dist_raw and dist_raw[0] else [0.0] * len(ids_list)
        meta_raw = results.get("metadatas")
        meta_list = meta_raw[0] if meta_raw and meta_raw[0] else [None] * len(ids_list)
        for i, vid in enumerate(ids_list):
            # 防御性：确保 distance 是 float
            dist = dist_list[i] if isinstance(dist_list[i], (int, float)) else 0.0
            flattened.append({
                "id": vid,
                "document": docs_list[i] if i < len(docs_list) else None,
                "distance": float(dist),
                "metadata": meta_list[i] if i < len(meta_list) else None,
            })
    return flattened#返回的平铺数据（多个列表）转换成一个个结构化结果对象
def delete_vectors_by_knowledge(agent_id:int,knowledge_id:int)->None:
    """删除某文档对应的所有向量（用metadata过滤）
      因为 add_vectors 时每条metadata都存了 {"knowledge_id": x, ...}
      ChromaDB支持按metadata条件批量删除，比先查id再逐个删快很多。"""
    collection = _get_collection(agent_id)
    collection.delete(where={"knowledge_id":knowledge_id})
    logger.info(f"Agent{agent_id} 删除文档{knowledge_id} 的所有向量")
def delete_collection(agent_id:int)->None:
    """删除某Agent的整个向量集合（删除Agent时调用）
       删整个collection比删所有向量快几个数量级。
       为什么要try/except？Agent可能从没上传过文档，collection不存在，
       这种情况不算错误，只记warning。"""
    client = _get_client()
    collection_name = f"agent_{agent_id}_knowledge"
    try:
        client.delete_collection(name=collection_name)
        logger.info(f"删除Agent{agent_id}的向量集合")
    except Exception as e:
        logger.warning(f"删除向量集合失败（可能不存在）: {e}")
