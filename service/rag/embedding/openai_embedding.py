"""
OpenAI Embedding 实现
对应模型：text-embedding-ada-002, text-embedding-3-small, text-embedding-3-large
和智谱
1. 端点不同：https://api.openai.com/v1/embeddings
2. 单次最多100条（智谱是64）
3. 维度参数名不同：OpenAI用 dimensions（智谱也是dimensions，但老模型不支持）
4. ada-002 固定1536维，不能指定维度
"""
import requests
from typing import List
import httpx
from service.rag.embedding.base import BaseEmbedding
from service.http_resilience import async_request_with_retry, request_with_retry
from utils.logger_handler import get_logger
logger = get_logger("openai_embedding")
class OpenAIEmbedding(BaseEmbedding):
    """OpenAI Embedding客户端"""
    OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
    BATCH_SIZE = 100        # OpenAI单次最多100条
    # 各模型默认维度（OpenAI不像智谱可以随意指定）
    _MODEL_DINS= {
        "text-embedding-ada-002": 1536,        # 老模型，固定1536维
        "text-embedding-3-small": 1536,        # 新模型，默认1536，可降维
        "text-embedding-3-large": 3072,        # 大模型，默认3072，可降维
    }
    def __init__(self,api_key:int,api_url:str =None,model_name:str="text-embedding-3-small"):
        super().__init__(api_key,api_url,model_name)
        # 根据模型名查默认维度
        self.dimension  = self._MODEL_DINS.get(model_name,1536)
    def get_dimension(self) ->int:
        return self.dimension
    def embed_texts(self,texts:List[str])->List[List[float]]:
        #批量文本→向量
        if not texts:
            return[]
        all_vectors = []
        for i in range(0,len(texts),self.BATCH_SIZE):
            batch = texts[i:i+self.BATCH_SIZE]
            vectors = self._call_api(batch)
            all_vectors.extend(vectors)
            logger.info(f"OpenAI嵌入批次 {i // self.BATCH_SIZE + 1} 完成，本批 {len(batch)} 条")
        logger.info(f"OpenAI嵌入完成，共 {len(all_vectors)} 条向量")
        return all_vectors
    def embed_query(self,query:str) ->List[float]:
        #文本里提取问
        vectors = self.embed_texts([query])
        return vectors[0] if vectors else []

    async def aembed_texts(self, texts: List[str]) -> List[List[float]]:
        """异步批量文本嵌入，适合 API 请求链路直接 await。"""

        if not texts:
            return []
        all_vectors = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i:i + self.BATCH_SIZE]
            vectors = await self._acall_api(batch)
            all_vectors.extend(vectors)
            logger.info(f"OpenAI异步嵌入批次 {i // self.BATCH_SIZE + 1} 完成，本批 {len(batch)} 条")
        logger.info(f"OpenAI异步嵌入完成，共 {len(all_vectors)} 条向量")
        return all_vectors

    async def aembed_query(self, query: str) -> List[float]:
        vectors = await self.aembed_texts([query])
        return vectors[0] if vectors else []

    def _call_api(self,texts:List[str])->List[List[float]]:
        """真正调OpenAI API
        1. URL不同
        2. ada-002不支持dimensions参数，所以有条件加
        3. 返回格式同样是 {data:[{embedding,index}]}，按index排序
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model":self.model_name,
            "input":texts
            # 只有 text-embedding-3-* 系列支持指定维度
            # ada-002 固定1536维，传dimensions会报错
        }
        try:
            # 支持自定义api_url（用户可能用代理或兼容服务）
            url = self.api_url or self.OPENAI_EMBEDDING_URL
            resp = request_with_retry(
                service_name=f"embedding:{self.model_name}",
                sender=lambda timeout: requests.post(url, headers=headers, json=payload, timeout=timeout),
                timeout_env="EMBEDDING_REQUEST_TIMEOUT_SECONDS",
                default_timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in embeddings]
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI Embedding API调用失败: {e}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"OpenAI Embedding响应格式异常: {e}")
            raise

    async def _acall_api(self, texts: List[str]) -> List[List[float]]:
        """异步调用 OpenAI Embedding API。"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "input": texts
        }
        try:
            url = self.api_url or self.OPENAI_EMBEDDING_URL
            resp = await async_request_with_retry(
                service_name=f"embedding:{self.model_name}",
                sender=lambda client: client.post(url, headers=headers, json=payload),
                timeout_env="EMBEDDING_REQUEST_TIMEOUT_SECONDS",
                default_timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in embeddings]
        except httpx.HTTPError as e:
            logger.error(f"OpenAI Embedding API异步调用失败: {e}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"OpenAI Embedding异步响应格式异常: {e}")
            raise
# ========== 自动注册 ==========
from service.rag.embedding.base import EmbeddingRegistry
EmbeddingRegistry.register(
    model_names=[
        "text-embedding-ada-002",
        "text-embedding-3-small",
        "text-embedding-3-large",
    ],
    client_class=OpenAIEmbedding,
)
