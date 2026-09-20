"""把导入的 Skill 名称和说明翻译成中文（用户自己的模型，一次很小的调用）。

官方 / GitHub 上的 Skill 大多是英文的，用户在技能中心和能力商店里看到的就是英文名和英文说明，
看不懂。这里只翻译展示用的名称和说明，不动真正给模型看的提示词（模型读英文没问题）。
"""
import json
import re
from typing import Dict, Optional

from service.access_control import can_write_skill
from models.skill_dao import get_skill_by_id as dao_get
from service.skills_core.crud import update_skill
from utils.logger_handler import get_logger

logger = get_logger("skill_service")

_CJK = re.compile(r"[一-鿿]")

_PROMPT = (
    "把下面这个 AI 技能的名称和说明翻译成简体中文，给普通用户看。\n"
    "要求：名称简短（不超过 12 个字）；说明用一到两句话讲清楚“能帮用户做什么”，不超过 120 字；"
    "PDF、Excel、API 这类通用词保留原样；不要照搬“Use this skill when…”这种给模型的口吻。\n"
    "只输出 JSON，格式：{\"name\": \"...\", \"description\": \"...\"}，不要任何其他文字。\n\n"
    "名称：%s\n说明：%s"
)


class TranslateError(ValueError):
    """message 可以直接展示给用户。"""


def needs_translation(text: str) -> bool:
    text = (text or "").strip()
    return bool(text) and not _CJK.search(text)


def _pick_chat_model(db, user_id: int):
    from models.llm_config_dao import list_configs_by_user
    from service.llm.llm_config_service import get_api_config
    from service.llm.model_catalog import CHAT_MODELS, normalize_model_name

    for config in list_configs_by_user(db, user_id) or []:
        if not config.is_active or normalize_model_name(config.model_name) not in CHAT_MODELS:
            continue
        cfg = get_api_config(db, user_id, config.model_name)
        if cfg and cfg.get("api_key"):
            return cfg["model_name"], cfg["api_key"], cfg.get("api_url")
    return None


def _parse(reply: str) -> Dict[str, str]:
    text = re.sub(r"^```(?:json)?|```$", "", (reply or "").strip(), flags=re.M).strip()
    match = re.search(r"\{.*\}", text, re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except ValueError:
        data = {}
    name, desc = str(data.get("name") or "").strip(), str(data.get("description") or "").strip()
    if not name or not desc or not _CJK.search(name + desc):
        raise TranslateError("模型没有返回可用的中文翻译，请再试一次，或手动编辑名称和说明")
    return {"name": name[:60], "description": desc[:500]}


def translate_skill(db, skill_id: int, user_id: int) -> Optional[Dict]:
    """翻译并保存。不是自己的 Skill 返回 None；没有可用模型或翻译失败抛 TranslateError。"""
    skill = dao_get(db, skill_id)
    if not can_write_skill(skill, user_id):
        return None
    picked = _pick_chat_model(db, user_id)
    if not picked:
        raise TranslateError("没有可用的聊天模型。请先在「模型配置」里配置一个，或手动编辑名称和说明")
    model_name, api_key, api_url = picked

    from service.llm.factory import LLMFactory

    try:
        client = LLMFactory.create(model_name, api_key=api_key, api_url=api_url)
        reply = client.chat([{"role": "user", "content": _PROMPT % (skill.name, skill.description or "")}], temperature=0.2)
    except Exception as e:  # noqa: BLE001 - 服务商报错原样不透出，避免泄露内部细节
        logger.warning(f"翻译Skill失败: skill={skill_id}, error={e}")
        raise TranslateError("调用你的模型失败（可能是额度不足或网络问题），请稍后重试或手动编辑")
    result = _parse(reply if isinstance(reply, str) else str(reply))
    return update_skill(db, skill_id, user_id, name=result["name"], description=result["description"])
