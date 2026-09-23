"""用户异步 DAO。"""

from utils.timeutil import utcnow
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.init_db import User


async def get_user_by_id_async(db: AsyncSession, user_id: int) -> Optional[User]:
    """异步按 ID 查询用户，并预加载角色。"""

    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
    )
    return result.scalars().first()


async def get_user_by_name_async(db: AsyncSession, name: str) -> Optional[User]:
    """异步按用户名查询用户，并预加载角色。"""

    result = await db.execute(
        select(User)
        .where(User.name == name)
        .options(selectinload(User.roles))
    )
    return result.scalars().first()


async def get_users_by_ids_async(db: AsyncSession, user_ids: List[int]) -> Dict[int, str]:
    """{user_id: user_name}，用于成员/审计列表回填显示名。"""
    ids = [int(i) for i in dict.fromkeys(user_ids or [])]
    if not ids:
        return {}
    result = await db.execute(select(User.id, User.name).where(User.id.in_(ids)))
    return {row[0]: row[1] for row in result.all()}


async def get_user_by_phone_async(db: AsyncSession, phone: str) -> Optional[User]:
    """异步按手机号查询用户。"""

    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalars().first()


async def create_user_async(
        db: AsyncSession, name: str, password: str, age: int, phone: str = None,
) -> User:
    """异步创建用户。"""

    user = User(name=name, password=password, age=age, phone=phone)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def touch_user_seen_async(db: AsyncSession, user_id: int) -> bool:
    """异步更新用户最近访问时间。"""

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(last_seen_at=utcnow())
    )
    await db.commit()
    return True


async def update_user_login_seen_async(db: AsyncSession, user_id: int, login_at: datetime) -> None:
    """异步更新登录和最近访问时间。"""

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(last_login_at=login_at, last_seen_at=login_at)
    )
    await db.commit()


async def update_user_password_async(db: AsyncSession, user_id: int, password: str) -> None:
    """异步更新用户密码，同时让这个用户此前签发的所有 token 一起失效。

    用户改密码 / 短信重置密码 / 管理员重置密码都走这里。auth_version 用 SQL 表达式
    `auth_version + 1` 原地自增而不是"读出来再加一写回去"，避免两个请求（比如用户自己
    正在改密码、管理员同时把它强制下线）并发时其中一次自增被覆盖丢失。
    """

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(password=password, auth_version=User.auth_version + 1, password_changed_at=utcnow())
    )
    await db.commit()


async def bump_auth_version_async(db: AsyncSession, user_id: int) -> bool:
    """不改密码，只让这个用户已签发的 token 全部失效（强制下线 / 退出所有设备）。

    返回是否命中了用户（rowcount），调用方据此决定要不要 404。
    """

    result = await db.execute(
        update(User).where(User.id == user_id).values(auth_version=User.auth_version + 1)
    )
    await db.commit()
    return result.rowcount > 0
