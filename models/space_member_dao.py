"""知识库空间成员 DAO（同步 + 异步）。

只做数据访问。owner 不落这张表（由 knowledge_spaces.user_id 隐含），
所以这里的 role 只会是 admin / editor / viewer。
"""

from typing import List, Optional

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import SpaceMember
from utils.timeutil import utcnow

MEMBER_ROLES = ("admin", "editor", "viewer")


# ---------------- 同步 ----------------

def get_role(db, space_id: int, user_id: int) -> Optional[str]:
    row = (
        db.query(SpaceMember.role)
        .filter(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
        .first()
    )
    return row[0] if row else None


def list_members(db, space_id: int) -> List[SpaceMember]:
    return (
        db.query(SpaceMember)
        .filter(SpaceMember.space_id == space_id)
        .order_by(SpaceMember.id.asc())
        .all()
    )


def list_space_ids_for_member(db, user_id: int) -> List[int]:
    rows = db.query(SpaceMember.space_id).filter(SpaceMember.user_id == user_id).all()
    return [r[0] for r in rows]


def upsert_member(db, space_id: int, user_id: int, role: str, *, commit: bool = True) -> SpaceMember:
    member = (
        db.query(SpaceMember)
        .filter(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
        .first()
    )
    if member:
        member.role = role
        member.updated_at = utcnow()
    else:
        member = SpaceMember(space_id=space_id, user_id=user_id, role=role)
        db.add(member)
    if commit:
        db.commit()
        db.refresh(member)
    else:
        db.flush()
    return member


def remove_member(db, space_id: int, user_id: int, *, commit: bool = True) -> int:
    n = (
        db.query(SpaceMember)
        .filter(SpaceMember.space_id == space_id, SpaceMember.user_id == user_id)
        .delete(synchronize_session=False)
    )
    if commit:
        db.commit()
    else:
        db.flush()
    return n


def delete_all_for_space(db, space_id: int, *, commit: bool = True) -> int:
    n = db.query(SpaceMember).filter(SpaceMember.space_id == space_id).delete(synchronize_session=False)
    if commit:
        db.commit()
    else:
        db.flush()
    return n


# ---------------- 异步 ----------------

async def get_role_async(db: AsyncSession, space_id: int, user_id: int) -> Optional[str]:
    res = await db.execute(
        select(SpaceMember.role).where(
            SpaceMember.space_id == space_id, SpaceMember.user_id == user_id
        )
    )
    row = res.first()
    return row[0] if row else None


async def list_members_async(db: AsyncSession, space_id: int) -> List[SpaceMember]:
    res = await db.execute(
        select(SpaceMember).where(SpaceMember.space_id == space_id).order_by(SpaceMember.id.asc())
    )
    return list(res.scalars().all())


async def list_space_ids_for_member_async(db: AsyncSession, user_id: int) -> List[int]:
    res = await db.execute(
        select(SpaceMember.space_id).where(SpaceMember.user_id == user_id)
    )
    return [row[0] for row in res.all()]


async def upsert_member_async(db: AsyncSession, space_id: int, user_id: int, role: str) -> SpaceMember:
    res = await db.execute(
        select(SpaceMember).where(
            SpaceMember.space_id == space_id, SpaceMember.user_id == user_id
        )
    )
    member = res.scalars().first()
    if member:
        member.role = role
        member.updated_at = utcnow()
    else:
        member = SpaceMember(space_id=space_id, user_id=user_id, role=role)
        db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member_async(db: AsyncSession, space_id: int, user_id: int) -> int:
    res = await db.execute(
        sa_delete(SpaceMember).where(
            SpaceMember.space_id == space_id, SpaceMember.user_id == user_id
        )
    )
    await db.commit()
    return res.rowcount or 0
