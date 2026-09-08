"""Skill 模板的增删改查。"""
from typing import Any, Dict, List, Optional

from service.skills.loader import get_template_path, invalidate_skill_config, list_available_templates, load_skill_config
from utils.logger_handler import get_logger

from .common import _can_use_template, _safe_skill_stem
from .validation import _validate_tool_names

logger = get_logger("skill_service")


def list_templates(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    templates = []
    for filename in list_available_templates():
        if user_id is not None and not _can_use_template(user_id, filename):
            continue
        try:
            cfg = load_skill_config(filename)
            templates.append({
                "filename": filename,
                "name": cfg.get("name", filename),
                "description": cfg.get("description", ""),
                "tool_names": cfg.get("tool_names", []),
                "system_prompt": cfg.get("system_prompt", ""),
            })
        except Exception as e:
            logger.warning(f"模板加载失败: {filename}, error={e}")
            templates.append({
                "filename": filename,
                "name": filename,
                "description": "模板配置不可用",
                "tool_names": [],
                "system_prompt": "",
            })
    return templates


def get_template_config(template_filename: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if template_filename not in list_available_templates():
        return None
    if user_id is not None and not _can_use_template(user_id, template_filename):
        return None
    cfg = load_skill_config(template_filename)
    return {
        "filename": template_filename,
        "name": cfg.get("name", template_filename),
        "description": cfg.get("description", ""),
        "version": cfg.get("version", "1.0"),
        "tools": cfg.get("tools", []),
        "tool_names": cfg.get("tool_names", []),
        "system_prompt": cfg.get("system_prompt", ""),
        "editable": template_filename.startswith("user_templates/"),
    }


def _write_template_file(config_file: str, name: str, description: str,
                         system_prompt: str, tool_names: List[str],
                         version: str = "1.0") -> Optional[Dict[str, Any]]:
    import os
    import yaml
    from service.skills.loader import SKILLS_ROOT

    selected_tool_names = _validate_tool_names(tool_names)
    if selected_tool_names is None:
        logger.warning(f"保存模板失败：工具不存在或未选择工具 {tool_names}")
        return None
    if not system_prompt.strip():
        logger.warning("保存模板失败：Skill指令不能为空")
        return None

    config_path = os.path.join(SKILLS_ROOT, config_file)
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        runtime_config = {
            "name": name,
            "description": description,
            "version": version or "1.0",
            "tools": [{"name": tool_name, "defaults": {}} for tool_name in selected_tool_names],
            "permissions": {"network": False, "file_read": [], "exec": False},
            "resources": [],
            "system_prompt": system_prompt.strip(),
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(runtime_config, f, allow_unicode=True, sort_keys=False)
        invalidate_skill_config(config_file)
        return get_template_config(config_file)
    except Exception as e:
        logger.error(f"保存模板文件失败: config_file={config_file}, error={e}")
        return None


def create_template(user_id: int, name: str, description: str,
                    system_prompt: str, tool_names: List[str]) -> Optional[Dict[str, Any]]:
    import uuid

    config_file = f"user_templates/u{user_id}_{uuid.uuid4().hex[:10]}_{_safe_skill_stem(name)}.yml"
    return _write_template_file(
        config_file=config_file,
        name=name,
        description=description,
        system_prompt=system_prompt,
        tool_names=tool_names,
    )


def update_template(user_id: int, template_filename: str, name: str, description: str,
                    system_prompt: str, tool_names: List[str]) -> Optional[Dict[str, Any]]:
    expected_prefix = f"user_templates/u{user_id}_"
    if not template_filename.startswith(expected_prefix):
        logger.warning(f"拒绝修改非本人模板: user={user_id}, template={template_filename}")
        return None
    existing = get_template_config(template_filename)
    if not existing:
        return None
    return _write_template_file(
        config_file=template_filename,
        name=name,
        description=description,
        system_prompt=system_prompt,
        tool_names=tool_names,
        version=existing.get("version", "1.0"),
    )


def delete_template(user_id: int, template_filename: str) -> bool:
    import os
    from service.skills.loader import SKILLS_ROOT

    expected_prefix = f"user_templates/u{user_id}_"
    if not template_filename.startswith(expected_prefix):
        logger.warning(f"拒绝删除非本人模板: user={user_id}, template={template_filename}")
        return False
    if template_filename not in list_available_templates():
        return False
    path = os.path.abspath(os.path.join(SKILLS_ROOT, template_filename))
    root = os.path.abspath(os.path.join(SKILLS_ROOT, "user_templates"))
    if not path.startswith(root + os.sep):
        return False
    try:
        os.remove(path)
        invalidate_skill_config(template_filename)
        return True
    except OSError as e:
        logger.error(f"删除模板失败: template={template_filename}, error={e}")
        return False
