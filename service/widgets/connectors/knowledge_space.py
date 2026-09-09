"""数据源：某个知识库空间的健康分。

按 ctx.user_id 隔离：health_service.health_snapshot 内部走 access_control.get_owned_space，
不属于当前用户的空间会抛 PermissionError -> PermissionDenied。

健康分计算只读 DB（knowledge / rag_debug_samples），是同步子系统，这里经 asyncio.to_thread
跨线程调用，本模块不出现同步 Session。

config:
  - space_id: 必填，要看哪个知识库空间的健康分
"""

import asyncio
from typing import Any, Dict, List

from service.widgets.connectors.base import BaseConnector
from service.widgets.context import WidgetRunContext


class KnowledgeSpaceConnector(BaseConnector):
    kind = "knowledge_space"
    label = "知识库健康"
    needs_db = True

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        space_id = (config or {}).get("space_id")
        if not isinstance(space_id, int) or space_id <= 0:
            return ["请选择要监控的知识库空间（space_id）"]
        return []

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        from service.exceptions import PermissionDenied
        from service.knowledge_space.health_service import health_snapshot

        space_id = int((config or {}).get("space_id"))
        try:
            snap = await asyncio.to_thread(health_snapshot, ctx.user_id, space_id, persist=False)
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc

        docs = snap["documents"]
        retr = snap["retrieval"]
        # 指标卡 / 表格通用形状：summary 给单值卡，rows 给明细
        return {
            "space_id": space_id,
            "health_score": snap["health_score"],
            "level": snap["level"],
            "summary": {
                "health_score": snap["health_score"],
                "documents": docs["total"],
                "failed": docs["failed"],
                "stale": docs["stale"],
                "hit_rate": retr["hit_rate"],
                "refuse_rate": retr["refuse_rate"],
            },
            "rows": [
                {"metric": "健康分", "value": snap["health_score"]},
                {"metric": "文档总数", "value": docs["total"]},
                {"metric": "已入库", "value": docs["done"]},
                {"metric": "入库失败", "value": docs["failed"]},
                {"metric": "久未更新", "value": docs["stale"]},
                {"metric": "调试样例数", "value": retr["sample_count"]},
                {"metric": "检索命中率", "value": retr["hit_rate"]},
                {"metric": "拒答率", "value": retr["refuse_rate"]},
            ],
            "fetched_at": ctx.now.strftime("%Y-%m-%d %H:%M:%S"),
        }


CONNECTOR = KnowledgeSpaceConnector()
