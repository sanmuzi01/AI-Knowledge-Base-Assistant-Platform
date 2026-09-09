"""数据源连接器注册表。

runner 只通过 CONNECTORS.get(kind) 拿连接器，从不认识具体是哪个数据源。
新增数据源：写一个 BaseConnector 子类 -> 在这里 CONNECTORS.add(kind, instance) -> 完成。
"""

from service.widgets.connectors.base import BaseConnector
from service.widgets.registry import Registry

CONNECTORS: Registry[BaseConnector] = Registry("数据源")

# 注册连接器（导入即注册）
from service.widgets.connectors import (  # noqa: E402
    agent_runs,
    catalog,
    http_api,
    knowledge_base,
    sample,
    system_stats,
    web_page,
)

CONNECTORS.add(sample.CONNECTOR.kind, sample.CONNECTOR)
CONNECTORS.add(catalog.CONNECTOR.kind, catalog.CONNECTOR)
CONNECTORS.add(system_stats.CONNECTOR.kind, system_stats.CONNECTOR)
CONNECTORS.add(agent_runs.CONNECTOR.kind, agent_runs.CONNECTOR)
# P2：外部数据源
CONNECTORS.add(http_api.CONNECTOR.kind, http_api.CONNECTOR)
CONNECTORS.add(web_page.CONNECTOR.kind, web_page.CONNECTOR)
CONNECTORS.add(knowledge_base.CONNECTOR.kind, knowledge_base.CONNECTOR)


def get_connector(kind: str) -> BaseConnector:
    return CONNECTORS.get(kind)
