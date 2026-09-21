"""技能历史版本的读写（同步 Session）。"""
from typing import List, Optional

from models.init_db import SkillVersion


def latest(db, skill_id: int) -> Optional[SkillVersion]:
    return (
        db.query(SkillVersion)
        .filter(SkillVersion.skill_id == skill_id)
        .order_by(SkillVersion.version_no.desc())
        .first()
    )


def create(db, skill_id: int, name: str, description: str, config_text: str, note: str,
           created_by: Optional[int]) -> SkillVersion:
    last = latest(db, skill_id)
    row = SkillVersion(
        skill_id=skill_id,
        version_no=(last.version_no if last else 0) + 1,
        name=name,
        description=description or "",
        config_text=config_text,
        note=note[:200],
        created_by=created_by,
    )
    db.add(row)
    db.flush()
    return row


def list_versions(db, skill_id: int, limit: int = 50) -> List[SkillVersion]:
    return (
        db.query(SkillVersion)
        .filter(SkillVersion.skill_id == skill_id)
        .order_by(SkillVersion.version_no.desc())
        .limit(limit)
        .all()
    )


def get(db, skill_id: int, version_id: int) -> Optional[SkillVersion]:
    return (
        db.query(SkillVersion)
        .filter(SkillVersion.skill_id == skill_id, SkillVersion.id == version_id)
        .first()
    )


def prune(db, skill_id: int, keep: int) -> int:
    """只留最近 keep 个版本，返回删除了几个。"""
    old = (
        db.query(SkillVersion.id)
        .filter(SkillVersion.skill_id == skill_id)
        .order_by(SkillVersion.version_no.desc())
        .offset(keep)
        .all()
    )
    ids = [r[0] for r in old]
    if ids:
        db.query(SkillVersion).filter(SkillVersion.id.in_(ids)).delete(synchronize_session=False)
    return len(ids)


def delete_all(db, skill_id: int) -> int:
    return db.query(SkillVersion).filter(SkillVersion.skill_id == skill_id).delete(synchronize_session=False)
