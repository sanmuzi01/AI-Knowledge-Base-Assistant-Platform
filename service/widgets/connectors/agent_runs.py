"""数据源：当前用户的 Agent 运行记录统计。

按 ctx.user_id 过滤。既能出汇总指标，也能出「按天运行次数」的时间序列（给图表用）。
config:
  - days: 统计窗口天数，默认 14，范围 1~90
"""

from collections import Counter
from datetime import timedelta
from typing import Any, Dict, List

from sqlalchemy import select

from service.widgets.connectors.base import BaseConnector
from service.widgets.context import WidgetRunContext


class AgentRunsConnector(BaseConnector):
    kind = "agent_runs"
    label = "我的 AI 运行记录"
    needs_db = True

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        days = (config or {}).get("days", 14)
        if not isinstance(days, int) or not (1 <= days <= 90):
            return ["统计天数需要在 1~90 之间"]
        return []

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        if ctx.db is None:
            raise RuntimeError("agent_runs 数据源需要数据库连接")
        from models.init_db import AgentRun

        days = int((config or {}).get("days", 14))
        days = max(1, min(days, 90))
        since = ctx.now - timedelta(days=days - 1)

        result = await ctx.db.execute(
            select(
                AgentRun.id,
                AgentRun.status,
                AgentRun.total_steps,
                AgentRun.total_tokens,
                AgentRun.started_at,
            )
            .where(AgentRun.user_id == ctx.user_id, AgentRun.started_at >= since)
            .order_by(AgentRun.started_at.desc())
        )
        rows = result.all()

        status_counter: Counter = Counter()
        per_day: Counter = Counter()
        total_tokens = 0
        total_steps = 0
        for _id, status, steps, tokens, started_at in rows:
            status_counter[status or "unknown"] += 1
            total_tokens += int(tokens or 0)
            total_steps += int(steps or 0)
            if started_at:
                per_day[started_at.strftime("%Y-%m-%d")] += 1

        series = []
        for i in range(days):
            day = (since + timedelta(days=i)).strftime("%Y-%m-%d")
            series.append({"date": day, "value": per_day.get(day, 0)})

        run_count = len(rows)
        finished = status_counter.get("finished", 0)
        return {
            "window_days": days,
            "rows": series,
            "summary": {
                "runs": run_count,
                "finished": finished,
                "failed": status_counter.get("failed", 0),
                "success_rate": round(finished / run_count, 4) if run_count else None,
                "total_tokens": total_tokens,
                "avg_steps": round(total_steps / run_count, 2) if run_count else 0,
            },
            "by_status": dict(status_counter),
        }


CONNECTOR = AgentRunsConnector()
