"""通用审计事件 DAO（同步 + 异步）。跟 kb_audit_dao.py 是同一种形状，服务的是
`AuditEvent` 表而不是 `KbAuditLog`——两张表的关系见 models/init_db.py 里 AuditEvent
的类文档。只有 `record[_async]`/`list_by_resource[_async]`，没有改/删函数：审计只追加。
"""

import json
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import AuditEvent


def _detail_str(detail: Any) -> Optional[str]:
    if detail is None:
        return None
    if isinstance(detail, str):
        return detail[:2000]
    try:
        return json.dumps(detail, ensure_ascii=False)[:2000]
    except (TypeError, ValueError):
        return str(detail)[:2000]


def record(db, user_id: int, action: str, *, resource_type: str = None,
           resource_id: int = None, detail: Any = None, commit: bool = True) -> None:
    db.add(AuditEvent(
        user_id=user_id, action=action,
        resource_type=resource_type, resource_id=resource_id, detail=_detail_str(detail),
    ))
    if commit:
        db.commit()
    else:
        db.flush()


def list_by_resource(db, resource_type: str, resource_id: int, limit: int = 200) -> List[AuditEvent]:
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.resource_type == resource_type, AuditEvent.resource_id == resource_id)
        .order_by(AuditEvent.id.desc())
        .limit(limit)
        .all()
    )


async def record_async(db: AsyncSession, user_id: int, action: str, *, resource_type: str = None,
                        resource_id: int = None, detail: Any = None) -> None:
    db.add(AuditEvent(
        user_id=user_id, action=action,
        resource_type=resource_type, resource_id=resource_id, detail=_detail_str(detail),
    ))
    await db.commit()


async def list_by_resource_async(db: AsyncSession, resource_type: str, resource_id: int,
                                  limit: int = 200) -> List[AuditEvent]:
    res = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.resource_type == resource_type, AuditEvent.resource_id == resource_id)
        .order_by(AuditEvent.id.desc()).limit(limit)
    )
    return list(res.scalars().all())
