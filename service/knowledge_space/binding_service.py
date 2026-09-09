"""Agent ↔ 知识库空间 绑定：带归属校验的编排。

阶段1：只允许把「自己的 Agent」绑定到「自己的空间」。
阶段3 接线到 agent create/update。
"""

from typing import List

from models import agent_knowledge_space_dao as dao
from service.exceptions import NotFound, PermissionDenied


def _validate(db, user_id: int, agent_id: int, space_ids: List[int]):
    from service.access_control import get_owned_agent, user_space_ids

    if get_owned_agent(db, user_id, agent_id) is None:
        raise NotFound("智能体不存在或无权限")
    allowed = user_space_ids(db, user_id)
    bad = [int(s) for s in space_ids if int(s) not in allowed]
    if bad:
        raise PermissionDenied(f"包含无权访问的知识库空间：{bad}")


def set_agent_spaces(db, user_id: int, agent_id: int, space_ids: List[int]) -> List[int]:
    """整体替换某 Agent 绑定的空间；返回最终 space_ids。"""
    space_ids = [int(s) for s in (space_ids or [])]
    _validate(db, user_id, agent_id, space_ids)
    dao.set_agent_spaces(db, agent_id, space_ids)
    return dao.list_space_ids_by_agent(db, agent_id)


def get_agent_space_ids(db, agent_id: int) -> List[int]:
    return dao.list_space_ids_by_agent(db, agent_id)
