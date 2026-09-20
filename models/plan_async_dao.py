"""套餐（Plan）+ 用户订阅（UserSubscription）异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import Plan, UserSubscription


async def list_plans_async(db: AsyncSession) -> List[Plan]:
    result = await db.execute(select(Plan).order_by(Plan.id.asc()))
    return list(result.scalars().all())


async def get_plan_async(db: AsyncSession, plan_id: int) -> Optional[Plan]:
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    return result.scalars().first()


async def get_plan_by_name_async(db: AsyncSession, name: str) -> Optional[Plan]:
    result = await db.execute(select(Plan).where(Plan.name == name))
    return result.scalars().first()


async def get_default_plan_async(db: AsyncSession) -> Optional[Plan]:
    result = await db.execute(select(Plan).where(Plan.is_default == 1).limit(1))
    return result.scalars().first()


async def count_subscriptions_for_plan_async(db: AsyncSession, plan_id: int) -> int:
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(UserSubscription.id)).where(UserSubscription.plan_id == plan_id)
    )
    return int(result.scalar() or 0)


async def get_subscription_async(db: AsyncSession, user_id: int) -> Optional[UserSubscription]:
    result = await db.execute(select(UserSubscription).where(UserSubscription.user_id == user_id))
    return result.scalars().first()


async def get_effective_plan_async(db: AsyncSession, user_id: int) -> Optional[Plan]:
    """用户当前生效套餐：有订阅用订阅的，没有则回退默认套餐，都没有则 None（视为不限量）。"""
    result = await db.execute(
        select(Plan)
        .join(UserSubscription, UserSubscription.plan_id == Plan.id)
        .where(UserSubscription.user_id == user_id)
    )
    plan = result.scalars().first()
    if plan is not None:
        return plan
    return await get_default_plan_async(db)


async def set_user_plan_async(db: AsyncSession, user_id: int, plan_id: int) -> UserSubscription:
    sub = await get_subscription_async(db, user_id)
    if sub:
        sub.plan_id = plan_id
    else:
        sub = UserSubscription(user_id=user_id, plan_id=plan_id)
        db.add(sub)
    await db.flush()
    await db.commit()
    return sub
