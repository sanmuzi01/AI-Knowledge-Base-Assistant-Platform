"""固定评估集 DAO 的 AsyncSession 版（models/eval_dao.py 的异步双胞胎）。

字段/归属规则跟同步版完全一致，只是查询走 AsyncSession。这是 Phase 3 收尾"继续把
同步接口迁到异步"的最后一段——docs/sync-async-boundary.md 里
`FasdtApi/evaluation.py` 那条尾巴，async 化后 `rag_service.async_search`
（半异步：向量化 async、DAO 反查同步，直接在事件循环里跑同步 DB 调用）
才能真正退役。
"""
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.init_db import EvalRun, EvalSet


async def create_eval_set_async(
        db: AsyncSession, user_id: int, name: str, cases: List[Dict[str, Any]],
        *, agent_id: int = None, space_id: int = None, settings: Dict[str, Any] = None,
) -> EvalSet:
    row = EvalSet(
        user_id=user_id, agent_id=agent_id, space_id=space_id, name=name,
        cases_json=json.dumps(cases, ensure_ascii=False),
        settings_json=json.dumps(settings or {}, ensure_ascii=False),
    )
    db.add(row)
    await db.flush()
    return row


async def get_owned_eval_set_async(db: AsyncSession, user_id: int, eval_set_id: int) -> Optional[EvalSet]:
    res = await db.execute(
        select(EvalSet).where(EvalSet.id == eval_set_id, EvalSet.user_id == user_id)
    )
    return res.scalars().first()


async def list_eval_sets_async(
        db: AsyncSession, user_id: int, *, agent_id: int = None, space_id: int = None,
) -> List[EvalSet]:
    stmt = select(EvalSet).where(EvalSet.user_id == user_id)
    if agent_id is not None:
        stmt = stmt.where(EvalSet.agent_id == agent_id)
    if space_id is not None:
        stmt = stmt.where(EvalSet.space_id == space_id)
    res = await db.execute(stmt.order_by(EvalSet.created_at.desc()))
    return list(res.scalars().all())


async def delete_eval_set_async(db: AsyncSession, row: EvalSet) -> None:
    await db.execute(sa_delete(EvalRun).where(EvalRun.eval_set_id == row.id))
    await db.delete(row)
    await db.flush()


async def create_eval_run_async(db: AsyncSession, eval_set_id: int, report: Dict[str, Any]) -> EvalRun:
    metrics = report.get("metrics") or {}
    row = EvalRun(
        eval_set_id=eval_set_id,
        hit_rate=metrics.get("hit_rate"),
        recall=metrics.get("recall"),
        precision_at_k=metrics.get("precision_at_k"),
        mrr=metrics.get("mrr"),
        faithfulness=metrics.get("faithfulness"),
        report_json=json.dumps(report, ensure_ascii=False),
    )
    db.add(row)
    await db.flush()
    return row


async def list_eval_runs_async(db: AsyncSession, eval_set_id: int, limit: int = 20) -> List[EvalRun]:
    res = await db.execute(
        select(EvalRun)
        .where(EvalRun.eval_set_id == eval_set_id)
        .order_by(EvalRun.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_latest_eval_run_async(db: AsyncSession, eval_set_id: int) -> Optional[EvalRun]:
    res = await db.execute(
        select(EvalRun)
        .where(EvalRun.eval_set_id == eval_set_id)
        .order_by(EvalRun.created_at.desc())
        .limit(1)
    )
    return res.scalars().first()
