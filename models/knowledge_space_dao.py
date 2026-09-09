"""知识库空间 同步 DAO。

只做数据访问，不含权限判断（权限在 service/access_control 与 service/knowledge_space/*）。
"""

from typing import List, Optional

from models.init_db import KnowledgeSpace
from utils.timeutil import utcnow


def create_space(db, user_id: int, fields: dict) -> KnowledgeSpace:
    space = KnowledgeSpace(user_id=user_id, **fields)
    db.add(space)
    db.commit()
    db.refresh(space)
    return space


def get_space_by_id(db, space_id: int) -> Optional[KnowledgeSpace]:
    return db.query(KnowledgeSpace).filter(KnowledgeSpace.id == space_id).first()


def get_owned_space(db, user_id: int, space_id: int) -> Optional[KnowledgeSpace]:
    return (
        db.query(KnowledgeSpace)
        .filter(KnowledgeSpace.id == space_id, KnowledgeSpace.user_id == user_id)
        .first()
    )


def list_spaces_by_user(db, user_id: int, include_archived: bool = True) -> List[KnowledgeSpace]:
    q = db.query(KnowledgeSpace).filter(KnowledgeSpace.user_id == user_id)
    if not include_archived:
        q = q.filter(KnowledgeSpace.status == "active")
    return q.order_by(KnowledgeSpace.id.desc()).all()


def find_legacy_space(db, user_id: int, legacy_agent_id: int) -> Optional[KnowledgeSpace]:
    return (
        db.query(KnowledgeSpace)
        .filter(
            KnowledgeSpace.user_id == user_id,
            KnowledgeSpace.legacy_agent_id == legacy_agent_id,
        )
        .first()
    )


def update_space(db, space: KnowledgeSpace, fields: dict) -> KnowledgeSpace:
    for k, v in fields.items():
        setattr(space, k, v)
    space.updated_at = utcnow()
    db.commit()
    db.refresh(space)
    return space


def delete_space(db, space: KnowledgeSpace) -> None:
    db.delete(space)
    db.commit()


def set_stats(db, space_id: int, *, doc_count: int, chunk_count: int) -> None:
    space = get_space_by_id(db, space_id)
    if not space:
        return
    space.doc_count = doc_count
    space.chunk_count = chunk_count
    space.last_indexed_at = utcnow()
    db.commit()
