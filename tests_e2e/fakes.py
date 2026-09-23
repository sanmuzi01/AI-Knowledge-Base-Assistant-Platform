"""E2E 冒烟测试用的假模型：不调用任何真实大模型/向量 API，换成进程内确定性计算。

为什么不用 mock HTTP 服务器：LangChain 的 ChatOpenAI 对流式响应的 wire protocol 有自己的
一套期望（chunk 形状、usage 字段……），手搭一个 HTTP 服务器去精确模仿很容易在细节上翻车。
这里直接在 Python 层换掉创建 LLM / Embedding 客户端的那一步——用 LangChain 官方自带的测试替身
`FakeListChatModel`，以及一个基于词袋哈希的确定性 Embedding，两者都实现了和真实客户端完全一样的
接口，上层代码（ReAct 引擎、RAG 检索）完全不知道自己在跟假的打交道。
"""
import hashlib
import re
from typing import List, Optional

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from service.rag.embedding.base import BaseEmbedding

EMBEDDING_DIM = 64


def _hash_embed(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """词袋哈希向量：同一个词/字永远落在同一个维度上，共享的越多、余弦相似度越高。

    中文没有空格分词，`\\w+` 会把一整句中文当成一个不可分割的 token——两句只要不是
    逐字完全相同就零重合，query 和文档几乎永远匹配不上。所以中文按单字切（保留英文/
    数字按连续串切），"专业版多少钱"和"专业版一年授权的价格"才会因为共享单字而有重合。
    不追求语义理解（这是冒烟测试，不是评测模型质量），只要"内容相关的文本向量更接近"
    这一条对 ChromaDB 的最近邻检索成立就够了。
    """
    vec = [0.0] * dim
    tokens = re.findall(r"[a-zA-Z0-9]+|[一-鿿]", (text or "").lower()) or [text or ""]
    for w in tokens:
        idx = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % dim
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


class FakeEmbedding(BaseEmbedding):
    """本地确定性 Embedding，不发任何网络请求。"""

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None,
                model_name: str = "fake-embedding"):
        super().__init__(api_key, api_url, model_name)

    def get_dimension(self) -> int:
        return EMBEDDING_DIM

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [_hash_embed(t) for t in (texts or [])]

    def embed_query(self, query: str) -> List[float]:
        return _hash_embed(query)

    async def aembed_texts(self, texts: List[str]) -> List[List[float]]:
        return self.embed_texts(texts)

    async def aembed_query(self, query: str) -> List[float]:
        return self.embed_query(query)


class _FakeToolCapableChatModel(FakeListChatModel):
    """`FakeListChatModel` 没实现 `bind_tools`（基类默认直接 raise NotImplementedError）——
    Agent 只要绑了一个技能（哪怕技能只带一个工具），ReActEngine 初始化时就会调
    `llm.bind_tools(tools)`，不重载这个方法整个对话请求直接 500。
    冒烟测试不需要模型真的发起工具调用（回答一次到位、不进 tool 分支），
    所以这里"绑定"只是把工具签名记下来、原样返回自己，不做真正的函数调用适配。
    """

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001 - 签名跟随基类，无需强类型
        return self


def make_fake_chat_model(answer: str) -> FakeListChatModel:
    """每次调用都回同一句话——够冒烟测试用：只关心"回答完整地流出来了、citations 事件带上了"，
    不关心模型有没有真的读懂资料（真实理解能力不是这条测试要验证的东西）。
    """
    return _FakeToolCapableChatModel(responses=[answer])
