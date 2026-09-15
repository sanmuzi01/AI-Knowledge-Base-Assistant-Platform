"""Agent 企业接口连接器 DAO。"""
from typing import List, Optional

from models.init_db import AgentApiConnector


def create_connector(db, **fields) -> AgentApiConnector:
    row = AgentApiConnector(**fields)
    db.add(row)
    db.flush()
    return row


def get_owned_connector(db, user_id: int, connector_id: int) -> Optional[AgentApiConnector]:
    return (
        db.query(AgentApiConnector)
        .filter(AgentApiConnector.id == connector_id, AgentApiConnector.user_id == user_id)
        .first()
    )


def list_connectors_by_agent(db, agent_id: int, *, enabled_only: bool = False) -> List[AgentApiConnector]:
    q = db.query(AgentApiConnector).filter(AgentApiConnector.agent_id == agent_id)
    if enabled_only:
        q = q.filter(AgentApiConnector.is_enabled == 1)
    return q.order_by(AgentApiConnector.created_at.asc()).all()


def delete_connector(db, row: AgentApiConnector) -> None:
    db.delete(row)
    db.flush()
