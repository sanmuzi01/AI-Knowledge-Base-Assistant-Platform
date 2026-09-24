"""add user_widgets and widget_data_points tables

Revision ID: 20260909_0003
Revises: 20260831_0002
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260909_0003"
down_revision: Union[str, Sequence[str], None] = "20260831_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_widgets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("spec_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("capabilities_json", sa.Text(), nullable=True),
        sa.Column("data_source_json", sa.Text(), nullable=True),
        sa.Column("processor_json", sa.Text(), nullable=True),
        sa.Column("view_json", sa.Text(), nullable=True),
        sa.Column("trigger_json", sa.Text(), nullable=True),
        sa.Column("actions_json", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], name="fk_user_widgets_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_user_widgets_user_sort", "user_widgets", ["user_id", "sort_order"])
    op.create_index("idx_user_widgets_next_run", "user_widgets", ["enabled", "next_run_at"])

    op.create_table(
        "widget_data_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("widget_id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ok", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["widget_id"], ["user_widgets.id"], name="fk_widget_data_points_widget"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_widget_data_points_widget_time", "widget_data_points", ["widget_id", "recorded_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_widget_data_points_widget_time", table_name="widget_data_points")
    op.drop_table("widget_data_points")
    op.drop_index("idx_user_widgets_next_run", table_name="user_widgets")
    op.drop_index("idx_user_widgets_user_sort", table_name="user_widgets")
    op.drop_table("user_widgets")
