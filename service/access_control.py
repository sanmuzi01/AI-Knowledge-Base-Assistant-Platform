"""Shared resource access checks.

Keep these helpers framework-agnostic so both API routes and services can reuse
the same ownership rules without importing FastAPI.
"""
from typing import Optional

from models.agent_dao import get_agent_by_id
from models.agent_run_dao import get_run_by_id
from models.background_task_dao import get_task_by_id
from models.conversation_dao import get_conversation_by_id
from models.knowledge_dao import get_knowledge_by_id
from models.memory_dao import get_memory_by_id
from models.skill_dao import get_skill_by_id
from models.init_db import Agent, AgentRun, BackgroundTask, Conversation, Knowledge, Memory, Skill


def get_owned_agent(db, user_id: int, agent_id: int) -> Optional[Agent]:
    agent = get_agent_by_id(db, agent_id)
    if not agent or agent.user_id != user_id:
        return None
    return agent


def get_owned_conversation(db, user_id: int, conversation_id: int, agent_id: int = None) -> Optional[Conversation]:
    conversation = get_conversation_by_id(db, conversation_id)
    if not conversation or conversation.user_id != user_id:
        return None
    if agent_id is not None and conversation.agent_id != agent_id:
        return None
    return conversation


def get_owned_knowledge(db, user_id: int, knowledge_id: int, agent_id: int = None) -> Optional[Knowledge]:
    knowledge = get_knowledge_by_id(db, knowledge_id)
    if not knowledge or knowledge.user_id != user_id:
        return None
    if agent_id is not None and knowledge.agent_id != agent_id:
        return None
    return knowledge


def get_owned_run(db, user_id: int, run_id: int, agent_id: int = None) -> Optional[AgentRun]:
    run = get_run_by_id(db, run_id)
    if not run or run.user_id != user_id:
        return None
    if agent_id is not None and run.agent_id != agent_id:
        return None
    return run


def get_owned_task(db, user_id: int, task_id: int, agent_id: int = None) -> Optional[BackgroundTask]:
    task = get_task_by_id(db, task_id)
    if not task or task.user_id != user_id:
        return None
    if agent_id is not None and task.agent_id != agent_id:
        return None
    return task


def can_read_skill(skill: Skill, user_id: int) -> bool:
    return bool(skill and (skill.user_id == user_id or skill.is_public == 1))


def can_write_skill(skill: Skill, user_id: int) -> bool:
    return bool(skill and skill.user_id == user_id)


def get_readable_skill(db, user_id: int, skill_id: int) -> Optional[Skill]:
    skill = get_skill_by_id(db, skill_id)
    return skill if can_read_skill(skill, user_id) else None


def get_writable_skill(db, user_id: int, skill_id: int) -> Optional[Skill]:
    skill = get_skill_by_id(db, skill_id)
    return skill if can_write_skill(skill, user_id) else None


def get_owned_memory(db, user_id: int, memory_id: int, agent_id: int = None) -> Optional[Memory]:
    memory = get_memory_by_id(db, memory_id)
    if not memory or memory.user_id != user_id:
        return None
    if agent_id is not None and memory.agent_id != agent_id:
        return None
    return memory
