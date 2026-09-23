"""
BGE 本地 Rerank 实现
对应模型：BAAI/bge-reranker-base / BAAI/bge-reranker-large / BAAI/bge-reranker-v2-m3
1. 本地跑模型（用 sentence-transformers 库），不需要API Key
2. 输入：(query, document) 对 → 输出：相关性分数（0~1之间，越高越相关）
3. 首次加载下载模型，之后本地加载
4. 重排序是RAG的"精排"：向量检索返回top_k=10条，Rerank再重新打分选出top_n=3条
向量检索靠向量相似度（余弦/欧氏距离）粗排，召回率高但精度低：
  - "深度学习是机器学习的分支"  和 "深度学习" → 向量很接近（得分高）✓
  - "机器学习包括决策树、SVM等"    和 "深度学习" → 向量也很接近（得分中等，但可能不相关）✗
Rerank模型是Cross-Encoder，同时看query和document，精度大幅提升：
  Cross-Encoder直接对(query,doc)打分，不生成向量，精度更高但速度更慢
  → 所以先Embedding粗排top_k=10，再Rerank精排top_n=3，平衡速度和精度
"""
from utils.logger_handler import get_logger
from typing import List, Tuple
from service.rag.rerank.base import BaseReranker
logger = get_logger("bge_rerank")
class BGEReranker(BaseReranker):
    """BGE本地Reranker客户端"""
    # 支持的模型列表（v2-m3支持中英双语，推荐）
    _SUPPORTED_MODELS = {
        "BAAI/bge-reranker-base",
        "BAAI/bge-reranker-large",
        "BAAI/bge-reranker-v2-m3",
    }
    def __init__(self,model_name:str = "BAAI/bge-reranker-v2-m3"):
        super().__init__(model_name)
        self._model = None   # 懒加载：第一次用才加载
    def _get_model(self):
        if self._model is None:
            #懒加载本地模型（第一次调用时加载，之后复用）
            from sentence_transformers import CrossEncoder
            logger.info(f"加载BGE Rerank模型: {self.model_name}（首次加载较慢，约几GB）")
            # CrossEncoder = Cross-Encoder = 同时输入query和doc一起编码打
            self._model = CrossEncoder(self.model_name)
            logger.info("BGE Rerank模型加载完成")
        return self._model
    def rerank(self,query:str,documents:List[str],top_n:int=3)->List[Tuple[int,float]]:
        """对documents重新打分排序，返回 (原始索引, 分数) 的列表，按分数从高到低
            :param query: 用户问题
            :param documents: 向量检索返回的文档内容列表
            :param top_n: 返回前N条（如果top_n>文档数，就全部返回）
            :return: [(原索引0, 分数0.92), (原索引3, 分数0.87), ...]
            上层调用时已经有完整的chunk信息（content、chunk_id、knowledge_id等），
            rerank只负责"排序"，不负责搬运数据。上层用返回的索引去原列表取数据，效率最高。
            """
        if not documents:
            return []
        # top_n不能超过文档数，也不能小于1
        top_n = max(1,min(top_n,len(documents)))
        # 组装输入对：[(query, doc1), (query, doc2), ...]
        # CrossEncoder的输入格式就是 句子对列表
        sentence_pairs = [(query,doc) for doc in documents]
        model = self._get_model()
        # 组装：(原索引, 分数) 然后按分数降序排序
        scores = model.predict(sentence_pairs)
        scored = [(idx, float(score)) for idx, score in enumerate(scores)]
        #按照 scored 里面每个元素的第 2 个值（分数）从高到低排序。
        scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)
        logger.info(
            f"Rerank完成: 输入{len(documents)}条 → 返回前{top_n}条, "
            f"最高分数={scored_sorted[0][1]:.4f}")
        return scored_sorted[:top_n]

# ========== 自动注册（和bge_embedding.py最后一段一样的写法） ==========
from service.rag.rerank.base import RerankRegistry

RerankRegistry.register(
    model_names=[
        "BAAI/bge-reranker-base",
        "BAAI/bge-reranker-large",
        "BAAI/bge-reranker-v2-m3",
    ],
    reranker_class=BGEReranker,
)
