"""space permissions: space_members / kb_audit_log / organizations / teams（阶段6）

Revision ID: 20260911_0006
Revises: 20260910_0005
Create Date: 2026-09-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260911_0006"
down_revision: Union[str, Sequence[str], None] = "20260910_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "space_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.id"], name="fk_sm_space"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_sm_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_space_member", "space_members", ["space_id", "user_id"], unique=True)
    op.create_index("idx_space_member_user", "space_members", ["user_id"])

    op.create_table(
        "kb_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kb_audit_space_time", "kb_audit_log", ["space_id", "created_at"])
    op.create_index("idx_kb_audit_user", "kb_audit_log", ["user_id"])

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_team_org", "teams", ["organization_id"])


def downgrade() -> None:
    op.drop_index("idx_team_org", table_name="teams")
    op.drop_table("teams")
    op.drop_table("organizations")
    op.drop_index("idx_kb_audit_user", table_name="kb_audit_log")
    op.drop_index("idx_kb_audit_space_time", table_name="kb_audit_log")
    op.drop_table("kb_audit_log")
    op.drop_index("idx_space_member_user", table_name="space_members")
    op.drop_index("uq_space_member", table_name="space_members")
    op.drop_table("space_members")
