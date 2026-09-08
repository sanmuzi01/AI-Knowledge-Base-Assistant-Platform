"""Agent 异步服务。

这里只放已经迁移到 AsyncSession 的读接口，避免和现有同步写逻辑混在一起。
"""

from typing import Any, Dict, List, Optional

from prompt.prompt_manager import read_prompt_file
from models.agent_async_dao import (
    get_agent_by_id_async,
    get_selected_agent_by_user_async,
    list_agents_by_user_async,
    skill_to_dict,
)


def _agent_payload(agent, selected_agent_id: Optional[int]) -> Dict[str, Any]:
    """统一组装助手返回结构。"""

    return {
        "id": agent.id,
        "name": agent.name,
        "prompt": read_prompt_file(agent.id),
        "model_name": agent.model_name,
        "rag_enabled": agent.rag_enabled,
        "memory_enabled": agent.memory_enabled,
        "temperature": agent.temperature,
        "skills": [skill_to_dict(skill) for skill in (agent.skills or [])],
        "is_selected": agent.id == selected_agent_id,
    }


async def list_agent(db, user) -> List[Dict[str, Any]]:
    """异步查询助手列表。"""

    agents = await list_agents_by_user_async(db, user.id)
    return [_agent_payload(agent, user.selected_agent_id) for agent in agents]


async def get_agent(db, user, agent_id: int) -> Optional[Dict[str, Any]]:
    """异步查询单个助手，自动校验归属。"""

    agent = await get_agent_by_id_async(db, agent_id)
    if not agent or agent.user_id != user.id:
        return None
    return _agent_payload(agent, user.selected_agent_id)


async def get_selected(db, user) -> Optional[Dict[str, Any]]:
    """异步查询当前选中的助手。"""

    agent = await get_selected_agent_by_user_async(db, user)
    if not agent:
        return None
    return _agent_payload(agent, user.selected_agent_id)
