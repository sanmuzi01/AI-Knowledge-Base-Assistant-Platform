"""skill_version：技能配置的历史快照（管理员编辑前自动保存，可回滚）

Revision ID: 20260921_0007
Revises: 20260911_0006
Create Date: 2026-09-21

幂等：应用启动时的 bootstrap_database() 也会 create_all，线上可能已经先建好了这张表，
所以这里先检查表是否存在，存在就跳过，避免 `alembic upgrade head` 报 "already exists"。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql


revision: str = "20260921_0007"
down_revision: Union[str, Sequence[str], None] = "20260911_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "skill_version" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "skill_version",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("config_text", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_skill_version_skill", "skill_version", ["skill_id", "version_no"])


def downgrade() -> None:
    op.drop_table("skill_version")
