"""知识库空间健康分（阶段5）。

只读 DB（knowledge / rag_debug_samples / agent_knowledge_space），不跑向量检索、不调 LLM，
所以够快，既能当 `space_health` 后台任务批量刷，也能在详情页按需实时算。

明细指标：
  文档侧  total / enabled / done / failed / pending / stale（久未更新）
  质量侧  从「知识库调试台样例」统计 —— 命中率 / 拒答率 / 引用率 / 人工好评率
健康分 0~100 由这些指标加权，扣分项优先（失败 > 未入库 > 过期 > 低命中）。
"""

import json
import os
from typing import Any, Dict

from utils.logger_handler import get_logger
from utils.timeutil import utcnow

logger = get_logger("kb_health")


def _stale_days() -> int:
    try:
        return max(1, int(os.getenv("KB_STALE_DAYS", "90")))
    except (TypeError, ValueError):
        return 90


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def _collect_doc_metrics(db, space_id: int) -> Dict[str, Any]:
    from datetime import timedelta

    from models.init_db import Knowledge

    rows = db.query(Knowledge).filter(Knowledge.space_id == space_id).all()
    total = len(rows)
    enabled = sum(1 for r in rows if r.is_enabled != 0)
    done = sum(1 for r in rows if r.status == "done")
    failed = sum(1 for r in rows if r.status == "failed")
    pending = sum(1 for r in rows if r.status in ("pending", "processing"))
    empty = sum(1 for r in rows if r.status == "done" and int(r.chunk_count or 0) == 0)

    stale_before = utcnow() - timedelta(days=_stale_days())
    stale = 0
    for r in rows:
        ts = r.updated_at or r.created_at
        if ts and ts < stale_before:
            stale += 1

    return {
        "total": total,
        "enabled": enabled,
        "done": done,
        "failed": failed,
        "pending": pending,
        "empty_done": empty,
        "stale": stale,
        "failed_rate": _rate(failed, total),
        "pending_rate": _rate(pending, total),
        "stale_rate": _rate(stale, total),
        "disabled_rate": _rate(total - enabled, total),
        "chunk_count": sum(int(r.chunk_count or 0) for r in rows),
    }


def _collect_sample_metrics(db, space_id: int) -> Dict[str, Any]:
    from models.init_db import RagDebugSample

    rows = db.query(RagDebugSample).filter(RagDebugSample.space_id == space_id).all()
    total = len(rows)
    if not total:
        return {"sample_count": 0, "hit_rate": None, "refuse_rate": None,
                "citation_rate": None, "useful_rate": None}

    hit = refused = with_answer = cited = verdict_total = useful = 0
    for r in rows:
        try:
            result = json.loads(r.result_json) if r.result_json else {}
        except (TypeError, ValueError):
            result = {}
        hits = result.get("hits") or []
        if hits:
            hit += 1
        if result.get("refused"):
            refused += 1
        if result.get("answer"):
            with_answer += 1
            if result.get("citations"):
                cited += 1
        if r.verdict in ("useful", "useless"):
            verdict_total += 1
            if r.verdict == "useful":
                useful += 1

    return {
        "sample_count": total,
        "hit_rate": _rate(hit, total),
        "refuse_rate": _rate(refused, total),
        "citation_rate": _rate(cited, with_answer) if with_answer else None,
        "useful_rate": _rate(useful, verdict_total) if verdict_total else None,
    }


def _score(docs: Dict[str, Any], samples: Dict[str, Any]) -> int:
    """0~100。空空间给中性 60；否则从 100 起扣。"""
    if docs["total"] == 0:
        return 60

    score = 100.0
    score -= docs["failed_rate"] * 45
    score -= docs["pending_rate"] * 15
    score -= docs["stale_rate"] * 20
    score -= _rate(docs["empty_done"], docs["total"]) * 15

    if samples["sample_count"] >= 3:
        # 有足够调试样例时，命中率 / 拒答率 也纳入
        score -= (1 - (samples["hit_rate"] or 0)) * 15
        score -= (samples["refuse_rate"] or 0) * 10
        if samples["useful_rate"] is not None:
            score -= (1 - samples["useful_rate"]) * 10

    return max(0, min(100, round(score)))


def compute_health(db, space_id: int) -> Dict[str, Any]:
    """算一次健康快照（不落库）。"""
    docs = _collect_doc_metrics(db, space_id)
    samples = _collect_sample_metrics(db, space_id)
    score = _score(docs, samples)
    return {
        "space_id": space_id,
        "health_score": score,
        "level": "good" if score >= 80 else "fair" if score >= 55 else "poor",
        "documents": docs,
        "retrieval": samples,
        "stale_days": _stale_days(),
        "computed_at": utcnow().isoformat(),
    }


def persist_health(db, space_id: int, snapshot: Dict[str, Any]) -> None:
    from models.knowledge_space_dao import get_space_by_id

    space = get_space_by_id(db, space_id)
    if not space:
        return
    space.health_score = snapshot["health_score"]
    space.health_json = json.dumps(snapshot, ensure_ascii=False)
    space.updated_at = utcnow()
    db.commit()


def compute_and_persist(db, space_id: int) -> Dict[str, Any]:
    snapshot = compute_health(db, space_id)
    persist_health(db, space_id, snapshot)
    return snapshot


# --------- 自带 Session 的入口（详情页按需 / Widget connector 经 to_thread 调） ---------

def health_snapshot(user_id: int, space_id: int, *, persist: bool = False) -> Dict[str, Any]:
    """校验空间归属后算一次健康分。persist=True 时回写 knowledge_spaces.health_*。

    归属不符 -> PermissionError（路由层转 404，不泄露存在性）。
    """
    from models.init_db import SessionLocal
    from service.access_control import get_owned_space

    db = SessionLocal()
    try:
        if get_owned_space(db, user_id, space_id) is None:
            raise PermissionError("知识库空间不存在或无权限")
        snapshot = compute_health(db, space_id)
        if persist:
            persist_health(db, space_id, snapshot)
        return snapshot
    finally:
        db.close()
