"""
Skill 业务层
  1. Skill的CRUD（调DAO）
  2. Skill和Agent的绑定/解绑
  3. 加载Agent绑定的所有Skill配置并合并（ToolExecutor运行时用）
【核心方法】get_agent_skills_merged_config(agent_id)
  ToolExecutor运行时调用，拿到该Agent绑定的所有Skill的合并配置：
    - tool_names: 所有Skill工具的并集（只加载这些工具，不是全部）
    - tool_defaults_map: 所有Skill默认值的合并
    - system_prompt: 所有Skill prompt的拼接（在Agent prompt基础上补充）

实现已拆分到 service/skills_core/ 下的子模块（common / validation / crud /
import_export / templates / binding），本文件只做统一的对外导出，
现有 `from service.skill_service import xxx` 的调用方式不需要改动。
"""
from service.skills_core.common import (
    _can_use_template,
    _is_user_template,
    _list_package_resources,
    _normalize_permission_payload,
    _safe_skill_stem,
    _skill_to_dict,
)
from service.skills_core.validation import (
    _validate_tool_names,
    list_available_tools,
    validate_skill,
    validate_skill_config_file,
)
from service.skills_core.crud import (
    _write_skill_config,
    create_skill,
    delete_skill,
    get_skill,
    get_skill_config,
    list_all_skills,
    list_public_skills,
    list_user_skills,
    update_skill,
    update_skill_config,
    update_skill_with_config,
)
from service.skills_core.import_export import (
    export_skill_package,
    import_skill_from_upload,
    install_public_skill,
)
from service.skills_core.templates import (
    _write_template_file,
    create_template,
    delete_template,
    get_template_config,
    list_templates,
    update_template,
)
from service.skills_core.binding import (
    bind_skill,
    get_agent_skills_merged_config,
    list_agent_skills,
    unbind_skill,
    update_agent_skills,
)

__all__ = [
    "_can_use_template",
    "_is_user_template",
    "_list_package_resources",
    "_normalize_permission_payload",
    "_safe_skill_stem",
    "_skill_to_dict",
    "_validate_tool_names",
    "list_available_tools",
    "validate_skill",
    "validate_skill_config_file",
    "_write_skill_config",
    "create_skill",
    "delete_skill",
    "get_skill",
    "get_skill_config",
    "list_all_skills",
    "list_public_skills",
    "list_user_skills",
    "update_skill",
    "update_skill_config",
    "update_skill_with_config",
    "export_skill_package",
    "import_skill_from_upload",
    "install_public_skill",
    "_write_template_file",
    "create_template",
    "delete_template",
    "get_template_config",
    "list_templates",
    "update_template",
    "bind_skill",
    "get_agent_skills_merged_config",
    "list_agent_skills",
    "unbind_skill",
    "update_agent_skills",
]
