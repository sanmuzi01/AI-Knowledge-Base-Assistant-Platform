"""平台内置数据源目录（catalog）。

用户不填 URL、不碰鉴权，只选一个 provider（gold_price / usd_cny / weather ...）。
provider 自己是一个小注册表：新增数据源 = 新增一个 provider 文件/函数并注册，
catalog 连接器和 runner 主流程都不用改。

P1：provider 返回服务端生成的、结构真实的数据（不发起外部请求）。
P2：真实外部数据（固定服务端 URL / 第三方 API / 用户自带 Key）以同样的 provider
    接口接入，并统一走出站抓取的安全校验。
"""

from typing import Any, Callable, Dict, List

from service.widgets.connectors.base import BaseConnector
from service.widgets.connectors.sample import SampleConnector
from service.widgets.context import WidgetRunContext
from service.widgets.registry import Registry

# provider 接口：async (ctx, config) -> raw_data
CatalogProvider = Callable[[WidgetRunContext, Dict[str, Any]], Any]
CATALOG_PROVIDERS: Registry[CatalogProvider] = Registry("平台数据源")

_sample = SampleConnector()


async def _gold_price(ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
    points = int(config.get("points", 30))
    data = await _sample.fetch(ctx, {"series": "gold_price", "points": points})
    data["provider"] = "gold_price"
    data["title"] = "黄金价格走势"
    return data


async def _usd_cny(ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
    points = int(config.get("points", 30))
    data = await _sample.fetch(ctx, {"series": "usd_cny", "points": points})
    data["provider"] = "usd_cny"
    data["title"] = "美元兑人民币汇率"
    return data


async def _weather(ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
    city = str(config.get("city") or "北京")
    points = int(config.get("points", 7))
    data = await _sample.fetch(ctx, {"series": "temperature", "points": points})
    for row in data["rows"]:
        row["city"] = city
    data["provider"] = "weather"
    data["title"] = f"{city}气温趋势"
    data["city"] = city
    return data


CATALOG_PROVIDERS.add("gold_price", _gold_price)
CATALOG_PROVIDERS.add("usd_cny", _usd_cny)
CATALOG_PROVIDERS.add("weather", _weather)


class CatalogConnector(BaseConnector):
    kind = "catalog"
    label = "平台数据服务"

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        provider = (config or {}).get("provider")
        if not provider or not CATALOG_PROVIDERS.has(provider):
            return [f"暂不支持的数据服务：{provider or '(空)'}"]
        return []

    async def fetch(self, ctx: WidgetRunContext, config: Dict[str, Any]) -> Any:
        provider = str((config or {}).get("provider") or "").strip()
        fn = CATALOG_PROVIDERS.get(provider)
        return await fn(ctx, config or {})


CONNECTOR = CatalogConnector()
