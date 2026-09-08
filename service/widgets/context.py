"""组件运行上下文。

connector 和 processor 都通过 WidgetRunContext 拿到必要信息，而不是各自去摸全局。
这样以后加事件触发 / Webhook 触发 / Worker 定时触发，只要构造好 context 再调
run_widget 即可，连接器和处理器代码完全不用动。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class WidgetRunContext:
    user_id: int
    now: datetime
    widget_id: Optional[int] = None
    widget_type: Optional[str] = None
    db: Any = None                       # AsyncSession，供 system_stats / agent_runs 等按用户过滤的数据源使用
    request_id: Optional[str] = None
    trigger: str = "manual"             # manual / hourly / daily / event / webhook ...
    extra: Dict[str, Any] = field(default_factory=dict)
