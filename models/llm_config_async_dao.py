"""模型配置异步 DAO。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import LLMConfig


async def get_config_by_user_and_model_async(
        db: AsyncSession, user_id: int, model_name: str,
) -> Optional[LLMConfig]:
    """异步查询用户某个模型配置。"""

    result = await db.execute(
        select(LLMConfig).where(
            LLMConfig.user_id == user_id,
            LLMConfig.model_name == model_name,
        )
    )
    return result.scalars().first()


async def list_configs_by_user_async(db: AsyncSession, user_id: int) -> List[LLMConfig]:
    """异步查询用户全部模型配置。"""

    result = await db.execute(
        select(LLMConfig)
        .where(LLMConfig.user_id == user_id)
        .order_by(LLMConfig.id.desc())
    )
    return list(result.scalars().all())


async def create_config_async(
        db: AsyncSession,
        user_id: int,
        model_name: str,
        api_key: str,
        api_url: str = None,
) -> LLMConfig:
    config = LLMConfig(
        user_id=user_id,
        model_name=model_name,
        api_key=api_key,
        api_url=api_url,
        is_active=1,
    )
    db.add(config)
    await db.flush()
    return config


async def update_config_async(
        db: AsyncSession,
        config: LLMConfig,
        api_key: str = None,
        api_url: str = None,
        is_active: int = None,
) -> LLMConfig:
    if api_key is not None:
        config.api_key = api_key
    if api_url is not None:
        config.api_url = api_url
    if is_active is not None:
        config.is_active = is_active
    await db.flush()
    return config


async def delete_config_async(db: AsyncSession, config: LLMConfig) -> None:
    await db.delete(config)
    await db.flush()
