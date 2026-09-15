"""固定评估集 DAO：EvalSet（问题集本体）+ EvalRun（每次运行的结果快照）。"""
import json
from typing import Any, Dict, List, Optional

from models.init_db import EvalRun, EvalSet


def create_eval_set(
        db, user_id: int, name: str, cases: List[Dict[str, Any]],
        *, agent_id: int = None, space_id: int = None, settings: Dict[str, Any] = None,
) -> EvalSet:
    row = EvalSet(
        user_id=user_id, agent_id=agent_id, space_id=space_id, name=name,
        cases_json=json.dumps(cases, ensure_ascii=False),
        settings_json=json.dumps(settings or {}, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    return row


def get_owned_eval_set(db, user_id: int, eval_set_id: int) -> Optional[EvalSet]:
    return (
        db.query(EvalSet)
        .filter(EvalSet.id == eval_set_id, EvalSet.user_id == user_id)
        .first()
    )


def list_eval_sets(
        db, user_id: int, *, agent_id: int = None, space_id: int = None,
) -> List[EvalSet]:
    q = db.query(EvalSet).filter(EvalSet.user_id == user_id)
    if agent_id is not None:
        q = q.filter(EvalSet.agent_id == agent_id)
    if space_id is not None:
        q = q.filter(EvalSet.space_id == space_id)
    return q.order_by(EvalSet.created_at.desc()).all()


def delete_eval_set(db, row: EvalSet) -> None:
    db.query(EvalRun).filter(EvalRun.eval_set_id == row.id).delete(synchronize_session=False)
    db.delete(row)
    db.flush()


def create_eval_run(db, eval_set_id: int, report: Dict[str, Any]) -> EvalRun:
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
    db.flush()
    return row


def list_eval_runs(db, eval_set_id: int, limit: int = 20) -> List[EvalRun]:
    return (
        db.query(EvalRun)
        .filter(EvalRun.eval_set_id == eval_set_id)
        .order_by(EvalRun.created_at.desc())
        .limit(limit)
        .all()
    )


def get_latest_eval_run(db, eval_set_id: int) -> Optional[EvalRun]:
    return (
        db.query(EvalRun)
        .filter(EvalRun.eval_set_id == eval_set_id)
        .order_by(EvalRun.created_at.desc())
        .first()
    )
