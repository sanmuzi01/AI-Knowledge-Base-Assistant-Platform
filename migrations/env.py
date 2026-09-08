from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv()

# 当前项目的模型定义仍集中在 models/init_db.py，导入该模块会创建连接并执行旧的
# create_all/幂等迁移。为了让 Alembic 命令保持纯粹，迁移环境暂不导入业务模型。
# 后续把模型和数据库初始化拆开后，可以把这里替换为 Base.metadata 以支持自动生成。
target_metadata = None


def _database_url() -> str:
    """从环境变量生成 Alembic 使用的数据库连接串。"""

    required = {
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT"),
        "DB_NAME": os.getenv("DB_NAME"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("缺少数据库环境变量: " + ", ".join(missing))

    return (
        f"mysql+pymysql://{required['DB_USER']}:{required['DB_PASSWORD']}"
        f"@{required['DB_HOST']}:{required['DB_PORT']}/{required['DB_NAME']}"
    )


def run_migrations_offline() -> None:
    """离线模式生成 SQL，不主动连接数据库。"""

    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式连接数据库并执行迁移脚本。"""

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
