"""用户异步 DAO。"""

from datetime import datetime
from typing import Optional

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
        .values(last_seen_at=datetime.utcnow())
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
    """异步更新用户密码。"""

    await db.execute(update(User).where(User.id == user_id).values(password=password))
    await db.commit()
