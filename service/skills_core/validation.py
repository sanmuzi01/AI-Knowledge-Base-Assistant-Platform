"""Skill 配置文件 / 工具名校验。"""
from typing import Any, Dict, List, Optional

from service.skills.loader import SkillValidationError, _get_yml_path, load_skill_config
from utils.logger_handler import get_logger

logger = get_logger("skill_service")

# 由系统在绑定时自动添加的工具，不让用户手动勾选（比如 run_skill_script 只对带脚本的 Skill 有意义）
INTERNAL_TOOLS = {"run_skill_script"}


def list_available_tools() -> List[Dict[str, Any]]:
    import service.tools  # noqa: F401 - trigger tool auto registration
    from service.tools.base import ToolRegistry

    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "requires_context": tool.requires_context,
            "required_permissions": tool.required_permissions,
        }
        for tool in ToolRegistry.get_all_tools()
        if tool.name not in INTERNAL_TOOLS
    ]


def _validate_tool_names(tool_names: List[str]) -> Optional[List[str]]:
    selected_tool_names = [t.strip() for t in tool_names if isinstance(t, str) and t.strip()]
    available_tool_names = {tool["name"] for tool in list_available_tools()}
    if not selected_tool_names or any(tool_name not in available_tool_names for tool_name in selected_tool_names):
        return None
    return selected_tool_names


def validate_skill_config_file(config_file: str) -> Dict[str, Any]:
    """检查一个运行时 Skill YML 是否能被平台安全载入。"""
    import os
    import yaml
    import service.tools  # noqa: F401
    from service.tools.base import ToolRegistry

    result = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "tool_names": [],
        "missing_tool_names": [],
        "system_prompt_ready": False,
        "permissions": {"network": False, "file_read": [], "exec": False},
        "resources": [],
        "resource_count": 0,
        "allowed_resource_count": 0,
    }
    try:
        file_path = _get_yml_path(config_file)
        if not os.path.exists(file_path):
            raise SkillValidationError(f"Skill配置文件不存在: {config_file}")
        with open(file_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except Exception as e:
        result["ok"] = False
        result["errors"].append(str(e))
        return result

    if not isinstance(raw, dict):
        result["ok"] = False
        result["errors"].append("Skill配置根节点必须是对象")
        return result

    if not raw.get("name"):
        result["ok"] = False
        result["errors"].append("缺少 name 字段")

    tools_raw = raw.get("tools")
    if tools_raw is None:
        result["ok"] = False
        result["errors"].append("缺少 tools 字段")
        tools_raw = []
    if not isinstance(tools_raw, list):
        result["ok"] = False
        result["errors"].append("tools 字段必须是列表")
        tools_raw = []

    available = set(ToolRegistry.list_all())
    for item in tools_raw:
        if isinstance(item, str):
            tool_name = item.strip()
        elif isinstance(item, dict):
            tool_name = str(item.get("name") or "").strip()
        else:
            result["ok"] = False
            result["errors"].append(f"tools 项格式错误: {item}")
            continue
        if not tool_name:
            result["ok"] = False
            result["errors"].append("tools 中存在空工具名")
            continue
        if tool_name not in available:
            result["ok"] = False
            result["missing_tool_names"].append(tool_name)
            result["errors"].append(f"工具不存在: {tool_name}")
            continue
        result["tool_names"].append(tool_name)

    result["system_prompt_ready"] = bool(str(raw.get("system_prompt") or "").strip())
    # 没有工具不是问题：纯说明型能力（写作规范、审阅流程等）本来就只靠提示词，页面上显示为"提示词能力"
    if not result["system_prompt_ready"]:
        result["warnings"].append("system_prompt 为空，Skill 对回答行为的影响会很弱")

    try:
        cfg = load_skill_config(config_file)
        result["permissions"] = cfg.get("permissions", result["permissions"])
        result["resources"] = cfg.get("resources", [])
        result["resource_count"] = len(result["resources"])
        result["allowed_resource_count"] = len([item for item in result["resources"] if item.get("allowed")])
        script_count = len(cfg.get("scripts") or [])
        result["script_count"] = script_count
        if script_count:
            from service import sandbox

            if not sandbox.is_enabled():
                result["warnings"].append(f"带 {script_count} 个 Python 脚本，但脚本沙箱未开启，暂时只按文字说明工作")
    except Exception as e:
        result["ok"] = False
        result["errors"].append(str(e))
    return result


def validate_skill(db, skill_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    from service.access_control import can_read_skill
    from models.skill_dao import get_skill_by_id as dao_get

    skill = dao_get(db, skill_id)
    if not can_read_skill(skill, user_id):
        return None
    result = validate_skill_config_file(skill.config_file)
    result.update({
        "skill_id": skill.id,
        "name": skill.name,
        "config_file": skill.config_file,
        "is_public": skill.is_public,
    })
    return result
