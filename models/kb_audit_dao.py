"""知识库审计日志 DAO（同步 + 异步）。写入尽力而为，调用方用 try/except 包住。"""

import json
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import KbAuditLog


def _detail_str(detail: Any) -> Optional[str]:
    if detail is None:
        return None
    if isinstance(detail, str):
        return detail[:2000]
    try:
        return json.dumps(detail, ensure_ascii=False)[:2000]
    except (TypeError, ValueError):
        return str(detail)[:2000]


def record(db, user_id: int, action: str, *, space_id: int = None,
           target_type: str = None, target_id: int = None, detail: Any = None,
           commit: bool = True) -> None:
    db.add(KbAuditLog(
        user_id=user_id, space_id=space_id, action=action,
        target_type=target_type, target_id=target_id, detail=_detail_str(detail),
    ))
    if commit:
        db.commit()
    else:
        db.flush()


def list_by_space(db, space_id: int, limit: int = 200) -> List[KbAuditLog]:
    return (
        db.query(KbAuditLog)
        .filter(KbAuditLog.space_id == space_id)
        .order_by(KbAuditLog.id.desc())
        .limit(limit)
        .all()
    )


async def record_async(db: AsyncSession, user_id: int, action: str, *, space_id: int = None,
                       target_type: str = None, target_id: int = None, detail: Any = None) -> None:
    db.add(KbAuditLog(
        user_id=user_id, space_id=space_id, action=action,
        target_type=target_type, target_id=target_id, detail=_detail_str(detail),
    ))
    await db.commit()


async def list_by_space_async(db: AsyncSession, space_id: int, limit: int = 200) -> List[KbAuditLog]:
    res = await db.execute(
        select(KbAuditLog).where(KbAuditLog.space_id == space_id)
        .order_by(KbAuditLog.id.desc()).limit(limit)
    )
    return list(res.scalars().all())
