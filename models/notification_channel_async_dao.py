"""外部告警推送通道（NotificationChannel）异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import NotificationChannel
from utils.timeutil import utcnow


async def list_channels_async(db: AsyncSession, user_id: int) -> List[NotificationChannel]:
    result = await db.execute(
        select(NotificationChannel).where(NotificationChannel.user_id == user_id)
        .order_by(NotificationChannel.id.asc())
    )
    return list(result.scalars().all())


async def list_enabled_channels_async(db: AsyncSession, user_id: int) -> List[NotificationChannel]:
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.user_id == user_id, NotificationChannel.is_enabled == 1,
        )
    )
    return list(result.scalars().all())


async def get_owned_channel_async(db: AsyncSession, user_id: int, channel_id: int) -> Optional[NotificationChannel]:
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id, NotificationChannel.user_id == user_id,
        )
    )
    return result.scalars().first()


async def create_channel_async(db: AsyncSession, user_id: int, name: str, webhook_url: str) -> NotificationChannel:
    channel = NotificationChannel(user_id=user_id, name=name, kind="webhook", webhook_url=webhook_url, is_enabled=1)
    db.add(channel)
    await db.flush()
    await db.commit()
    return channel


async def update_channel_async(db: AsyncSession, channel: NotificationChannel, fields: dict) -> NotificationChannel:
    for key, value in fields.items():
        setattr(channel, key, value)
    await db.flush()
    await db.commit()
    return channel


async def delete_channel_async(db: AsyncSession, channel: NotificationChannel) -> None:
    await db.delete(channel)
    await db.commit()


async def mark_sent_async(db: AsyncSession, channel: NotificationChannel, *, error: Optional[str]) -> None:
    channel.last_sent_at = utcnow()
    channel.last_error = error
    await db.flush()
    await db.commit()
