"""
RAG编排服务：把文档解析→切分→嵌入→向量存储→DB存储 全部串起来
对外提供3个高级接口：
  upload_and_index()              上传文档并入库
  search()                        根据问题检索知识片段
  delete_knowledge_completely()   彻底删除文档（向量库+chunks+knowledge记录）
这一层在架构中的位置
  路由层 (FasdtApi/knowledge.py)
        ↓
  rag_service.py (业务编排 ← 你在这里)
        ↓
  embedding_service + vector_store_service + knowledge_dao + knowledge_chunk_dao
        ↓
  智谱API + ChromaDB + MySQL
路由层不该关心"怎么切分文档""怎么调嵌入API"，
这些业务逻辑封装在这里，路由层只调 upload_and_index() / search()。
"""
import os
import uuid
from typing import List,Dict,Any
from dotenv import load_dotenv
from service.rag.rerank.factory import RerankFactory
from models.knowledge_chunk_dao import create_chunks_batch, get_chunks_by_vector_ids, delete_chunks_by_knowledge
from utils.logger_handler import get_logger
from utils.path_tool import get_abs_path
# 导入 RAG 底层两层能力
from service.rag.embedding_service import embed_texts,embed_query
from service.rag.embedding_service import aembed_query, aembed_query_async
from service.rag.vector_store_service import (add_vectors,search_similar,delete_vectors_by_knowledge,space_collection_key)
# 导入 DAO（4层架构：Service层只调DAO，不直接碰 ORM）
from models.knowledge_dao import (
    create_knowledge,get_knowledge_by_id,
    delete_knowledge as dao_delete_knowledge,
    update_knowledge_status)

load_dotenv()
# 上传的原始文档保存在哪（磁盘）
KNOWLEDGE_FILE_PATH = os.getenv("KNOWLEDGE_FILE_PATH","./knowledge_files")
# 切块参数
CHUNK_SIZE = 500        # 每块约500字符（用户没自选时的默认）
CHUNK_OVERLAP = 50      # 相邻块重叠50字符（防止一句话被切断）
CHUNK_SIZE_MIN = 120    # 用户可选切块大小下限
CHUNK_SIZE_MAX = 2000   # 上限


def _effective_chunk_params(knowledge) -> tuple:
    """按文档的 chunk_size（用户自选）解析出 (chunk_size, overlap)，越界夹紧，None 用默认。

    overlap 固定 CHUNK_OVERLAP，仅在 chunk 很小时按 size//4 缩小（保证 overlap < size）。
    """
    raw = getattr(knowledge, "chunk_size", None)
    size = CHUNK_SIZE if not raw else max(CHUNK_SIZE_MIN, min(int(raw), CHUNK_SIZE_MAX))
    overlap = min(CHUNK_OVERLAP, size // 4)
    return size, overlap


def clamp_chunk_size(value) -> "int | None":
    """路由层入口校验：把用户传的 chunk_size 夹到合法区间；空/非法 → None（用默认）。"""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(CHUNK_SIZE_MIN, min(n, CHUNK_SIZE_MAX))
RAG_RERANK_ENABLED = os.getenv("RAG_RERANK_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
RAG_RERANK_MODEL = os.getenv("RAG_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
logger = get_logger("rag_service")
# ========== 获取 Rerank Client ==========
_rerank_client = None
def _get_rerank_client():
    """获取Rerank客户端（本地BGE模型，不需要Key）"""
    global _rerank_client
    if not RAG_RERANK_ENABLED:
        logger.info("Rerank未启用，跳过重排序")
        return None
    if _rerank_client is not None:
        return _rerank_client
    try:
        logger.info(f"Rerank已启用，开始加载模型: {RAG_RERANK_MODEL}")
        _rerank_client = RerankFactory.create(RAG_RERANK_MODEL)
        return _rerank_client
    except Exception as e:
        logger.warning(f"创建Reranker失败: {e}，将跳过重排序")
        return None
# ========== 文档解析（不同文件类型用不同库） ==========
def _parse_pdf(file_path:str)->str:
    """解析PDF成纯文本"""
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    text=""
    for page in reader.pages:#当前 PDF 文件里面所有页面的列表。
        text += (page.extract_text() or "") + "\n\n"# extract_text() 返回每页文字，末尾加换行分隔页
    return text
def _parse_docx(file_path:str)->str:
    """解析 Word(.docx) 成纯文本"""
    import docx
    doc = docx.Document(file_path)
    # paragraph 是每一段，跳过空段
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
def _parse_txt(file_path:str)->str:
    """解析纯文本 / Markdown"""
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()
def parse_document(file_path:str,file_type:str)->str:#文件在哪里 和 文件是什么类型
    """根据文件类型选择解析器
      新增文件类型时只加一行 key-value，不用改 if 结构。
      而且抛错时能直接给出"不支持的类型"，不用写默认else。
      """
    parsers = {
        "pdf": _parse_pdf,
        "docx": _parse_docx,
        "txt": _parse_txt,
        "md": _parse_txt,  # markdown 和纯文本解析方式一
    }
    parser = parsers.get(file_type)
    if parser is None:
        raise ValueError(f"不支持的文件类型: {file_type}，支持: {list(parsers.keys())}")
    return parser(file_path)
# ========== 文本切分 ==========
def split_text(
        text:str,chunk_size:int = CHUNK_SIZE,
        overlap:int = CHUNK_OVERLAP
)->List[str]:
    #    按固定字符长度切分 + 重叠
    if not text or not text.strip():
        return []
    chunks = []
    start = 0
    while start<len(text):
        end = start+chunk_size
        chunk = text[start:end]
    # strip() 去掉块首尾的空白字符（很多文档有大量无用空行/空格）
        chunks.append(chunk.strip())
    # strip() 去掉块首尾的空白字符（很多文档有大量无用空行/空格）
        start = end-overlap
    # 过滤掉太短的块小于十个字符的多半是切分后的残留空白）
    chunks = [c for c in chunks if len(c)>10]
    logger.info(f"文本切分完成：{len(chunks)} 块，每块约 {chunk_size} 字")
    return chunks
# ========== 上传入库完整流程（核心） ==========
def _vector_key(knowledge):
    """向量集合键：优先 space_<id>，否则回退旧 agent_id。"""
    sid = getattr(knowledge, "space_id", None)
    return space_collection_key(sid) if sid else knowledge.agent_id


def upload_and_index(
        db,user_id:int,agent_id,file_name:str,file_content:bytes,file_type:str
)->Dict[str,Any]:#返回字典
    knowledge = prepare_upload(db, user_id, agent_id, file_name, file_content, file_type)
    return index_existing_knowledge(db, user_id, agent_id, knowledge.id)


def prepare_upload(db, user_id: int, agent_id, file_name: str,
                   file_content: bytes, file_type: str, *, space_id: int = None,
                   category: str = None, tags_json: str = None, version: str = None,
                   source_type: str = "upload", source_url: str = None,
                   chunk_size: int = None):
    """保存原文件并创建 pending 文档记录，不执行耗时入库。"""
    file_dir = get_abs_path(KNOWLEDGE_FILE_PATH)
    os.makedirs(file_dir,exist_ok=True)#创建文件目录，如果文件夹存在则不报错
    safe_name = f"{uuid.uuid4().hex}_{file_name}"
    file_path = os.path.join(file_dir, safe_name)#把文件夹路径和文件名拼接成完整文件路径。
    with open(file_path,"wb") as f:
        f.write(file_content)#文本内容打开写入二进制文件真是内容
    file_size = len(file_content)
    # ---------- 第2步：DB 建 knowledge 记录（status=pending） ----------
    knowledge = create_knowledge(
        db, user_id=user_id, agent_id=agent_id, file_name=file_name,
        file_path=file_path, file_type=file_type, file_size=file_size,
        space_id=space_id, category=category, tags_json=tags_json, version=version,
        source_type=source_type, source_url=source_url,
        chunk_size=clamp_chunk_size(chunk_size),
    )
    logger.info(f"创建待入库文档: knowledge_id={knowledge.id}, file={file_name}")
    return knowledge


def index_existing_knowledge(db, user_id: int, agent_id: int, knowledge_id: int) -> Dict[str, Any]:
    """解析已有文档并写入 chunks + 向量。"""
    knowledge = get_knowledge_by_id(db, knowledge_id)
    if not knowledge or knowledge.user_id != user_id or (agent_id is not None and knowledge.agent_id != agent_id):
        raise ValueError("文档不存在或无权限")
    if not os.path.exists(knowledge.file_path):
        update_knowledge_status(db, knowledge, "failed", error_msg="原始文件已丢失，请重新上传这份资料。")
        raise ValueError("原始文件已丢失，请重新上传这份资料。")
    try:
        # ---------- 第3步：更新状态 processing ----------
        update_knowledge_status(db,knowledge,"processing")#数据库，知识库文件记录，状态
        db.flush()
        # ---------- 第4步：解析文档 ----------
        text = parse_document(knowledge.file_path, knowledge.file_type)#文件路径和文件类型
        if not text.strip():
            raise ValueError("没读到文字内容。若是扫描件 / 图片版 PDF，请先用 OCR 转成可复制的文字再上传。")
        # ---------- 第5步：切分（按文档自选 chunk_size，没选用默认） ----------
        _cs, _ov = _effective_chunk_params(knowledge)
        chunks_text = split_text(text, chunk_size=_cs, overlap=_ov)
        if not chunks_text:
            raise ValueError("文档里几乎没有有效文字（可能太短，或全是空白 / 表格图片）。")
        # ---------- 第6步：批量嵌入（调智谱API，可能耗时） ----------
        vectors = embed_texts(db,user_id,chunks_text)
        # ---------- 第7步：存向量到 ChromaDB ----------
        # 构造有意义的 vector_id：k{knowledge_id}_c{chunk_index}
        vector_ids = [f"k{knowledge.id}_c{i}" for i in range(len(chunks_text))]#每条向量的唯一ID
        # metadata：存 knowledge_id 和 chunk_index，后面按文档删向量要用
        metadatas = [
            {"knowledge_id": knowledge.id, "chunk_index": i}
            for i in range(len(chunks_text))
        ]#给每个向量附加额外信息。
        add_vectors(
            agent_id = _vector_key(knowledge),vectors=vectors,
            ids=vector_ids,documents=chunks_text,metadatas=metadatas)
        # ---------- 第8步：批量存 chunks 到 MySQL ----------
        chunk_records=[
            {
                "knowledge_id": knowledge.id,
                "chunk_index": i,
                "content": chunks_text[i],
                "vector_id": vector_ids[i],
                "token_count": len(chunks_text[i]) // 2,  # 粗估：中文每2字符≈1token
            }
            for i in range(len(chunks_text))
        ]
        create_chunks_batch(db,chunk_records)
        # ---------- 第9步：更新状态 done，回填 chunk_count ----------
        update_knowledge_status(db,knowledge,"done",chunk_count=len(chunks_text))
        logger.info(f"文档入库成功: knowledge_id={knowledge.id}, chunks={len(chunks_text)}")
        return {
            "knowledge_id": knowledge.id,
            "chunk_count": len(chunks_text),
            "message": "上传并入库成功",
        }
    except Exception as e:
        # ---------- 任何一步失败：把状态标成 failed ----------
        update_knowledge_status(db,knowledge,"failed", error_msg=str(e))
        logger.error(f"文档入库失败: knowledge_id={knowledge.id}, error={e}")
        # 继续向上抛异常，让路由层返回给用户
        raise
    # ========== 检索流程（RAG的"查"） ==========


def reindex_knowledge(db, user_id: int, agent_id: int, knowledge_id: int) -> Dict[str, Any]:
    """重新解析已有文件并重建 chunks + 向量。"""
    knowledge = get_knowledge_by_id(db, knowledge_id)
    if not knowledge or knowledge.user_id != user_id or (agent_id is not None and knowledge.agent_id != agent_id):
        raise ValueError("文档不存在或无权限")
    if not os.path.exists(knowledge.file_path):
        update_knowledge_status(db, knowledge, "failed", error_msg="原始文件已丢失，请重新上传这份资料。")
        raise ValueError("原始文件已丢失，请重新上传这份资料。")

    try:
        update_knowledge_status(db, knowledge, "processing", chunk_count=0)
        db.flush()
        try:
            delete_vectors_by_knowledge(_vector_key(knowledge), knowledge_id)
        except Exception as e:
            logger.warning(f"重建索引时删除旧向量失败，继续重建: {e}")
        delete_chunks_by_knowledge(db, knowledge_id)

        text = parse_document(knowledge.file_path, knowledge.file_type)
        if not text.strip():
            raise ValueError("没读到文字内容。若是扫描件 / 图片版 PDF，请先用 OCR 转成可复制的文字再上传。")
        _cs, _ov = _effective_chunk_params(knowledge)
        chunks_text = split_text(text, chunk_size=_cs, overlap=_ov)
        if not chunks_text:
            raise ValueError("文档里几乎没有有效文字（可能太短，或全是空白 / 表格图片）。")

        vectors = embed_texts(db, user_id, chunks_text)
        vector_ids = [f"k{knowledge.id}_c{i}" for i in range(len(chunks_text))]
        metadatas = [
            {"knowledge_id": knowledge.id, "chunk_index": i}
            for i in range(len(chunks_text))
        ]
        add_vectors(
            agent_id=_vector_key(knowledge),
            vectors=vectors,
            ids=vector_ids,
            documents=chunks_text,
            metadatas=metadatas,
        )
        chunk_records = [
            {
                "knowledge_id": knowledge.id,
                "chunk_index": i,
                "content": chunks_text[i],
                "vector_id": vector_ids[i],
                "token_count": len(chunks_text[i]) // 2,
            }
            for i in range(len(chunks_text))
        ]
        create_chunks_batch(db, chunk_records)
        update_knowledge_status(db, knowledge, "done", chunk_count=len(chunks_text))
        logger.info(f"文档重建索引成功: knowledge_id={knowledge.id}, chunks={len(chunks_text)}")
        return {
            "knowledge_id": knowledge.id,
            "chunk_count": len(chunks_text),
            "message": "重新入库成功",
        }
    except Exception as e:
        update_knowledge_status(db, knowledge, "failed", error_msg=str(e))
        logger.error(f"文档重建索引失败: knowledge_id={knowledge.id}, error={e}")
        raise


def search(
        db,user_id:int,agent_id:int ,query:str,top_k:int = 5, knowledge_id:int = None
)->List[Dict[str,Any]]:
    """完整检索（4步）：
        用户问题向量化,向量库相似度检索（拿到 vector_id 列表）
        反查 MySQL 拿完整 chunk 内容 + 按相似度排序,Rerank重排序（如果Reranker可用）
       """
    # 第1步：问题向量化
    if not query or not query.strip():
        raise ValueError("检索关键词不能为空")
    query_vector = embed_query(db,user_id,query)
    return _build_search_results(db, agent_id, query, top_k, query_vector, knowledge_id)


def _build_search_results(
        db, agent_id: int, query: str, top_k: int,
        query_vector: List[float], knowledge_id: int = None,
) -> List[Dict[str, Any]]:
    """根据已经生成好的查询向量完成向量检索、DB 反查和可选重排。"""

    if not query_vector:
        return []
    logger.info(f"开始检索: agent={agent_id}, query='{query[:50]}...', top_k={top_k}")
    retrieve_count = max(10, top_k * 2) if RAG_RERANK_ENABLED else top_k
    where = {"knowledge_id": knowledge_id} if knowledge_id is not None else None
    results = search_similar(agent_id, query_vector, top_k=retrieve_count, where=where)
    if not results:
        logger.info(f"向量检索无命中: agent={agent_id}, query='{query[:50]}...'")
        return []
    logger.info(f"向量检索完成: agent={agent_id}, 命中{len(results)}条")

    vector_ids = [r["id"] for r in results]
    chunks = get_chunks_by_vector_ids(db, vector_ids)
    knowledge_ids = {chunk.knowledge_id for chunk in chunks}
    knowledge_map = {
        kid: get_knowledge_by_id(db, kid)
        for kid in knowledge_ids
    }
    chunk_map = {c.vector_id: c for c in chunks}
    final = []
    for r in results:
        chunk = chunk_map.get(r["id"])
        knowledge = knowledge_map.get(chunk.knowledge_id) if chunk else None
        if chunk and knowledge and knowledge.is_enabled != 0:
            final.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "score": max(0.0, 1.0 - float(r["distance"])),
                "distance": r["distance"],
                "knowledge_id": chunk.knowledge_id,
                "chunk_index": chunk.chunk_index,
            })
    if not final:
        logger.info(f"向量命中但未在MySQL找到chunk: agent={agent_id}, vector_ids={vector_ids[:5]}")
        return []

    reranker = _get_rerank_client()
    if reranker and len(final) > 1:
        doc_contents = [item["content"] for item in final]
        reranked = reranker.rerank(query, doc_contents, top_n=len(final))
        new_final = []
        for original_idx, rerank_score in reranked:
            if original_idx < len(final):
                item = final[original_idx].copy()
                item["score"] = rerank_score
                new_final.append(item)
        final = new_final[:top_k]
        logger.info(
            f"Rerank重排完成: {len(doc_contents)}条 → {len(final)}条, "
            f"Rerank最高分数={final[0]['score']:.4f}"
        )

    logger.info(f"检索完成: agent={agent_id}, query='{query[:20]}...', 命中{len(final)}条")
    for item in final:
        knowledge = knowledge_map.get(item["knowledge_id"])
        item["file_name"] = knowledge.file_name if knowledge else ""
        item["file_type"] = knowledge.file_type if knowledge else ""
    return final


async def async_search(
        db, user_id: int, agent_id: int, query: str,
        top_k: int = 5, knowledge_id: int = None,
) -> List[Dict[str, Any]]:
    """异步检索入口。

    查询向量化是最容易阻塞请求的远程 HTTP 调用，优先使用异步客户端。
    本地 ChromaDB 和当前同步 SQLAlchemy DAO 保持同步调用，后续切 async ORM 时只改这里。
    """

    if not query or not query.strip():
        raise ValueError("检索关键词不能为空")
    query_vector = await aembed_query(db, user_id, query)
    return _build_search_results(db, agent_id, query, top_k, query_vector, knowledge_id)


async def search_async(
        db, user_id: int, agent_id: int, query: str,
        top_k: int = 5, knowledge_id: int = None,
) -> List[Dict[str, Any]]:
    """彻底 async 版检索：`db` 为 AsyncSession。

    向量化走 async 客户端 + async 配置查询；chunk / knowledge 反查走 async DAO；
    ChromaDB 相似度检索与 rerank 仍同步，统一封 `asyncio.to_thread`。
    行为与同步 `search` 逐条对齐。
    """
    if not query or not query.strip():
        raise ValueError("检索关键词不能为空")
    query_vector = await aembed_query_async(db, user_id, query)
    return await _build_search_results_async(db, agent_id, query, top_k, query_vector, knowledge_id)


async def _build_search_results_async(
        db, agent_id: int, query: str, top_k: int,
        query_vector: List[float], knowledge_id: int = None,
) -> List[Dict[str, Any]]:
    """`_build_search_results` 的 AsyncSession 版。"""
    import asyncio

    from models.knowledge_async_dao import (
        get_chunks_by_vector_ids_async, get_knowledge_by_id_async,
    )

    if not query_vector:
        return []
    logger.info(f"开始检索(async): agent={agent_id}, query='{query[:50]}...', top_k={top_k}")
    retrieve_count = max(10, top_k * 2) if RAG_RERANK_ENABLED else top_k
    where = {"knowledge_id": knowledge_id} if knowledge_id is not None else None
    results = await asyncio.to_thread(
        search_similar, agent_id, query_vector, retrieve_count, where,
    )
    if not results:
        logger.info(f"向量检索无命中(async): agent={agent_id}, query='{query[:50]}...'")
        return []
    logger.info(f"向量检索完成(async): agent={agent_id}, 命中{len(results)}条")

    vector_ids = [r["id"] for r in results]
    chunks = await get_chunks_by_vector_ids_async(db, vector_ids)
    knowledge_ids = {chunk.knowledge_id for chunk in chunks}
    knowledge_map = {kid: await get_knowledge_by_id_async(db, kid) for kid in knowledge_ids}
    chunk_map = {c.vector_id: c for c in chunks}
    final = []
    for r in results:
        chunk = chunk_map.get(r["id"])
        knowledge = knowledge_map.get(chunk.knowledge_id) if chunk else None
        if chunk and knowledge and knowledge.is_enabled != 0:
            final.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "score": max(0.0, 1.0 - float(r["distance"])),
                "distance": r["distance"],
                "knowledge_id": chunk.knowledge_id,
                "chunk_index": chunk.chunk_index,
            })
    if not final:
        logger.info(f"向量命中但未在MySQL找到chunk(async): agent={agent_id}, vector_ids={vector_ids[:5]}")
        return []

    reranker = _get_rerank_client()
    if reranker and len(final) > 1:
        doc_contents = [item["content"] for item in final]
        reranked = await asyncio.to_thread(reranker.rerank, query, doc_contents, len(final))
        new_final = []
        for original_idx, rerank_score in reranked:
            if original_idx < len(final):
                item = final[original_idx].copy()
                item["score"] = rerank_score
                new_final.append(item)
        final = new_final[:top_k]
        logger.info(
            f"Rerank重排完成(async): {len(doc_contents)}条 → {len(final)}条, "
            f"Rerank最高分数={final[0]['score']:.4f}"
        )

    logger.info(f"检索完成(async): agent={agent_id}, query='{query[:20]}...', 命中{len(final)}条")
    for item in final:
        knowledge = knowledge_map.get(item["knowledge_id"])
        item["file_name"] = knowledge.file_name if knowledge else ""
        item["file_type"] = knowledge.file_type if knowledge else ""
    return final
# ========== 彻底删除文档 ==========
def delete_knowledge_completely(
        db,agent_id:int,knowledge_id:int
)->Dict[str,Any]:
    """
    彻底删除文档,按三层顺序删。先删最危险的（容易漏的向量库），再往内一层层删。
    """
    knowledge = get_knowledge_by_id(db,knowledge_id)
    if not knowledge:
        return {"message": "文档不存在"}
    # 1. 删向量库（即使失败也继续，保证DB记录被清）
    try:
        delete_vectors_by_knowledge(_vector_key(knowledge),knowledge_id)
    except Exception as e:
        logger.warning(f"删向量库失败（继续删DB）: {e}")
    # 2. 删 chunks
    deleted_chunks=delete_chunks_by_knowledge(db,knowledge_id)
    # 3. 删 knowledge 主记录
    dao_delete_knowledge(db,knowledge)
    logger.info(
        f"文档彻底删除: knowledge_id={knowledge_id}, 删除chunks={deleted_chunks}"
    )
    return {"message": "删除成功", "deleted_chunks": deleted_chunks}
