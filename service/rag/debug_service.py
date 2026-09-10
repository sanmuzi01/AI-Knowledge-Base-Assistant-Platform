"""知识库调试台（阶段4）。

跑一次完整检索（可选带 LLM 回答），产出「全过程快照」给前端分步展示；
支持把快照存成测试样例、标注 useful/useless、勾进评估集、导出成 rag_eval 的 cases。

- 检索本身走同步 RAG 管线（`space_search` / `search_entry`），自带 Session，
  异步路由经 `asyncio.to_thread` 调用（见 docs/sync-async-boundary.md）。
- LLM 回答走 `llm_service.async_chat`（异步）。
- 隔离：space 经 `access_control.user_space_ids` / `get_owned_space_async`，
  agent 经 `get_owned_agent_async`；越权 -> PermissionDenied / NotFound。
"""

import json
from typing import Any, Dict, List, Optional

from service.exceptions import InvalidInput, NotFound, PermissionDenied
from utils.logger_handler import get_logger

logger = get_logger("rag_debug")

_VERDICTS = {"useful", "useless"}


# --------------------------- 检索快照（同步入口） ---------------------------

def _normalize_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """统一 hit 结构：补齐 source（旧 Agent 私有库检索没有 source）。"""
    out = []
    for h in hits or []:
        src = h.get("source") or {
            "space_id": None,
            "space_name": "本助手私有库",
            "file_name": h.get("file_name", ""),
            "file_type": h.get("file_type", ""),
            "category": None,
            "version": None,
            "source_url": None,
        }
        out.append({
            "chunk_id": h.get("chunk_id"),
            "knowledge_id": h.get("knowledge_id"),
            "chunk_index": h.get("chunk_index"),
            "content": h.get("content", ""),
            "score": h.get("score"),
            "rerank_score": h.get("rerank_score"),
            "distance": h.get("distance"),
            "citation_index": h.get("citation_index"),
            "source": src,
        })
    return out


def run_retrieval(
    user_id: int,
    *,
    query: str,
    space_ids: Optional[List[int]] = None,
    agent_id: Optional[int] = None,
    top_k: int = 5,
    rerank: Optional[bool] = None,
    refuse_when_empty: bool = True,
) -> Dict[str, Any]:
    """跑一次检索，返回快照（不含 LLM 回答）。同步，自带 Session。

    - 传 space_ids -> 直接对这些空间联合检索（`space_search.search_spaces`）
    - 否则传 agent_id -> 按 Agent 实际绑定检索（`search_entry.search_for_agent`）
    - 归属校验：space_search / search_for_agent 内部各自做，越权抛 PermissionError
    """
    if not query or not query.strip():
        raise InvalidInput("检索关键词不能为空")
    space_ids = [int(s) for s in dict.fromkeys(space_ids or [])]
    if not space_ids and agent_id is None:
        raise InvalidInput("请指定 space_ids 或 agent_id")

    try:
        if space_ids:
            from service.rag.space_search import search_spaces

            res = search_spaces(
                user_id, space_ids, query,
                top_k=top_k, rerank=rerank, refuse_when_empty=refuse_when_empty,
            )
            mode = "spaces"
            used_space_ids = res.get("space_ids", space_ids)
        else:
            from service.rag.search_entry import search_for_agent

            res = search_for_agent(
                user_id, int(agent_id), query,
                top_k=top_k, rerank=rerank, refuse_when_empty=refuse_when_empty,
            )
            mode = res.get("mode", "agent")
            used_space_ids = []
    except PermissionError as e:
        raise PermissionDenied(str(e) or "无权访问该知识库空间")
    except ValueError as e:
        raise InvalidInput(str(e))

    hits = _normalize_hits(res.get("hits", []))
    context = res.get("context", "")
    return {
        "query": query,
        "mode": mode,
        "space_ids": used_space_ids,
        "agent_id": agent_id,
        "top_k": top_k,
        "rerank": bool(res.get("rerank")) if "rerank" in res else bool(rerank),
        "refused": bool(res.get("refused")),
        "hit_count": len(hits),
        "hits": hits,
        "context": context,
        "citations": res.get("citations", []),
        "stats": res.get("stats") or _retrieval_savings(hits, context),
        "answer": None,
        "faithfulness": None,
    }


def _retrieval_savings(hits: List[Dict[str, Any]], context: str) -> Dict[str, Any]:
    """调试台快照的「上下文压缩 / Token 节省」。同步，自带 Session。"""
    from models.init_db import SessionLocal
    from models.knowledge_chunk_dao import sum_content_chars_by_knowledge_ids
    from service.rag.rag_stats import build_savings, hit_knowledge_ids

    kids = hit_knowledge_ids(hits)
    src_chars = 0
    if kids:
        db = SessionLocal()
        try:
            src_chars = sum_content_chars_by_knowledge_ids(db, kids)
        finally:
            db.close()
    return build_savings(src_chars, context, len(hits))


# --------------------------- 可选 LLM 回答（异步） ---------------------------

async def attach_answer(
    db,
    user_id: int,
    trace: Dict[str, Any],
    model_name: str,
) -> Dict[str, Any]:
    """在快照上补一次 LLM 回答 + 启发式忠诚度评分。失败只记 error，不抛。"""
    from service.evaluation.rag_eval_service import evaluate_faithfulness
    from service.llm import llm_service

    context = trace.get("context") or ""
    if not context:
        trace["answer"] = "知识库中没有检索到相关资料。"
        trace["faithfulness"] = None
        return trace

    system_prompt = (
        "你是严谨的企业知识库问答助手。只依据下面的参考资料回答，"
        "每处引用了资料的内容在句末用【来源N】标注（N 为资料编号）。"
        "参考资料不足以回答时，直接说「知识库中没有相关内容」，不要编造。\n\n"
        f"=== 参考资料（按编号）===\n{context}\n=== 参考资料结束 ==="
    )
    try:
        answer = await llm_service.async_chat(
            db=db, user_id=user_id, model_name=model_name,
            system_prompt=system_prompt, history=[],
            user_message=trace["query"], temperature=0,
        )
    except Exception as e:  # noqa: BLE001 —— 调试台里 LLM 失败不该 500
        logger.warning(f"调试台生成回答失败: {e}")
        trace["answer_error"] = str(e)[:300]
        return trace

    trace["answer"] = answer
    trace["faithfulness"] = evaluate_faithfulness(
        answer, [h["content"] for h in trace.get("hits", [])]
    )
    trace["answer_model"] = model_name
    return trace


# --------------------------- 样例存取（异步） ---------------------------

def _sample_dict(s) -> Dict[str, Any]:
    try:
        result = json.loads(s.result_json) if s.result_json else None
    except (TypeError, ValueError):
        result = None
    try:
        space_ids = json.loads(s.space_ids_json) if s.space_ids_json else []
    except (TypeError, ValueError):
        space_ids = []
    return {
        "id": s.id,
        "query": s.query,
        "space_id": s.space_id,
        "space_ids": space_ids,
        "agent_id": s.agent_id,
        "top_k": s.top_k,
        "rerank_enabled": s.rerank_enabled,
        "verdict": s.verdict,
        "in_eval_set": bool(s.in_eval_set),
        "hit_count": len((result or {}).get("hits", [])) if result else 0,
        "has_answer": bool((result or {}).get("answer")) if result else False,
        "result": result,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


async def _assert_scope_owned(async_db, user_id: int, space_ids, agent_id):
    """存样例前校验：涉及的 space / agent 都属于当前用户。"""
    from service.access_control import get_owned_agent_async, user_space_ids_async

    if space_ids:
        allowed = await user_space_ids_async(async_db, user_id)
        bad = [int(s) for s in space_ids if int(s) not in allowed]
        if bad:
            raise PermissionDenied(f"包含无权访问的知识库空间：{bad}")
    if agent_id is not None and await get_owned_agent_async(async_db, user_id, int(agent_id)) is None:
        raise NotFound("智能体不存在或无权限")


def _trim_result_for_storage(result: Dict[str, Any]) -> Dict[str, Any]:
    """样例快照落 TEXT 列前收敛体积：截断 chunk 正文和 context，保留 id / 分数 / 引用。"""
    trimmed = dict(result or {})
    trimmed["hits"] = [
        {**h, "content": (h.get("content") or "")[:600]}
        for h in (result or {}).get("hits", []) or []
    ]
    if trimmed.get("context"):
        trimmed["context"] = trimmed["context"][:8000]
    if trimmed.get("answer"):
        trimmed["answer"] = trimmed["answer"][:4000]
    return trimmed


async def save_sample(async_db, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    from models import rag_debug_dao as dao

    query = (payload.get("query") or "").strip()
    if not query:
        raise InvalidInput("检索关键词不能为空")
    result = _trim_result_for_storage(payload.get("result") or {})
    space_ids = [int(s) for s in dict.fromkeys(payload.get("space_ids") or result.get("space_ids") or [])]
    agent_id = payload.get("agent_id") if payload.get("agent_id") is not None else result.get("agent_id")
    await _assert_scope_owned(async_db, user_id, space_ids, agent_id)

    verdict = payload.get("verdict")
    if verdict is not None and verdict not in _VERDICTS:
        raise InvalidInput("verdict 只能是 useful / useless")

    sample = await dao.create_sample_async(async_db, user_id, {
        "query": query,
        "space_id": space_ids[0] if len(space_ids) == 1 else None,
        "space_ids_json": json.dumps(space_ids) if space_ids else None,
        "agent_id": int(agent_id) if agent_id is not None else None,
        "top_k": payload.get("top_k") or result.get("top_k"),
        "rerank_enabled": 1 if (payload.get("rerank") or result.get("rerank")) else 0,
        "result_json": json.dumps(result, ensure_ascii=False),
        "verdict": verdict,
        "in_eval_set": 1 if payload.get("in_eval_set") else 0,
    })
    return _sample_dict(sample)


async def list_samples(async_db, user_id: int, *, space_id=None, agent_id=None, eval_only=False) -> Dict[str, Any]:
    from models import rag_debug_dao as dao
    from service.access_control import get_owned_space_async

    if space_id is not None and await get_owned_space_async(async_db, user_id, int(space_id)) is None:
        raise NotFound("知识库空间不存在或无权限")
    rows = await dao.list_samples_async(
        async_db, user_id, space_id=space_id, agent_id=agent_id, eval_only=eval_only,
    )
    return {"items": [_sample_dict(r) for r in rows], "total": len(rows)}


async def update_sample(async_db, user_id: int, sample_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    from models import rag_debug_dao as dao

    sample = await dao.get_owned_sample_async(async_db, user_id, sample_id)
    if not sample:
        raise NotFound("样例不存在或无权限")
    fields: Dict[str, Any] = {}
    if "verdict" in patch:
        v = patch["verdict"]
        if v is not None and v not in _VERDICTS:
            raise InvalidInput("verdict 只能是 useful / useless")
        fields["verdict"] = v
    if "in_eval_set" in patch:
        fields["in_eval_set"] = 1 if patch["in_eval_set"] else 0
    if not fields:
        return _sample_dict(sample)
    sample = await dao.update_sample_async(async_db, sample, fields)
    return _sample_dict(sample)


async def delete_sample(async_db, user_id: int, sample_id: int) -> Dict[str, Any]:
    from models import rag_debug_dao as dao

    sample = await dao.get_owned_sample_async(async_db, user_id, sample_id)
    if not sample:
        raise NotFound("样例不存在或无权限")
    await dao.delete_sample_async(async_db, sample)
    return {"message": "删除成功", "id": sample_id}


def _row_to_eval_case(query: str, verdict: Optional[str], result: Dict[str, Any]) -> Dict[str, Any]:
    """一条调试样例 -> rag_eval 的 case。useless 样例期望「查不到」，不带期望命中。"""
    hits = (result or {}).get("hits", []) or []
    expect = verdict != "useless"
    return {
        "question": query,
        "expected_knowledge_ids": sorted({h["knowledge_id"] for h in hits if h.get("knowledge_id")}) if expect else [],
        "expected_chunk_ids": sorted({h["chunk_id"] for h in hits if h.get("chunk_id")}) if expect else [],
        "expected_texts": [],
        "answer": (result or {}).get("answer"),
    }


async def export_eval_cases(async_db, user_id: int, *, space_id=None, agent_id=None) -> Dict[str, Any]:
    """把评估集里的样例导出成 rag_eval 的 cases（喂给 /evaluation/{agent_id}/rag）。

    期望命中 = 该样例检索到的 chunk / 文档；answer = 存快照时的 LLM 回答（若有）。
    """
    from models import rag_debug_dao as dao
    from service.access_control import get_owned_space_async

    if space_id is not None and await get_owned_space_async(async_db, user_id, int(space_id)) is None:
        raise NotFound("知识库空间不存在或无权限")
    rows = await dao.list_samples_async(
        async_db, user_id, space_id=space_id, agent_id=agent_id, eval_only=True,
    )
    cases = []
    for r in rows:
        try:
            result = json.loads(r.result_json) if r.result_json else {}
        except (TypeError, ValueError):
            result = {}
        cases.append(_row_to_eval_case(r.query, r.verdict, result))
    return {"cases": cases, "total": len(cases)}
