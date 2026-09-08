"""内置示例数据源。

作用：保证演示永远能跑（不依赖任何外部服务）。按 series 名生成一段确定性的、
看起来真实的时间序列。金价只是其中一个 series 名，逻辑不为金价写死。
"""

import hashlib
import math
from datetime import timedelta
from typing import Any, Dict, List

from service.widgets.connectors.base import BaseConnector
from service.widgets.context import WidgetRunContext

# series 名 -> (基准值, 波动幅度, 单位)。加新 series 只是加一行。
_SERIES_PROFILE: Dict[str, Any] = {
    "gold_price": (1900.0, 45.0, "USD/oz"),
    "usd_cny": (7.15, 0.06, "CNY"),
    "btc_price": (63000.0, 3500.0, "USD"),
    "temperature": (26.0, 6.0, "°C"),
    "generic": (100.0, 12.0, ""),
}


def _seeded_walk(series: str, points: int) -> List[float]:
    base, amp, _unit = _SERIES_PROFILE.get(series, _SERIES_PROFILE["generic"])
    seed = int(hashlib.sha256(series.encode("utf-8")).hexdigest(), 16) % 100000
    values: List[float] = []
    for i in range(points):
        wave = math.sin((seed + i) / 4.0) * amp * 0.6
        drift = math.cos((seed + i) / 11.0) * amp * 0.4
        values.append(round(base + wave + drift, 4))
    return values


class SampleConnector(BaseConnector):
    kind = "sample"
    label = "内置示例数据"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        points = config.get("points", 30)
        if not isinstance(points, int) or not (2 <= points <= 365):
            errors.append("示例数据的点数需要在 2~365 之间")
        return errors

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        series = str(config.get("series") or "generic").strip() or "generic"
        points = int(config.get("points", 30))
        points = max(2, min(points, 365))
        _base, _amp, unit = _SERIES_PROFILE.get(series, _SERIES_PROFILE["generic"])
        values = _seeded_walk(series, points)
        start = ctx.now - timedelta(days=points - 1)
        rows = [
            {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "value": values[i]}
            for i in range(points)
        ]
        return {"series": series, "unit": unit, "rows": rows}


CONNECTOR = SampleConnector()
