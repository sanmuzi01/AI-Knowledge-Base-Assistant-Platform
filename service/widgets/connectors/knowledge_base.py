"""数据源：从「我的知识库」按问题检索。

按 ctx.user_id 过滤：只能检索属于当前用户的 Agent 的知识库。

同步/异步边界：RAG 检索链路（向量化 + ChromaDB + 同步 DAO + rerank）是同步子系统，
统一入口在 service.rag.widget_search.search_for_widget（自带同步 Session + 归属校验）。
这里通过 asyncio.to_thread 跨线程调用，本模块不出现任何同步 Session。

config:
  - agent_id: 必填，要检索哪个 Agent 的知识库
  - query:    必填，检索问题
  - top_k:    选填，返回条数，默认 5，范围 1~10
"""

import asyncio
from typing import Any, Dict, List

from utils.logger_handler import get_logger
from service.widgets.connectors.base import BaseConnector
from service.widgets.context import WidgetRunContext

logger = get_logger("widget_knowledge_connector")


class KnowledgeBaseConnector(BaseConnector):
    kind = "knowledge_base"
    label = "我的知识库"
    needs_db = True

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        config = config or {}
        errors: List[str] = []
        agent_id = config.get("agent_id")
        if not isinstance(agent_id, int) or agent_id <= 0:
            errors.append("请选择要检索的知识库（agent_id）")
        if not str(config.get("query") or "").strip():
            errors.append("请填写要在知识库里检索的问题")
        top_k = config.get("top_k", 5)
        if not isinstance(top_k, int) or not (1 <= top_k <= 10):
            errors.append("知识库返回条数需要在 1~10 之间")
        return errors

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        from service.rag.widget_search import search_for_widget

        config = config or {}
        agent_id = int(config.get("agent_id"))
        query = str(config.get("query") or "").strip()
        top_k = max(1, min(int(config.get("top_k") or 5), 10))

        try:
            hits = await asyncio.to_thread(search_for_widget, ctx.user_id, agent_id, query, top_k)
        except PermissionError as exc:
            raise RuntimeError(str(exc)) from exc

        return {
            "query": query,
            "agent_id": agent_id,
            "hit_count": len(hits),
            "rows": hits,
            "fetched_at": ctx.now.strftime("%Y-%m-%d %H:%M:%S"),
        }


CONNECTOR = KnowledgeBaseConnector()
