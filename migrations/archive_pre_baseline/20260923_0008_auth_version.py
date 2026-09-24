"""user.auth_version / user.password_changed_at：token 版本号，用于让旧 token 主动失效

Revision ID: 20260923_0008
Revises: 20260921_0007
Create Date: 2026-09-23

幂等：应用启动时的 bootstrap_database() 也会补这两列，线上可能已经先加好了，
所以这里先检查列是否存在，存在就跳过，避免 `alembic upgrade head` 报 "duplicate column"。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260923_0008"
down_revision: Union[str, Sequence[str], None] = "20260921_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_columns() -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user")}


def upgrade() -> None:
    cols = _existing_columns()
    if "auth_version" not in cols:
        op.add_column(
            "user",
            sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0",
                      comment="token 版本号，改密码/强制下线时+1"),
        )
    if "password_changed_at" not in cols:
        op.add_column(
            "user",
            sa.Column("password_changed_at", sa.DateTime(), nullable=True, comment="最近一次修改密码时间"),
        )


def downgrade() -> None:
    cols = _existing_columns()
    if "password_changed_at" in cols:
        op.drop_column("user", "password_changed_at")
    if "auth_version" in cols:
        op.drop_column("user", "auth_version")
