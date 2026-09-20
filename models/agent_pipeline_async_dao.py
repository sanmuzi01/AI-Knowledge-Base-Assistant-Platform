"""Agent 流水线（AgentPipeline）异步 DAO。"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import AgentPipeline


async def list_pipelines_by_user_async(db: AsyncSession, user_id: int) -> List[AgentPipeline]:
    result = await db.execute(
        select(AgentPipeline).where(AgentPipeline.user_id == user_id).order_by(AgentPipeline.id.desc())
    )
    return list(result.scalars().all())


async def get_owned_pipeline_async(db: AsyncSession, user_id: int, pipeline_id: int) -> Optional[AgentPipeline]:
    result = await db.execute(
        select(AgentPipeline).where(AgentPipeline.id == pipeline_id, AgentPipeline.user_id == user_id)
    )
    return result.scalars().first()


async def create_pipeline_async(
        db: AsyncSession, user_id: int, name: str, description: Optional[str], steps: List[Dict[str, Any]],
) -> AgentPipeline:
    pipeline = AgentPipeline(
        user_id=user_id, name=name, description=description,
        steps_json=json.dumps(steps, ensure_ascii=False), is_enabled=1,
    )
    db.add(pipeline)
    await db.flush()
    await db.commit()
    return pipeline


async def update_pipeline_async(db: AsyncSession, pipeline: AgentPipeline, fields: Dict[str, Any]) -> AgentPipeline:
    for key, value in fields.items():
        setattr(pipeline, key, value)
    await db.flush()
    await db.commit()
    return pipeline


async def delete_pipeline_async(db: AsyncSession, pipeline: AgentPipeline) -> None:
    await db.delete(pipeline)
    await db.commit()
