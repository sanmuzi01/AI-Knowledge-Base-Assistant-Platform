"""技能的历史版本与回滚。

为什么需要：所有用户绑定的是同一份技能配置，管理员改错一次就影响所有人。
所以每次编辑（提示词 / 工具 / 权限 / 名称 / 说明，含翻译）之前先把当前的配置存一份快照，最多留最近 MAX_VERSIONS 个；
出问题时在后台「历史版本」里一键恢复。恢复本身也会先存一份当前状态，所以"恢复错了"也能再恢复回来。

存的是运行时 YML 原文（含脚本包路径和检查结果），恢复就是把原文写回去再校验；
是否公开（is_public）不随版本变——上架状态是另一件事，回滚提示词不应该顺带下架技能。
"""
import os
from typing import Any, Dict, List, Optional

from models import skill_version_dao as vdao
from models.skill_dao import get_skill_by_id as dao_get, update_skill as dao_update
from service.access_control import can_write_skill
from service.skills.loader import _get_yml_path, invalidate_skill_config
from utils.logger_handler import get_logger

from .validation import validate_skill_config_file

logger = get_logger("skill_service")

MAX_VERSIONS = 20


class VersionError(ValueError):
    """message 可以直接展示给用户。"""


def _read_config(skill) -> Optional[str]:
    try:
        path = _get_yml_path(skill.config_file)
    except Exception:  # noqa: BLE001 - 非法路径当作没有配置
        return None
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def snapshot_skill(db, skill, user_id: Optional[int], note: str, force: bool = False):
    """把当前状态存成一个版本。和上一个版本完全一样就不重复存（force=True 除外）。不 commit，由调用方提交。"""
    text = _read_config(skill)
    if text is None:
        return None
    last = vdao.latest(db, skill.id)
    if (not force and last is not None and last.config_text == text
            and last.name == skill.name and (last.description or "") == (skill.description or "")):
        return None
    row = vdao.create(db, skill.id, skill.name, skill.description or "", text, note, user_id)
    vdao.prune(db, skill.id, MAX_VERSIONS)
    return row


def snapshot_before_edit(db, skill_id: int, user_id: int) -> None:
    """编辑前调用。尽力而为：版本记录出问题不能挡住正常的编辑，只记日志。"""
    try:
        skill = dao_get(db, skill_id)
        if skill and can_write_skill(skill, user_id):
            snapshot_skill(db, skill, user_id, "编辑前自动保存")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"保存技能历史版本失败（不影响编辑）: skill={skill_id}, error={e}")


def delete_versions(db, skill_id: int) -> None:
    vdao.delete_all(db, skill_id)


def _to_dict(row) -> Dict[str, Any]:
    return {
        "id": row.id,
        "version_no": row.version_no,
        "name": row.name,
        "description": row.description or "",
        "note": row.note or "",
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "size": len(row.config_text or ""),
    }


def list_skill_versions(db, skill_id: int, user_id: int) -> Optional[List[Dict[str, Any]]]:
    """不是自己的技能返回 None。"""
    skill = dao_get(db, skill_id)
    if not skill or not can_write_skill(skill, user_id):
        return None
    return [_to_dict(r) for r in vdao.list_versions(db, skill_id, MAX_VERSIONS)]


def restore_skill_version(db, skill_id: int, version_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """恢复到指定版本。不是自己的技能返回 None；版本不存在或恢复后配置不可用抛 VersionError。"""
    skill = dao_get(db, skill_id)
    if not skill or not can_write_skill(skill, user_id):
        return None
    version = vdao.get(db, skill_id, version_id)
    if version is None:
        raise VersionError("这个版本不存在，可能已经被清理（只保留最近 %d 个版本）" % MAX_VERSIONS)

    current = _read_config(skill)
    if current is None:
        raise VersionError("这个技能的配置文件已经不存在，无法恢复")
    path = _get_yml_path(skill.config_file)

    snapshot_skill(db, skill, user_id, f"恢复到 v{version.version_no} 前自动保存", force=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(version.config_text)
    invalidate_skill_config(skill.config_file)

    validation = validate_skill_config_file(skill.config_file)
    if not validation["ok"]:
        # 旧版本现在已经不能用了（比如它引用的脚本包被清掉了）：把文件写回去，不要留一个坏配置
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(current)
        invalidate_skill_config(skill.config_file)
        db.rollback()
        raise VersionError("该版本现在已经不可用，未恢复：" + "；".join(validation["errors"][:2]))

    dao_update(db, skill_id, name=version.name, description=version.description or "")
    db.commit()
    return {"restored_to": version.version_no, "name": version.name}
