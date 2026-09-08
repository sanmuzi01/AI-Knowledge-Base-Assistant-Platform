"""add user profile table

Revision ID: 20260831_0002
Revises: 20260830_0001
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260831_0002"
down_revision: Union[str, Sequence[str], None] = "20260830_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("occupation", sa.String(length=100), nullable=True),
        sa.Column("skills", sa.Text(), nullable=True),
        sa.Column("preferences", sa.Text(), nullable=True),
        sa.Column("communication_style", sa.String(length=50), nullable=True, server_default="balanced"),
        sa.Column("persona", sa.String(length=50), nullable=True, server_default="professional"),
        sa.Column("extra_info", sa.Text(), nullable=True),
        sa.Column("auto_summary", sa.Text(), nullable=True),
        sa.Column("last_inferred_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_user_profile_user"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_profile_user_id"),
    )
    op.create_index("idx_user_profile_user_id", "user_profile", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_profile_user_id", table_name="user_profile")
    op.drop_table("user_profile")
