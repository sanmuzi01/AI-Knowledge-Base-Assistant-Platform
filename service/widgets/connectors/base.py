"""数据源连接器基类。

统一接口：await fetch(ctx, config) -> raw_data
- raw_data 可以是 list / dict / str / number，交给 processor 继续处理。
- 需要按当前用户过滤的连接器（system_stats / agent_runs），通过 ctx.db / ctx.user_id 拿数据。
- 连接器不信任 config：validate_config 负责挡掉非法配置，返回中文错误列表（空列表=通过）。
"""

from typing import Any, Dict, List

from service.widgets.context import WidgetRunContext


class BaseConnector:
    kind: str = ""
    label: str = ""
    needs_db: bool = False          # 是否依赖 ctx.db（按用户过滤的数据源）

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        return []
