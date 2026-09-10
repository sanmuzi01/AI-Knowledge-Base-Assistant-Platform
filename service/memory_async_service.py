"""长期记忆异步服务。

CRUD（list/add/edit/remove/clear）供管理端接口；
`load_memory_async` / `should_summarize_async` / `summarize_and_save_async` 是
`agent_runtime` async 迁移用的运行时侧接口，行为对齐 `service/memory/memory_service.py` 同步版。
"""

from typing import Dict, List, Optional

from models import memory_async_dao as dao
from models import agent_run_async_dao as run_dao
from service.memory.memory_service import (
    SHORT_TERM_ROUNDS,
    _build_summary_prompt,
    _format_runs_for_summary,
    _normalize_memory_type,
    memory_to_dict,
    render_memory_text,
    summary_due,
)
from utils.logger_handler import get_logger

logger = get_logger("memory_async_service")


async def list_agent_memories(db, user_id: int, agent_id: int) -> Optional[List[Dict]]:
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        return None
    memories = await dao.list_memories_by_agent_async(db, user_id, agent_id)
    return [memory_to_dict(memory) for memory in memories]


async def add_memory(db, user_id: int, agent_id: int, memory_type: str, content: str) -> Optional[Dict]:
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        return None
    normalized_type = _normalize_memory_type(memory_type)
    memory = await dao.create_memory_async(
        db=db,
        user_id=user_id,
        agent_id=agent_id,
        memory_type=normalized_type,
        content=content.strip(),
        chat_count=0,
    )
    await db.commit()
    return memory_to_dict(memory)


async def edit_memory(db, user_id: int, memory_id: int,
                      memory_type: str = None, content: str = None) -> Optional[Dict]:
    memory = await dao.get_owned_memory_async(db, user_id, memory_id)
    if not memory or not await dao.agent_belongs_to_user_async(db, user_id, memory.agent_id):
        return None
    normalized_type = _normalize_memory_type(memory_type) if memory_type is not None else None
    next_content = content.strip() if content is not None else None
    updated = await dao.update_memory_async(
        db,
        memory,
        memory_type=normalized_type,
        content=next_content,
    )
    await db.commit()
    return memory_to_dict(updated)


async def remove_memory(db, user_id: int, memory_id: int) -> bool:
    memory = await dao.get_owned_memory_async(db, user_id, memory_id)
    if not memory or not await dao.agent_belongs_to_user_async(db, user_id, memory.agent_id):
        return False
    await dao.delete_memory_async(db, memory)
    await db.commit()
    return True


async def clear_agent_memories(db, user_id: int, agent_id: int) -> Optional[int]:
    if not await dao.agent_belongs_to_user_async(db, user_id, agent_id):
        return None
    count = await dao.delete_memories_by_user_agent_async(db, user_id, agent_id)
    await db.commit()
    return count


# ========== 运行时侧（agent_runtime async 迁移用）==========

async def load_memory_async(db, user_id: int, agent_id: int) -> str:
    """加载长期记忆拼成文本。对齐同步 memory_service.load_memory。"""
    memories = await dao.list_memories_by_agent_async(db, user_id, agent_id)
    return render_memory_text(memories)


async def should_summarize_async(db, user_id: int, agent_id: int) -> bool:
    """是否该触发记忆总结。对齐同步 memory_service.should_summarize。"""
    total_count = await run_dao.count_finished_runs_by_agent_async(db, user_id, agent_id)
    summary = await dao.get_latest_summary_async(db, user_id, agent_id)
    last_summary_count = summary.chat_count if summary else 0
    return summary_due(total_count, last_summary_count)


async def summarize_and_save_async(
        db, user_id: int, agent_id: int, llm_model_name: str = "glm-4",
) -> Optional[str]:
    """总结旧对话 → 覆盖旧摘要存 DB。对齐同步 memory_service.summarize_and_save，
    但 LLM 调用走 `async_chat`，不在函数内 commit（由调用方统一提交事务）。"""
    from service.llm.llm_service import async_chat as llm_async_chat

    runs = await run_dao.list_finished_runs_by_agent_async(db, user_id, agent_id, limit=1000)
    if len(runs) <= SHORT_TERM_ROUNDS:
        logger.info(f"对话只有{len(runs)}轮，少于短期记忆{SHORT_TERM_ROUNDS}轮，不总结")
        return None

    old_runs = runs[SHORT_TERM_ROUNDS:]
    old_summary_obj = await dao.get_latest_summary_async(db, user_id, agent_id)
    old_summary_text = old_summary_obj.content if old_summary_obj else ""

    chat_text = _format_runs_for_summary(old_runs)
    summarize_prompt = _build_summary_prompt(old_summary=old_summary_text, new_chats_text=chat_text)

    try:
        new_summary = await llm_async_chat(
            db=db, user_id=user_id, model_name=llm_model_name,
            system_prompt=(
                "你是一个专业的对话记忆总结助手。"
                "你的任务是：从对话中提取关键信息并压缩成简洁的摘要，"
                "不要遗漏用户的关键事实（如姓名、职业、偏好、项目背景等）。"
                "直接输出摘要，不要用任何解释性语言。"
            ),
            history=[], user_message=summarize_prompt, temperature=0.1,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"记忆总结失败: {e}，将在下次对话时重试")
        return None

    if not new_summary or not new_summary.strip():
        logger.warning("记忆总结返回空内容，跳过保存")
        return None

    if old_summary_obj:
        await dao.delete_memory_async(db, old_summary_obj)
        logger.info(f"删除旧摘要: id={old_summary_obj.id}")

    total_chats = len(runs)
    await dao.create_memory_async(
        db, user_id=user_id, agent_id=agent_id, memory_type="summary",
        content=new_summary.strip(), chat_count=total_chats,
    )
    logger.info(
        f"记忆总结完成: {len(old_runs)}轮旧对话 → "
        f"{len(new_summary.strip())}字摘要, 当前总对话{total_chats}轮"
    )

    try:
        from service.user_profile_async_service import infer_user_profile_from_summary_async

        inferred = await infer_user_profile_from_summary_async(
            db=db, user_id=user_id, agent_id=agent_id,
            memory_summary=new_summary, llm_model_name=llm_model_name,
        )
        if inferred:
            logger.info(f"用户画像自动提炼完成: {len(inferred)}字")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"用户画像自动提炼失败（不影响记忆总结）: {e}")
    return new_summary
