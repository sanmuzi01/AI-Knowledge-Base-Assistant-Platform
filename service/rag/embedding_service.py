"""
嵌入服务编排层：把"取Key + 选模型 + 调工厂 + 调客户端"串起来
对外提供2个接口：embed_texts / embed_query

【这一层在架构中的位置】
  rag_service.py (业务编排)
        ↓
  embedding_service.py (嵌入编排 ← 你在这里)
        ↓
  EmbeddingFactory.create() (工厂分发)
        ↓
  ZhipuEmbedding/OpenAIEmbedding/BGEEmbedding (具体实现)
工厂只管"创建客户端"，但"用谁的Key、用哪个模型、怎么调用"是业务逻辑，
需要一个编排层封装。上层 rag_service 不用关心Key怎么来、用哪个厂商。
"""
import os
from typing import List
from dotenv import load_dotenv
from service.rag.embedding.factory import EmbeddingFactory
from service.rag.embedding.base import BaseEmbedding
from service.llm.llm_config_service import get_api_key, get_api_config, get_first_embedding_config
from utils.logger_handler import get_logger

load_dotenv()
logger = get_logger()
# 从 .env 读默认嵌入模型（用户没单独配 embedding-3 的Key时，用这个模型名查glm-4的Key）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "embedding-3")
def _get_embedding_api_key(db,user_id:int,model_name:str)->str:
    """
       获取Embedding的API Key（三级降级策略）
       下划线开头 = 内部函数，外部只该调 embed_texts / embed_query。
       场景1：用户想让 Chat 用 DeepSeek，Embedding 用智谱 → 单独配 embedding-3 的Key
       场景2：用户只配了 glm-4 → 智谱Key通用，自动复用，零额外配置
       场景3：啥都没配 → 明确报错
       :param model_name: 嵌入模型名（第1级用它查独立Key）
       :return: API Key 字符串，找不到返回 None"""
    api_key = get_api_key(db,user_id,model_name)
    if api_key:
        logger.info(f"使用独立配置的 {model_name} API Key")
        return api_key
    api_key = get_api_key(db,user_id,"glm-4")
    if api_key:
        logger.info(f"继承 glm-4 的 API Key 调用 {model_name}")
        return api_key
    return None

def _get_embedding_api_config(db, user_id: int, model_name: str):
    if not model_name:
        config = get_first_embedding_config(db, user_id)
        if config:
            logger.info(f"自动选择用户可用向量模型: {config['model_name']}")
            return config
        model_name = EMBEDDING_MODEL
    config = get_api_config(db, user_id, model_name)
    if config:
        logger.info(f"使用用户配置的 {model_name} API Key 调用RAG向量模型")
        return config
    api_key = get_api_key(db, user_id, "glm-4")
    if api_key:
        logger.info(f"未单独配置 {model_name}，复用用户 glm-4 API Key 调用RAG向量模型")
        return {"model_name": model_name, "api_key": api_key, "api_url": None}
    return None

def _get_client(db,user_id: int, model_name: str = None) -> BaseEmbedding:
    """
       拿到嵌入客户端（取Key → 调工厂 → 返回客户端）
       embed_texts 和 embed_query 都要"取Key + 调工厂"，抽出来复用，避免重复代码。
       :param model_name: 指定模型名，不传则用.env的默认配置
       :return: BaseEmbedding 实例
       """
    # 没指定模型就用.env默认配置
    actual_model = model_name or None
    api_config = _get_embedding_api_config(db,user_id,actual_model)
    if api_config:
        actual_model = api_config["model_name"]
    else:
        actual_model = EMBEDDING_MODEL
    api_key = api_config["api_key"] if api_config else None
    api_url = api_config.get("api_url") if api_config else None
    # 本地模型（BGE）不需要Key，但远程模型没Key必须报错
    if not api_key and not actual_model.startswith("BAAI/"):
        logger.error(f"用户{user_id}未配置API Key，无法调用 {actual_model}")
        raise ValueError(
            f"请先在【模型配置】中配置 {actual_model} 或 glm-4 的 API Key"
        )
    # 调工厂创建客户端
    client = EmbeddingFactory.create(
        model_name = actual_model,
        api_key=api_key,
        api_url=api_url,
    )
    return client
def embed_texts(
        db,user_id:int,texts:List[str],model_name:str = None
)->List[List[float]]:
    #批量把文本转成向量（文档入库时调用）
    if not texts:
        return []
    # 拿客户端（取Key + 调工厂）
    client = _get_client(db,user_id, model_name)
    # 调客户端的 embed_texts
    logger.info(f"调用 {client.model_name} 嵌入 {len(texts)} 条文本")
    vectors = client.embed_texts(texts)
    logger.info(f"嵌入完成，共 {len(vectors)} 条向量，维度={client.get_dimension()}")
    return vectors


async def aembed_texts(
        db, user_id: int, texts: List[str], model_name: str = None
) -> List[List[float]]:
    """异步批量嵌入，供 FastAPI 请求链路使用。"""

    if not texts:
        return []
    client = _get_client(db, user_id, model_name)
    logger.info(f"异步调用 {client.model_name} 嵌入 {len(texts)} 条文本")
    vectors = await client.aembed_texts(texts)
    logger.info(f"异步嵌入完成，共 {len(vectors)} 条向量，维度={client.get_dimension()}")
    return vectors

def embed_query(
        db,user_id:int,query:str,model_name:str=None
)->List[float]:
    """把单条用户问题转成向量（检索时调用）
    :return: 单个向量，空列表表示失败"""
    client = _get_client(db,user_id,model_name)
    logger.info(f"调用 {client.model_name} 嵌入查询: {query[:30]}...")
    vectors = client.embed_query(query)
    return vectors


async def aembed_query(
        db, user_id: int, query: str, model_name: str = None
) -> List[float]:
    """异步把单条用户问题转成向量。"""

    client = _get_client(db, user_id, model_name)
    logger.info(f"异步调用 {client.model_name} 嵌入查询: {query[:30]}...")
    return await client.aembed_query(query)


