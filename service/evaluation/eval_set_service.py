"""固定评估集编排：创建/列出问题集，跑一次并和上一轮自动比较。

之前 `/evaluation/{agent_id}/rag` 是「每次请求带 cases 现算现返回」，没有地方沉淀
一份可重复回归用的问题集，改完东西也没法知道效果是变好还是变差了。这一层把
`rag_eval_service` 现成的打分引擎接上持久化：建一次问题集，之后随时重跑，
每次都存一条运行快照，自动跟上一轮比对出回归/变好的问题。

Phase 3 收尾（docs/sync-async-boundary.md）：整层改成 AsyncSession——
`evaluate_rag_dataset` 已经切到 `rag_service.search_async`（原生 async，需要
AsyncSession），这一层如果还传同步 Session 会直接类型不对，所以 DAO、路由跟着一起改。
"""
import json
from typing import Any, Dict, List, Optional

from models import eval_async_dao as eval_dao
from service.evaluation.rag_eval_service import evaluate_rag_dataset, run_for_space


def _set_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "agent_id": row.agent_id,
        "space_id": row.space_id,
        "cases": json.loads(row.cases_json),
        "settings": json.loads(row.settings_json or "{}"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def create_eval_set(
        db, user_id: int, name: str, cases: List[Dict[str, Any]],
        *, agent_id: int = None, space_id: int = None, settings: Dict[str, Any] = None,
) -> Dict[str, Any]:
    if not cases:
        raise ValueError("评估集至少要有一条问题")
    if agent_id is None and space_id is None:
        raise ValueError("必须指定 agent_id 或 space_id 其中之一")
    if agent_id is not None and space_id is not None:
        raise ValueError("agent_id 和 space_id 只能二选一")
    row = await eval_dao.create_eval_set_async(
        db, user_id, name, cases, agent_id=agent_id, space_id=space_id, settings=settings,
    )
    await db.commit()
    return _set_to_dict(row)


async def list_eval_sets(
        db, user_id: int, *, agent_id: int = None, space_id: int = None,
) -> List[Dict[str, Any]]:
    rows = await eval_dao.list_eval_sets_async(db, user_id, agent_id=agent_id, space_id=space_id)
    return [_set_to_dict(r) for r in rows]


async def get_eval_set(db, user_id: int, eval_set_id: int) -> Dict[str, Any]:
    row = await eval_dao.get_owned_eval_set_async(db, user_id, eval_set_id)
    if not row:
        raise ValueError("评估集不存在或无权限")
    return _set_to_dict(row)


async def delete_eval_set(db, user_id: int, eval_set_id: int) -> None:
    row = await eval_dao.get_owned_eval_set_async(db, user_id, eval_set_id)
    if not row:
        raise ValueError("评估集不存在或无权限")
    await eval_dao.delete_eval_set_async(db, row)
    await db.commit()


def _diff_against_previous(
        report: Dict[str, Any], previous_report: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """逐条 case 对比这次和上一轮：谁从命中变没命中（回归），谁从没命中变命中（变好）。"""
    if not previous_report:
        return None
    prev_by_question = {c["question"]: c for c in previous_report.get("cases", [])}
    regressed, improved = [], []
    for case in report.get("cases", []):
        prev = prev_by_question.get(case["question"])
        if not prev:
            continue
        prev_hit, cur_hit = prev.get("hit"), case.get("hit")
        if prev_hit is None or cur_hit is None:
            continue
        if prev_hit and not cur_hit:
            regressed.append(case["question"])
        elif not prev_hit and cur_hit:
            improved.append(case["question"])

    metric_deltas = {}
    for key in ("hit_rate", "recall", "precision_at_k", "mrr", "faithfulness"):
        cur = (report.get("metrics") or {}).get(key)
        prev = (previous_report.get("metrics") or {}).get(key)
        if cur is not None and prev is not None:
            metric_deltas[key] = round(cur - prev, 4)
    return {"regressed_questions": regressed, "improved_questions": improved, "metric_deltas": metric_deltas}


async def run_eval_set(db, user_id: int, eval_set_id: int) -> Dict[str, Any]:
    row = await eval_dao.get_owned_eval_set_async(db, user_id, eval_set_id)
    if not row:
        raise ValueError("评估集不存在或无权限")
    cases = json.loads(row.cases_json)
    settings = json.loads(row.settings_json or "{}")

    previous = await eval_dao.get_latest_eval_run_async(db, eval_set_id)
    previous_report = json.loads(previous.report_json) if previous else None

    if row.space_id is not None:
        report = await run_for_space(
            user_id, [row.space_id], cases,
            top_k=settings.get("top_k", 5), rerank=settings.get("rerank"),
            text_match_threshold=settings.get("text_match_threshold", 0.35),
            faithfulness_threshold=settings.get("faithfulness_threshold", 0.25),
        )
    else:
        report = await evaluate_rag_dataset(
            db, user_id, row.agent_id, cases,
            top_k=settings.get("top_k", 5),
            text_match_threshold=settings.get("text_match_threshold", 0.35),
            faithfulness_threshold=settings.get("faithfulness_threshold", 0.25),
            faithfulness_judge_model=settings.get("faithfulness_judge_model"),
        )

    run_row = await eval_dao.create_eval_run_async(db, eval_set_id, report)
    await db.commit()

    return {
        "run_id": run_row.id,
        "eval_set_id": eval_set_id,
        "report": report,
        "diff": _diff_against_previous(report, previous_report),
    }


async def list_eval_runs(db, user_id: int, eval_set_id: int) -> List[Dict[str, Any]]:
    row = await eval_dao.get_owned_eval_set_async(db, user_id, eval_set_id)
    if not row:
        raise ValueError("评估集不存在或无权限")
    runs = await eval_dao.list_eval_runs_async(db, eval_set_id)
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "metrics": {
                "hit_rate": r.hit_rate,
                "recall": r.recall,
                "precision_at_k": r.precision_at_k,
                "mrr": r.mrr,
                "faithfulness": r.faithfulness,
            },
        }
        for r in runs
    ]
