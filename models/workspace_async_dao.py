"""用户工作台异步 DAO。"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import UserWorkspace


async def get_workspace_by_user_async(db: AsyncSession, user_id: int) -> Optional[UserWorkspace]:
    result = await db.execute(select(UserWorkspace).where(UserWorkspace.user_id == user_id))
    return result.scalars().first()


async def create_workspace_async(
        db: AsyncSession,
        user_id: int,
        modules_json: str,
        widgets_json: str,
        layout_json: str = None,
) -> UserWorkspace:
    workspace = UserWorkspace(
        user_id=user_id,
        modules_json=modules_json,
        widgets_json=widgets_json,
        layout_json=layout_json,
    )
    db.add(workspace)
    await db.flush()
    await db.refresh(workspace)
    return workspace
