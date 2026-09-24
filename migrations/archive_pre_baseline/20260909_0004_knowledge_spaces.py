"""knowledge spaces: tables + knowledge.space_id / agent.kb_* columns

Revision ID: 20260909_0004
Revises: 20260909_0003
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260909_0004"
down_revision: Union[str, Sequence[str], None] = "20260909_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_spaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("purpose", sa.String(length=60), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("doc_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_indexed_at", sa.DateTime(), nullable=True),
        sa.Column("health_score", sa.Integer(), nullable=True),
        sa.Column("health_json", sa.Text(), nullable=True),
        sa.Column("legacy_agent_id", sa.Integer(), nullable=True),
        sa.Column("vector_migrated", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_kspace_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kspace_user_status", "knowledge_spaces", ["user_id", "status"])
    op.create_index("idx_kspace_team", "knowledge_spaces", ["team_id"])
    op.create_index("idx_kspace_org", "knowledge_spaces", ["organization_id"])

    op.create_table(
        "agent_knowledge_space",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], name="fk_aks_agent"),
        sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.id"], name="fk_aks_space"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_agent_space", "agent_knowledge_space", ["agent_id", "space_id"], unique=True)
    op.create_index("idx_aks_space", "agent_knowledge_space", ["space_id"])

    for name, col in [
        ("space_id", sa.Column("space_id", sa.Integer(), nullable=True)),
        ("category", sa.Column("category", sa.String(length=60), nullable=True)),
        ("tags_json", sa.Column("tags_json", sa.Text(), nullable=True)),
        ("version", sa.Column("version", sa.String(length=40), nullable=True)),
        ("source_type", sa.Column("source_type", sa.String(length=20), nullable=False, server_default="upload")),
        ("source_url", sa.Column("source_url", sa.String(length=1000), nullable=True)),
        ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
    ]:
        op.add_column("knowledge", col)
    op.create_index("idx_knowledge_space_enabled_status", "knowledge", ["space_id", "is_enabled", "status"])

    for name, default in [
        ("kb_top_k", "5"),
        ("kb_rerank_enabled", "0"),
        ("kb_force_citation", "1"),
        ("kb_refuse_when_empty", "1"),
    ]:
        op.add_column("agent", sa.Column(name, sa.Integer(), nullable=False, server_default=default))


def downgrade() -> None:
    for name in ("kb_refuse_when_empty", "kb_force_citation", "kb_rerank_enabled", "kb_top_k"):
        op.drop_column("agent", name)
    op.drop_index("idx_knowledge_space_enabled_status", table_name="knowledge")
    for name in ("updated_at", "source_url", "source_type", "version", "tags_json", "category", "space_id"):
        op.drop_column("knowledge", name)
    op.drop_index("idx_aks_space", table_name="agent_knowledge_space")
    op.drop_index("uq_agent_space", table_name="agent_knowledge_space")
    op.drop_table("agent_knowledge_space")
    op.drop_index("idx_kspace_org", table_name="knowledge_spaces")
    op.drop_index("idx_kspace_team", table_name="knowledge_spaces")
    op.drop_index("idx_kspace_user_status", table_name="knowledge_spaces")
    op.drop_table("knowledge_spaces")
