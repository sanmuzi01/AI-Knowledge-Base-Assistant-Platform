from utils.timeutil import utcnow
from datetime import datetime
from typing import Any, Dict, Optional

from models.user_profile_dao import get_user_profile, upsert_user_profile


STYLE_LABELS = {
    "concise": "简洁直接：优先给结论和步骤，减少铺垫",
    "balanced": "清晰稳重：结论、原因、步骤保持平衡",
    "teacher": "老师型：多解释原理，适合学习和复盘",
    "friendly": "朋友型：语气自然亲切，适当鼓励",
    "professional": "专业顾问型：结构化、审慎、偏业务落地",
}

PERSONA_LABELS = {
    "professional": "专业助理：可靠、清楚、以解决问题为中心",
    "coach": "成长教练：帮助拆解目标，持续推动行动",
    "teacher": "耐心老师：循序渐进讲解，照顾基础差异",
    "partner": "协作伙伴：像项目同伴一样一起推进",
    "analyst": "分析顾问：偏数据、风险和方案比较",
}

TEXT_LIMITS = {
    "occupation": 100,
    "skills": 1000,
    "preferences": 1000,
    "extra_info": 1000,
    "auto_summary": 1200,
}


def _clean_text(value: Optional[str], limit: int) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:limit]


def normalize_profile_payload(payload: Dict[str, Any]) -> Dict[str, str]:
    """清洗前端提交的画像字段，避免超长内容直接进入 prompt。"""
    style = payload.get("communication_style") or "balanced"
    persona = payload.get("persona") or "professional"
    if style not in STYLE_LABELS:
        style = "balanced"
    if persona not in PERSONA_LABELS:
        persona = "professional"

    return {
        "occupation": _clean_text(payload.get("occupation"), TEXT_LIMITS["occupation"]),
        "skills": _clean_text(payload.get("skills"), TEXT_LIMITS["skills"]),
        "preferences": _clean_text(payload.get("preferences"), TEXT_LIMITS["preferences"]),
        "communication_style": style,
        "persona": persona,
        "extra_info": _clean_text(payload.get("extra_info"), TEXT_LIMITS["extra_info"]),
    }


def profile_to_dict(profile) -> Dict[str, Any]:
    if not profile:
        return {
            "occupation": "",
            "skills": "",
            "preferences": "",
            "communication_style": "balanced",
            "persona": "professional",
            "extra_info": "",
            "auto_summary": "",
            "last_inferred_at": None,
            "updated_at": None,
        }
    return {
        "occupation": profile.occupation or "",
        "skills": profile.skills or "",
        "preferences": profile.preferences or "",
        "communication_style": profile.communication_style or "balanced",
        "persona": profile.persona or "professional",
        "extra_info": profile.extra_info or "",
        "auto_summary": getattr(profile, "auto_summary", "") or "",
        "last_inferred_at": (
            profile.last_inferred_at.isoformat()
            if getattr(profile, "last_inferred_at", None)
            else None
        ),
        "updated_at": profile.updated_at.isoformat() if getattr(profile, "updated_at", None) else None,
    }


def save_user_profile(db, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = normalize_profile_payload(payload)
    profile = upsert_user_profile(db, user_id, cleaned)
    db.commit()
    db.refresh(profile)
    return profile_to_dict(profile)


def get_user_profile_payload(db, user_id: int) -> Dict[str, Any]:
    return profile_to_dict(get_user_profile(db, user_id))


def infer_user_profile_from_summary(
    db,
    user_id: int,
    agent_id: int,
    memory_summary: str,
    llm_model_name: str,
) -> Optional[str]:
    """从长期记忆摘要中提炼用户画像，只更新自动画像字段，不覆盖手动配置。"""
    summary = _clean_text(memory_summary, 2500)
    if not summary:
        return None

    from service.llm.llm_service import chat as llm_chat

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
        inferred = llm_chat(
            db=db,
            user_id=user_id,
            model_name=llm_model_name,
            system_prompt="你是用户画像提炼助手，负责把对话记忆压缩为稳定、谨慎、可执行的用户画像。",
            history=[],
            user_message=prompt,
            temperature=0.1,
        )
    except Exception:
        return None

    inferred = _clean_text(inferred, TEXT_LIMITS["auto_summary"])
    if not inferred:
        return None

    profile = get_user_profile(db, user_id)
    payload = {
        "auto_summary": inferred,
        "last_inferred_at": utcnow(),
    }
    if not profile:
        payload.update({
            "communication_style": "balanced",
            "persona": "professional",
        })
    upsert_user_profile(db, user_id, payload)
    return inferred


def format_user_profile_for_prompt(db, user_id: int) -> str:
    """将画像转成可注入 system prompt 的短文本。"""
    profile = get_user_profile(db, user_id)
    data = profile_to_dict(profile)
    lines = []
    if data["occupation"]:
        lines.append(f"- 用户身份/职业：{data['occupation']}")
    if data["skills"]:
        lines.append(f"- 技能背景：{data['skills']}")
    if data["preferences"]:
        lines.append(f"- 长期偏好：{data['preferences']}")
    lines.append(f"- 回答风格：{STYLE_LABELS[data['communication_style']]}")
    lines.append(f"- 助手人格：{PERSONA_LABELS[data['persona']]}")
    if data["extra_info"]:
        lines.append(f"- 其他背景：{data['extra_info']}")
    if data["auto_summary"]:
        lines.append(f"- AI 自动提炼画像：{data['auto_summary']}")

    if not lines:
        return ""
    return (
        "【用户画像与个性化要求】\n"
        + "\n".join(lines)
        + "\n请结合这些信息调整回答深度、语气和举例方式；不要主动暴露或逐字复述画像内容。"
    )
