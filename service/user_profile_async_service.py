"""用户画像异步服务。

`get_user_profile_payload` / `save_user_profile` 供画像管理接口；
`format_user_profile_for_prompt_async` / `infer_user_profile_from_summary_async` 是
`agent_runtime` / 记忆总结 async 迁移用的运行时侧接口，行为对齐
`service/user_profile_service.py` 同步版。
"""

from utils.timeutil import utcnow
from typing import Any, Dict, Optional

from models.user_profile_async_dao import get_user_profile_async, upsert_user_profile_async
from service.user_profile_service import (
    TEXT_LIMITS,
    _clean_text,
    normalize_profile_payload,
    profile_to_dict,
    render_profile_prompt,
)
from utils.logger_handler import get_logger

logger = get_logger("user_profile_async_service")


async def get_user_profile_payload(db, user_id: int) -> Dict[str, Any]:
    profile = await get_user_profile_async(db, user_id)
    return profile_to_dict(profile)


async def save_user_profile(db, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = normalize_profile_payload(payload)
    profile = await upsert_user_profile_async(db, user_id, cleaned)
    await db.commit()
    await db.refresh(profile)
    return profile_to_dict(profile)


async def format_user_profile_for_prompt_async(db, user_id: int) -> str:
    """将画像转成可注入 system prompt 的短文本。对齐同步 format_user_profile_for_prompt。"""
    profile = await get_user_profile_async(db, user_id)
    return render_profile_prompt(profile_to_dict(profile))


async def infer_user_profile_from_summary_async(
        db,
        user_id: int,
        agent_id: int,
        memory_summary: str,
        llm_model_name: str,
) -> Optional[str]:
    """从长期记忆摘要提炼用户画像，只更新自动画像字段，不覆盖手动配置。
    对齐同步 infer_user_profile_from_summary；LLM 调用走 async_chat，不在此 commit。"""
    summary = _clean_text(memory_summary, 2500)
    if not summary:
        return None

    from service.llm.llm_service import async_chat as llm_async_chat

    prompt = (
        "请从下面的长期记忆摘要中提炼用户画像，用于私人 AI 助手长期个性化回答。\n"
        "要求：\n"
        "1. 只保留稳定信息，例如用户身份、项目背景、技能水平、偏好、常见目标、表达习惯。\n"
        "2. 不要加入一次性任务、临时问题、无依据推测。\n"
        "3. 不要输出隐私敏感扩展推断，不要编造。\n"
        "4. 控制在 220 字以内，直接输出一段中文画像摘要。\n\n"
        f"【长期记忆摘要】\n{summary}"
    )
    try:
        inferred = await llm_async_chat(
            db=db,
            user_id=user_id,
            model_name=llm_model_name,
            system_prompt="你是用户画像提炼助手，负责把对话记忆压缩为稳定、谨慎、可执行的用户画像。",
            history=[],
            user_message=prompt,
            temperature=0.1,
        )
    except Exception:  # noqa: BLE001
        return None

    inferred = _clean_text(inferred, TEXT_LIMITS["auto_summary"])
    if not inferred:
        return None

    profile = await get_user_profile_async(db, user_id)
    payload = {
        "auto_summary": inferred,
        "last_inferred_at": utcnow(),
    }
    if not profile:
        payload.update({
            "communication_style": "balanced",
            "persona": "professional",
        })
    await upsert_user_profile_async(db, user_id, payload)
    return inferred
