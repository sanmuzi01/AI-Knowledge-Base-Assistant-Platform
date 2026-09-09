"""rag debug samples: 知识库调试台样例表

Revision ID: 20260910_0005
Revises: 20260909_0004
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260910_0005"
down_revision: Union[str, Sequence[str], None] = "20260909_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_debug_samples",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=True),
        sa.Column("space_ids_json", sa.Text(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=True),
        sa.Column("rerank_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("verdict", sa.String(length=10), nullable=True),
        sa.Column("in_eval_set", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_rds_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_rds_user_created", "rag_debug_samples", ["user_id", "created_at"])
    op.create_index("idx_rds_space", "rag_debug_samples", ["space_id"])


def downgrade() -> None:
    op.drop_index("idx_rds_space", table_name="rag_debug_samples")
    op.drop_index("idx_rds_user_created", table_name="rag_debug_samples")
    op.drop_table("rag_debug_samples")
