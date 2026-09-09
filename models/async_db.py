"""异步数据库入口。

面向上线和分布式部署时，路由层应该使用明确的异步数据库会话。
如果异步 MySQL 驱动缺失，应用启动阶段就应该暴露配置问题，而不是在
每个路由里写一遍“异步失败后走同步”的兼容分支。
"""

import importlib.util
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.init_db import (
    DB_HOST,
    DB_MAX_OVERFLOW,
    DB_NAME,
    DB_PASSWORD,
    DB_POOL_PRE_PING,
    DB_POOL_RECYCLE,
    DB_POOL_SIZE,
    DB_POOL_TIMEOUT,
    DB_PORT,
    DB_USER,
)


ASYNC_DB_DRIVER = "asyncmy"
ASYNC_DATABASE_URL = (
    f"mysql+{ASYNC_DB_DRIVER}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


def async_database_available() -> bool:
    """当前环境是否安装了异步 MySQL 驱动。"""

    return importlib.util.find_spec(ASYNC_DB_DRIVER) is not None


if not async_database_available():
    raise RuntimeError(f"缺少异步数据库驱动: {ASYNC_DB_DRIVER}")

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
    pool_pre_ping=DB_POOL_PRE_PING,
    pool_use_lifo=True,
    connect_args={"charset": "utf8mb4"},
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """返回异步数据库会话。"""

    async with AsyncSessionLocal() as session:
        yield session
