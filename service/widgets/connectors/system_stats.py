"""数据源：当前用户的系统 / 使用概览。

按 ctx.user_id 过滤，只能看到自己的数据。复用 user_dashboard_async_service。
"""

from typing import Any, Dict

from service.widgets.connectors.base import BaseConnector
from service.widgets.context import WidgetRunContext


class SystemStatsConnector(BaseConnector):
    kind = "system_stats"
    label = "我的使用与运行概览"
    needs_db = True

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        if ctx.db is None:
            raise RuntimeError("system_stats 数据源需要数据库连接")
        from service.user_dashboard_async_service import get_user_dashboard

        dashboard = await get_user_dashboard(ctx.db, ctx.user_id)
        counts = dashboard.get("counts", {})
        status = dashboard.get("status", {})
        return {
            "generated_for": ctx.user_id,
            "health_score": status.get("health_score"),
            "counts": counts,
            "status": status,
            "recent_runs": dashboard.get("recent_runs", []),
            "recent_tasks": dashboard.get("recent_tasks", []),
        }


CONNECTOR = SystemStatsConnector()
