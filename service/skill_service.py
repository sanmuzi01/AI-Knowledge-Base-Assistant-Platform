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
"""
from typing import List, Optional,Dict,Any
from sqlalchemy.orm import Session
from service.access_control import can_read_skill, can_write_skill, get_owned_agent
from models.skill_dao import (
    create_skill as dao_create,
    get_skill_by_id as dao_get,
    list_skills_by_user as dao_list_user,
    list_public_skills as dao_list_public,
    list_all_skills as dao_list_all,
    update_skill as dao_update,
    delete_skill as dao_delete,
    bind_skill_to_agent as dao_bind,
    unbind_skill_from_agent as dao_unbind,
    list_skills_by_agent as dao_list_by_agent,
    unbind_all_skills_from_agent as dao_unbind_all,
)
from service.skills.loader import (
    SKILLS_ROOT,
    SkillValidationError,
    _get_yml_path,
    invalidate_skill_config,
    load_skill_config,
    list_available_templates,
    get_template_path,
)
from utils.logger_handler import get_logger
logger = get_logger("skill_service")

def _safe_skill_stem(name: str) -> str:
    import re

    return re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]+", "_", (name or "skill")).strip("_") or "skill"


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
    if not result["tool_names"]:
        result["warnings"].append("没有可用工具，绑定后只会追加提示词，不会获得工具调用能力")
    if not result["system_prompt_ready"]:
        result["warnings"].append("system_prompt 为空，Skill 对回答行为的影响会很弱")

    try:
        cfg = load_skill_config(config_file)
        result["permissions"] = cfg.get("permissions", result["permissions"])
        result["resources"] = cfg.get("resources", [])
        result["resource_count"] = len(result["resources"])
        result["allowed_resource_count"] = len([item for item in result["resources"] if item.get("allowed")])
    except Exception as e:
        result["ok"] = False
        result["errors"].append(str(e))
    return result


def _is_user_template(template_filename: str) -> bool:
    return template_filename.startswith("user_templates/")


def _can_use_template(user_id: int, template_filename: str) -> bool:
    return not _is_user_template(template_filename) or template_filename.startswith(f"user_templates/u{user_id}_")


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
    ]

def import_skill_from_upload(
        db: Session,
        user_id: int,
        filename: str,
        content: bytes,
        is_public: int = 0,
        commit: bool = True,
) -> Optional[Dict]:
    """导入用户上传的 Skill。

    支持两种格式：
    1. 单个 .yml/.yaml：直接安装到 skills/imported/
    2. .zip Skill Package：读取 manifest.yaml + SKILL.md，转换为运行时YML
    """
    import os
    import re
    import uuid
    import zipfile
    import shutil
    import yaml
    from io import BytesIO
    from service.skills.loader import SKILLS_ROOT, load_skill_config

    def safe_stem(name: str) -> str:
        raw = os.path.splitext(os.path.basename(name))[0] or "skill"
        return re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]+", "_", raw).strip("_") or "skill"

    def ensure_safe_zip_member(member: str) -> bool:
        normalized = member.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            return False
        blocked_exts = {
            ".py", ".pyc", ".pyd", ".exe", ".dll", ".bat", ".cmd", ".ps1",
            ".sh", ".msi", ".scr", ".com", ".jar",
        }
        return os.path.splitext(normalized.lower())[1] not in blocked_exts

    imported_dir = os.path.join(SKILLS_ROOT, "imported")
    os.makedirs(imported_dir, exist_ok=True)
    stem = safe_stem(filename)
    unique = f"u{user_id}_{uuid.uuid4().hex[:10]}_{stem}"
    ext = os.path.splitext(filename.lower())[1]

    try:
        if ext in {".yml", ".yaml"}:
            config_file = f"imported/{unique}.yml"
            yml_path = os.path.join(SKILLS_ROOT, config_file)
            with open(yml_path, "wb") as f:
                f.write(content)
            invalidate_skill_config(config_file)
            validation = validate_skill_config_file(config_file)
            if not validation["ok"]:
                os.remove(yml_path)
                logger.warning(f"导入Skill失败，配置校验未通过: {validation}")
                return None
            cfg = load_skill_config(config_file)
            skill = dao_create(
                db=db,
                user_id=user_id,
                name=cfg.get("name") or stem,
                description=cfg.get("description") or "",
                config_file=config_file,
                is_public=is_public,
            )
            if skill and commit:
                db.commit()
            return _skill_to_dict(skill) if skill else None

        if ext != ".zip":
            logger.warning(f"不支持的Skill导入格式: {filename}")
            return None

        package_root = os.path.join(
            os.path.dirname(SKILLS_ROOT),
            "skills_packages",
            "imported",
            unique,
        )
        os.makedirs(package_root, exist_ok=True)
        with zipfile.ZipFile(BytesIO(content)) as zf:
            unsafe = [n for n in zf.namelist() if not ensure_safe_zip_member(n)]
            if unsafe:
                logger.warning(f"Skill包包含不安全文件: {unsafe[:5]}")
                shutil.rmtree(package_root, ignore_errors=True)
                return None
            zf.extractall(package_root)

        manifest_path = os.path.join(package_root, "manifest.yaml")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(package_root, "manifest.yml")
        skill_md_path = os.path.join(package_root, "SKILL.md")
        if not os.path.exists(manifest_path) or not os.path.exists(skill_md_path):
            logger.warning(f"Skill包缺少 manifest.yaml 或 SKILL.md: {filename}")
            shutil.rmtree(package_root, ignore_errors=True)
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}
        with open(skill_md_path, "r", encoding="utf-8") as f:
            skill_prompt = f.read()

        if not isinstance(manifest, dict):
            shutil.rmtree(package_root, ignore_errors=True)
            return None

        tools = manifest.get("tools") or []
        if not isinstance(tools, list):
            shutil.rmtree(package_root, ignore_errors=True)
            return None

        normalized_tools = []
        for item in tools:
            if isinstance(item, str):
                normalized_tools.append({"name": item, "defaults": {}})
            elif isinstance(item, dict) and item.get("name"):
                normalized_tools.append({
                    "name": item.get("name"),
                    "defaults": item.get("defaults") or {},
                })

        constraints = manifest.get("constraints") or ""
        output_format = manifest.get("output_format") or ""
        prompt_parts = []
        if constraints:
            prompt_parts.append(f"【约束】\n{constraints}")
        if output_format:
            prompt_parts.append(f"【输出格式】\n{output_format}")
        prompt_parts.append(skill_prompt)

        runtime_config = {
            "name": manifest.get("display_name") or manifest.get("name") or stem,
            "description": manifest.get("description") or "",
            "version": str(manifest.get("version") or "1.0.0"),
            "tools": normalized_tools,
            "permissions": {
                "network": bool((manifest.get("permissions") or {}).get("network", False)),
                "file_read": (manifest.get("permissions") or {}).get("file_read") or [],
                "exec": False,
            },
            "resource_root": os.path.join(package_root, "resources"),
            "resources": manifest.get("resources") or [
                path
                for path in _list_package_resources(os.path.join(package_root, "resources"))
            ],
            "system_prompt": "\n\n".join(prompt_parts),
        }

        config_file = f"imported/{unique}.yml"
        yml_path = os.path.join(SKILLS_ROOT, config_file)
        with open(yml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(runtime_config, f, allow_unicode=True, sort_keys=False)
        invalidate_skill_config(config_file)

        validation = validate_skill_config_file(config_file)
        if not validation["ok"]:
            shutil.rmtree(package_root, ignore_errors=True)
            os.remove(yml_path)
            logger.warning(f"导入Skill包失败，配置校验未通过: {validation}")
            return None
        cfg = load_skill_config(config_file)
        skill = dao_create(
            db=db,
            user_id=user_id,
            name=cfg.get("name") or stem,
            description=cfg.get("description") or "",
            config_file=config_file,
            is_public=is_public,
        )
        if skill and commit:
            db.commit()
        return _skill_to_dict(skill) if skill else None
    except Exception as e:
        logger.error(f"导入Skill失败: filename={filename}, error={e}")
        return None


def install_public_skill(db: Session, user_id: int, skill_id: int, commit: bool = True) -> Optional[Dict]:
    """把公开 Skill 安装为当前用户自己的私有副本。"""
    import os
    import uuid
    import yaml

    source = dao_get(db, skill_id)
    if not source or not can_read_skill(source, user_id) or source.is_public != 1:
        return None
    if source.user_id == user_id:
        return _skill_to_dict(source)

    try:
        cfg = load_skill_config(source.config_file)
        config_file = f"installed/u{user_id}_{uuid.uuid4().hex[:10]}_{_safe_skill_stem(source.name)}.yml"
        config_path = os.path.join(SKILLS_ROOT, config_file)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        runtime_config = {
            "name": cfg.get("name") or source.name,
            "description": cfg.get("description") or source.description or "",
            "version": cfg.get("version", "1.0"),
            "tools": cfg.get("tools", []),
            "permissions": _normalize_permission_payload(cfg.get("permissions", {})),
            "resource_root": cfg.get("resource_root", ""),
            "resources": cfg.get("resources", []),
            "system_prompt": cfg.get("system_prompt", ""),
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(runtime_config, f, allow_unicode=True, sort_keys=False)
        invalidate_skill_config(config_file)
        validation = validate_skill_config_file(config_file)
        if not validation["ok"]:
            os.remove(config_path)
            logger.warning(f"安装公开Skill失败，配置校验未通过: {validation}")
            return None
        skill = dao_create(
            db=db,
            user_id=user_id,
            name=f"{source.name}",
            description=source.description or cfg.get("description", ""),
            config_file=config_file,
            is_public=0,
        )
        if skill and commit:
            db.commit()
        return _skill_to_dict(skill) if skill else None
    except Exception as e:
        logger.error(f"安装公开Skill失败: skill={skill_id}, user={user_id}, error={e}")
        return None


# Skill CRUD
def _list_package_resources(resources_root: str) -> List[str]:
    import os

    if not os.path.exists(resources_root):
        return []
    result = []
    for root, _, files in os.walk(resources_root):
        for filename in files:
            full_path = os.path.join(root, filename)
            result.append(os.path.relpath(full_path, resources_root).replace("\\", "/"))
    return sorted(result)


def _normalize_permission_payload(permissions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    permissions = permissions or {}
    return {
        "network": bool(permissions.get("network", False)),
        "file_read": [str(item).replace("\\", "/") for item in permissions.get("file_read", []) if str(item).strip()],
        "exec": False,
    }


def create_skill(db: Session, user_id: int, name: str, description: str,
                 template_filename: str = "", is_public: int = 0,
                 system_prompt: str = "", tool_names: Optional[List[str]] = None,
                 permissions: Optional[Dict[str, Any]] = None,
                 commit: bool = True) -> Optional[Dict]:
    # 新建 Skill 要生成用户自己的运行时 YML，否则只是数据库里的一条模板引用。
    import os
    import uuid
    import yaml
    from service.skills.loader import SKILLS_ROOT

    template_cfg = {
        "name": name,
        "description": "",
        "version": "1.0",
        "tool_names": [],
        "tool_defaults_map": {},
        "system_prompt": "",
        "permissions": {"network": False, "file_read": [], "exec": False},
        "resources": [],
        "resource_root": "",
    }
    if template_filename:
        available = list_available_templates()
        if template_filename not in available or not _can_use_template(user_id, template_filename):
            logger.warning(f"创建Skill失败：模板不存在 {template_filename}")
            return None
        try:
            template_cfg = load_skill_config(get_template_path(template_filename))
        except Exception as e:
            logger.warning(f"创建Skill失败：模板配置不可用 {template_filename}, error={e}")
            return None

    if not template_filename and not system_prompt.strip():
        logger.warning("创建Skill失败：空白创建时必须填写Skill指令")
        return None

    selected_tool_names = _validate_tool_names(tool_names if tool_names is not None else template_cfg.get("tool_names", []))
    if selected_tool_names is None:
        logger.warning(f"创建Skill失败：工具不存在或未选择工具 {tool_names}")
        return None
    template_defaults = template_cfg.get("tool_defaults_map", {})
    runtime_tools = [
        {"name": tool_name, "defaults": template_defaults.get(tool_name, {})}
        for tool_name in selected_tool_names
    ]

    prompt_parts = []
    if template_cfg.get("system_prompt"):
        prompt_parts.append(template_cfg["system_prompt"])
    if system_prompt and system_prompt.strip():
        prompt_parts.append(system_prompt.strip())

    config_file = f"user_created/u{user_id}_{uuid.uuid4().hex[:10]}_{_safe_skill_stem(name)}.yml"
    config_path = os.path.join(SKILLS_ROOT, config_file)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    runtime_config = {
        "name": name,
        "description": description or template_cfg.get("description", ""),
        "version": template_cfg.get("version", "1.0"),
        "tools": runtime_tools,
        "permissions": _normalize_permission_payload(permissions or template_cfg.get("permissions")),
        "resource_root": template_cfg.get("resource_root", ""),
        "resources": template_cfg.get("resources", []),
        "system_prompt": "\n\n".join(prompt_parts),
    }

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(runtime_config, f, allow_unicode=True, sort_keys=False)
        invalidate_skill_config(config_file)
        load_skill_config(config_file)
    except Exception as e:
        logger.error(f"创建Skill配置文件失败: {e}")
        return None

    skill = dao_create(db=db,user_id=user_id,name=name,
        description=description,config_file=config_file,
        is_public=is_public)
    if not skill:
        return None
    if commit:
        db.commit()
    return _skill_to_dict(skill)


def _write_skill_config(config_file: str, name: str, description: str,
                        system_prompt: str, tool_names: List[str],
                        permissions: Optional[Dict[str, Any]] = None) -> bool:
    import os
    import yaml
    from service.skills.loader import SKILLS_ROOT

    selected_tool_names = _validate_tool_names(tool_names)
    if selected_tool_names is None:
        logger.warning(f"保存Skill配置失败：工具不存在或未选择工具 {tool_names}")
        return False

    config_path = os.path.join(SKILLS_ROOT, config_file)
    try:
        old_cfg = load_skill_config(config_file)
        runtime_config = {
            "name": name,
            "description": description,
            "version": old_cfg.get("version", "1.0"),
            "tools": [{"name": tool_name, "defaults": old_cfg.get("tool_defaults_map", {}).get(tool_name, {})}
                      for tool_name in selected_tool_names],
            "permissions": _normalize_permission_payload(permissions or old_cfg.get("permissions")),
            "resource_root": old_cfg.get("resource_root", ""),
            "resources": old_cfg.get("resources", []),
            "system_prompt": system_prompt,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(runtime_config, f, allow_unicode=True, sort_keys=False)
        invalidate_skill_config(config_file)
        load_skill_config(config_file)
        return True
    except Exception as e:
        logger.error(f"保存Skill配置失败: config_file={config_file}, error={e}")
        return False


def update_skill_config(db: Session, skill_id: int, user_id: int, *,
                        system_prompt: Optional[str] = None,
                        tool_names: Optional[List[str]] = None,
                        permissions: Optional[Dict[str, Any]] = None) -> bool:
    skill = dao_get(db, skill_id)
    if not can_write_skill(skill, user_id):
        return False
    if not skill.config_file.startswith(("user_created/", "imported/")):
        logger.warning(f"拒绝修改内置模板Skill配置: skill_id={skill_id}, config={skill.config_file}")
        return False
    cfg = load_skill_config(skill.config_file)
    return _write_skill_config(
        config_file=skill.config_file,
        name=skill.name,
        description=skill.description or cfg.get("description", ""),
        system_prompt=cfg.get("system_prompt", "") if system_prompt is None else system_prompt,
        tool_names=cfg.get("tool_names", []) if tool_names is None else tool_names,
        permissions=cfg.get("permissions", {}) if permissions is None else permissions,
    )


def get_skill_config(db: Session, skill_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    skill = dao_get(db, skill_id)
    if not can_read_skill(skill, user_id):
        return None
    cfg = load_skill_config(skill.config_file)
    return {
        "name": cfg.get("name", skill.name),
        "description": cfg.get("description", skill.description or ""),
        "version": cfg.get("version", "1.0"),
        "tools": cfg.get("tools", []),
        "tool_names": cfg.get("tool_names", []),
        "system_prompt": cfg.get("system_prompt", ""),
        "permissions": cfg.get("permissions", {"network": False, "file_read": [], "exec": False}),
        "resources": cfg.get("resources", []),
    }


def validate_skill(db: Session, skill_id: int, user_id: int) -> Optional[Dict[str, Any]]:
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


def export_skill_package(db: Session, skill_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """把运行时 Skill 导出为标准 zip 包：manifest.yaml + SKILL.md。"""
    import os
    import tempfile
    import zipfile
    import yaml

    skill = dao_get(db, skill_id)
    if not can_read_skill(skill, user_id):
        return None
    validation = validate_skill_config_file(skill.config_file)
    if not validation["ok"]:
        raise ValueError("Skill不可导出，请先修复配置错误")
    cfg = load_skill_config(skill.config_file)
    package_name = f"{_safe_skill_stem(skill.name)}_{skill.id}.zip"
    export_path = os.path.join(tempfile.gettempdir(), package_name)
    manifest = {
        "name": _safe_skill_stem(skill.name),
        "display_name": skill.name,
        "description": skill.description or cfg.get("description", ""),
        "version": cfg.get("version", "1.0.0"),
        "source": "export",
        "source_ref": skill.config_file,
        "tools": [
            {
                "name": tool_name,
                "defaults": cfg.get("tool_defaults_map", {}).get(tool_name, {}),
            }
            for tool_name in cfg.get("tool_names", [])
        ],
        "permissions": {"network": False, "file_read": [], "exec": False},
        "resources": cfg.get("resources", []),
        "output_format": "markdown",
    }
    with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.yaml", yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
        zf.writestr("SKILL.md", cfg.get("system_prompt", ""))
        resource_root = cfg.get("resource_root", "")
        for resource in cfg.get("resources", []):
            rel_path = resource.get("path") if isinstance(resource, dict) else str(resource)
            if not rel_path or not resource_root:
                continue
            abs_path = os.path.abspath(os.path.join(resource_root, rel_path))
            root = os.path.abspath(resource_root)
            if os.path.isfile(abs_path) and abs_path.startswith(root + os.sep):
                zf.write(abs_path, f"resources/{rel_path}")
    return {"path": export_path, "filename": package_name}


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

def get_skill(db:Session,skill_id:int, user_id: int = None)->Optional[Dict]:
    skill = dao_get(db,skill_id)
    if skill and user_id is not None and not can_read_skill(skill, user_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试查看私有Skill {skill_id}")
        return None
    return _skill_to_dict(skill) if skill else None
def list_user_skills(db: Session, user_id: int) -> List[Dict]:
    skills = dao_list_user(db, user_id)
    return [_skill_to_dict(s) for s in skills]
def list_public_skills(db: Session) -> List[Dict]:
    skills = dao_list_public(db)
    return [_skill_to_dict(s) for s in skills]
def list_all_skills(db: Session) -> List[Dict]:
    skills = dao_list_all(db)
    return [_skill_to_dict(s) for s in skills]
def update_skill(db: Session, skill_id: int, user_id: int, commit: bool = True, **kwargs) -> Optional[Dict]:
    # 先查Skill是否存在
    skill = dao_get(db, skill_id)
    if not skill:
        logger.warning(f"更新Skill失败：不存在 id={skill_id}")
        return None
    # 权限校验：只有创建者能更新
    if not can_write_skill(skill, user_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试更新别人的Skill {skill_id}")
        return None
    # 如果更新了模板文件，校验是否存在
    if "template_filename" in kwargs:
        template = kwargs.pop("template_filename")
        if template:
            available = list_available_templates()
            if template not in available:
                logger.warning(f"更新Skill失败：模板不存在 {template}")
                return None
            kwargs["config_file"] = get_template_path(template)

    updated_skill = dao_update(db, skill_id, **kwargs)
    if updated_skill and commit:
        db.commit()
    return _skill_to_dict(updated_skill) if updated_skill else None


def update_skill_with_config(
        db: Session,
        skill_id: int,
        user_id: int,
        fields: Dict[str, Any],
        config_fields: Dict[str, Any],
) -> Optional[Dict]:
    """统一更新 Skill 基础信息和运行配置。

    路由层不再拆分事务；基础字段和 YML 运行配置都成功后，才提交数据库变更。
    """
    if not fields and not config_fields:
        return None
    if fields:
        skill = update_skill(db, skill_id, user_id=user_id, commit=False, **fields)
        if not skill:
            return None
    if config_fields:
        if not update_skill_config(db, skill_id, user_id=user_id, **config_fields):
            return None
    db.commit()
    skill = get_skill(db, skill_id, user_id=user_id)
    if skill:
        skill["config"] = get_skill_config(db, skill_id, user_id=user_id)
    return skill


def delete_skill(db: Session, skill_id: int, user_id: int) -> bool:
    """删除Skill（加权限校验：只有创建者能删除）"""
    skill = dao_get(db, skill_id)
    if not skill:
        return False
    if not can_write_skill(skill, user_id):
        logger.warning(f"权限拒绝：用户{user_id}尝试删除别人的Skill {skill_id}")
        return False
    config_file = skill.config_file
    success = dao_delete(db, skill_id)
    if success:
        invalidate_skill_config(config_file)
        db.commit()
    return success
def bind_skill(db: Session, agent_id: int, skill_id: int, user_id: int) -> bool:
    """绑定Skill到Agent（校验：Skill必须是当前用户创建的或公开的）"""
    agent = get_owned_agent(db, user_id, agent_id)
    if not agent:
        logger.warning(f"权限拒绝：用户{user_id}无权操作Agent {agent_id}")
        return False
    skill = dao_get(db, skill_id)
    if not skill:
        return False
    # 权限：自己创建的 或 公开的Skill 才能绑定
    if not can_read_skill(skill, user_id):
        logger.warning(f"权限拒绝：用户{user_id}无权绑定Skill {skill_id}")
        return False
    success = dao_bind(db, agent_id, skill_id)
    if success:
        db.commit()
    return success

def unbind_skill(db: Session, agent_id: int, skill_id: int, user_id: int) -> bool:
    """解绑Skill（校验：Agent必须是当前用户的）"""
    agent = get_owned_agent(db, user_id, agent_id)
    if not agent:
        return False
    success = dao_unbind(db, agent_id, skill_id)
    if success:
        db.commit()
    return success

def list_agent_skills(db: Session, agent_id: int, user_id: int = None) -> List[Dict]:
    if user_id is not None:
        agent = get_owned_agent(db, user_id, agent_id)
        if not agent:
            logger.warning(f"权限拒绝：用户{user_id}无权查看Agent {agent_id}的Skill")
            return []
    skills = dao_list_by_agent(db, agent_id)
    return [_skill_to_dict(s) for s in skills]

def update_agent_skills(db: Session, agent_id: int, skill_ids: List[int], user_id: int = None, commit: bool = True) -> bool:
    """批量更新Agent绑定的Skill（先全部解绑，再绑定新的）"""
    if user_id is not None:
        agent = get_owned_agent(db, user_id, agent_id)
        if not agent:
            logger.warning(f"权限拒绝：用户{user_id}无权操作Agent {agent_id}")
            return False
        for skill_id in skill_ids:
            skill = dao_get(db, skill_id)
            if not can_read_skill(skill, user_id):
                logger.warning(f"权限拒绝：用户{user_id}无权绑定Skill {skill_id}")
                return False
    dao_unbind_all(db, agent_id)
    for skill_id in skill_ids:
        dao_bind(db, agent_id, skill_id)
    logger.info(f"更新Agent绑定Skill: agent={agent_id}, skills={skill_ids}")
    if commit:
        db.commit()
    return True
#合并Agent的所有Skill配置
def get_agent_skills_merged_config(db: Session, agent_id: int) -> Dict[str, Any]:
    """加载Agent绑定的所有Skill配置并合并ToolExecutor运行时调用：
      1. 查Agent绑定的所有Skill
      2. 逐个加载YML配置（调loader）
      3. 合并工具列表（并集）
      4. 合并工具默认值（同名的以先绑定的为准，不覆盖）
      5. 合并system_prompt（所有Skill的prompt拼接）
    :return: {
        "skill_names": ["论文写作助手", ...],
        "tool_names": ["outline_generator", "word_count", ...],  # 工具并集
        "tool_defaults_map": {"outline_generator": {"sections": 6}, ...},
        "system_prompt": "合并后的Skill prompt",
        "skills": [每个Skill的完整配置],
    }
    """
    skills = dao_list_by_agent(db,agent_id)
    if not skills:
        return {
            "skill_names": [],
            "tool_names": [],
            "tool_defaults_map": {},
            "system_prompt": "",
            "skills": [],
            "permissions": {"network": False, "file_read": [], "exec": False},
            "resource_roots": [],
            "resources": [],
        }
    merged_tool_names: List[str] = []
    merged_defaults: Dict[str, Dict] = {}
    skill_prompts: List[str] = []
    skill_configs: List[Dict] = []
    resource_roots: List[str] = []
    resources: List[Dict[str, Any]] = []
    load_errors: List[Dict[str, str]] = []
    for skill in skills:
        try:
            cfg = load_skill_config(skill.config_file)
        except Exception as e:
            logger.error(f"加载Skill配置失败: skill={skill.name}, error={e}")
            load_errors.append({"skill_name": skill.name, "error": str(e)})
            continue
        skill_configs.append(cfg)
        if cfg.get("resource_root") and cfg.get("resource_root") not in resource_roots:
            resource_roots.append(cfg.get("resource_root"))
        for resource in cfg.get("resources", []):
            item = dict(resource)
            item["skill_name"] = cfg.get("name")
            resources.append(item)
        # 工具并集（保持顺序，不重复）
        for name in cfg["tool_names"]:
            if name not in merged_tool_names:
                merged_tool_names.append(name)
        # 默认值合并（同名的以先绑定的为准，不覆盖）
        for name,defaults in cfg["tool_defaults_map"].items():
            if name not in merged_defaults:
                merged_defaults[name] = defaults
        # prompt拼接
        if cfg["system_prompt"]:
            skill_prompts.append(f"【Skill: {cfg['name']}】\n{cfg['system_prompt']}")
        if cfg.get("resource_text"):
            skill_prompts.append(f"【Skill资源: {cfg['name']}】\n{cfg['resource_text']}")
    merged_prompt = "\n\n".join(skill_prompts) if skill_prompts else ""
    logger.info(
        f"合并Agent Skill配置: agent={agent_id}, "
        f"skills={len(skill_configs)}个, tools={len(merged_tool_names)}个"
        + (f", 加载失败={len(load_errors)}个" if load_errors else "")
    )
    return {
        "skill_names": [cfg["name"] for cfg in skill_configs],
        "tool_names": merged_tool_names,
        "tool_defaults_map": merged_defaults,
        "system_prompt": merged_prompt,
        "skills": skill_configs,
        "permissions": {
            "network": any(bool(cfg.get("permissions", {}).get("network")) for cfg in skill_configs),
            "file_read": [
                path
                for cfg in skill_configs
                for path in cfg.get("permissions", {}).get("file_read", [])
            ],
            "exec": False,
        },
        "resource_roots": resource_roots,
        "resources": resources,
        "load_errors": load_errors,
    }
#辅助方法
def _skill_to_dict(skill) -> Dict:
    #Skill ORM对象转dict
    return {
        "id": skill.id,
        "user_id": skill.user_id,
        "name": skill.name,
        "description": skill.description,
        "config_file": skill.config_file,
        "is_public": skill.is_public,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
    }
