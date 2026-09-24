"""baseline current schema

Revision ID: 20260830_0001
Revises:
Create Date: 2026-08-30
"""

from typing import Sequence, Union


revision: str = "20260830_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 基线迁移只负责把已有项目纳入版本管理。
    # 当前真实建表和旧字段补齐仍由 models/init_db.py 兼容处理。
    pass


def downgrade() -> None:
    # 基线版本不做破坏性回滚。
    pass
