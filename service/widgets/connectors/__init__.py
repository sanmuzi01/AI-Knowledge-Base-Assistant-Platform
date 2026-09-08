"""数据源连接器注册表。

runner 只通过 CONNECTORS.get(kind) 拿连接器，从不认识具体是哪个数据源。
新增数据源：写一个 BaseConnector 子类 -> 在这里 CONNECTORS.add(kind, instance) -> 完成。
"""

from service.widgets.connectors.base import BaseConnector
from service.widgets.registry import Registry

CONNECTORS: Registry[BaseConnector] = Registry("数据源")

# 注册 P1 连接器（导入即注册）
from service.widgets.connectors import agent_runs, catalog, sample, system_stats  # noqa: E402

CONNECTORS.add(sample.CONNECTOR.kind, sample.CONNECTOR)
CONNECTORS.add(catalog.CONNECTOR.kind, catalog.CONNECTOR)
CONNECTORS.add(system_stats.CONNECTOR.kind, system_stats.CONNECTOR)
CONNECTORS.add(agent_runs.CONNECTOR.kind, agent_runs.CONNECTOR)


def get_connector(kind: str) -> BaseConnector:
    return CONNECTORS.get(kind)
