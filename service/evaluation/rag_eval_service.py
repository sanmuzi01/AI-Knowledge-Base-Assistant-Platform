import json
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from service.rag import rag_service
from service.llm import llm_service


DEFAULT_TEXT_MATCH_THRESHOLD = 0.35
DEFAULT_FAITHFULNESS_THRESHOLD = 0.25


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _latin_tokens(text: str) -> Set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", _normalize_text(text))
        if len(token) >= 2
    }


def _cjk_bigrams(text: str) -> Set[str]:
    chars = re.findall(r"[\u4e00-\u9fff]", text or "")
    return {"".join(chars[i:i + 2]) for i in range(len(chars) - 1)}


def _features(text: str) -> Set[str]:
    return _latin_tokens(text) | _cjk_bigrams(text)


def lexical_overlap(source: str, target: str) -> float:
    """Return how much of source is covered by target using mixed CN/EN tokens."""

    source_features = _features(source)
    if not source_features:
        return 0.0
    target_features = _features(target)
    if not target_features:
        return 0.0
    return len(source_features & target_features) / len(source_features)


def split_claims(answer: str) -> List[str]:
    """Split an answer into compact factual claims for heuristic faithfulness."""

    parts = re.split(r"[。！？!?；;\n]+", answer or "")
    return [part.strip(" ，,：:") for part in parts if len(part.strip()) >= 6]


def evaluate_faithfulness(
        answer: str,
        contexts: Sequence[str],
        threshold: float = DEFAULT_FAITHFULNESS_THRESHOLD,
) -> Dict[str, Any]:
    """Heuristic faithfulness: each answer claim should be supported by context.

    This is deliberately deterministic and dependency-free. It is suitable for
    regression checks and demos; a later LLM-as-judge evaluator can sit beside it.
    """

    claims = split_claims(answer)
    context_text = "\n".join(contexts or [])
    if not claims:
        return {
            "score": None,
            "supported_claims": 0,
            "claim_count": 0,
            "unsupported_claims": [],
            "details": [],
            "method": "lexical_overlap",
            "threshold": threshold,
        }

    details = []
    supported = 0
    unsupported = []
    for claim in claims:
        score = lexical_overlap(claim, context_text)
        is_supported = score >= threshold
        if is_supported:
            supported += 1
        else:
            unsupported.append(claim)
        details.append({
            "claim": claim,
            "support_score": round(score, 4),
            "supported": is_supported,
        })

    return {
        "score": round(supported / len(claims), 4),
        "supported_claims": supported,
        "claim_count": len(claims),
        "unsupported_claims": unsupported,
        "details": details,
        "method": "lexical_overlap",
        "threshold": threshold,
    }


def _retrieved_keys(results: Sequence[Dict[str, Any]]) -> Tuple[Set[int], Set[int]]:
    chunk_ids = {
        int(item["chunk_id"])
        for item in results
        if item.get("chunk_id") is not None
    }
    knowledge_ids = {
        int(item["knowledge_id"])
        for item in results
        if item.get("knowledge_id") is not None
    }
    return chunk_ids, knowledge_ids


def _match_expected_texts(
        expected_texts: Sequence[str],
        retrieved_texts: Sequence[str],
        threshold: float,
) -> List[Dict[str, Any]]:
    matches = []
    for text in expected_texts or []:
        best_score = 0.0
        best_index = None
        for index, retrieved in enumerate(retrieved_texts):
            score = lexical_overlap(text, retrieved)
            if score > best_score:
                best_score = score
                best_index = index
        matches.append({
            "expected_text": text,
            "matched": best_score >= threshold,
            "best_score": round(best_score, 4),
            "best_rank": best_index + 1 if best_index is not None else None,
        })
    return matches


def _result_relevance(
        results: Sequence[Dict[str, Any]],
        expected_chunk_ids: Set[int],
        expected_knowledge_ids: Set[int],
        expected_texts: Sequence[str],
        threshold: float,
) -> List[Dict[str, Any]]:
    relevance = []
    for index, item in enumerate(results):
        reasons = []
        chunk_id = item.get("chunk_id")
        knowledge_id = item.get("knowledge_id")
        content = item.get("content", "") or ""
        if chunk_id is not None and int(chunk_id) in expected_chunk_ids:
            reasons.append("chunk_id")
        if knowledge_id is not None and int(knowledge_id) in expected_knowledge_ids:
            reasons.append("knowledge_id")
        matched_texts = []
        for text in expected_texts or []:
            score = lexical_overlap(text, content)
            if score >= threshold:
                matched_texts.append({"expected_text": text, "score": round(score, 4)})
        if matched_texts:
            reasons.append("expected_text")
        relevance.append({
            "rank": index + 1,
            "relevant": bool(reasons),
            "reasons": reasons,
            "matched_texts": matched_texts,
        })
    return relevance


def _ranking_metrics(relevance: Sequence[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
    if not relevance:
        return {
            "precision_at_k": None,
            "mrr": None,
            "first_relevant_rank": None,
            "relevant_retrieved": 0,
        }
    cutoff = max(1, top_k)
    considered = list(relevance[:cutoff])
    relevant_ranks = [item["rank"] for item in considered if item["relevant"]]
    relevant_count = len(relevant_ranks)
    first_rank = relevant_ranks[0] if relevant_ranks else None
    return {
        "precision_at_k": round(relevant_count / len(considered), 4) if considered else None,
        "mrr": round(1 / first_rank, 4) if first_rank else 0.0,
        "first_relevant_rank": first_rank,
        "relevant_retrieved": relevant_count,
    }


def _safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    stripped = text.strip()
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    payload = match.group(0) if match else stripped
    try:
        return json.loads(payload)
    except Exception:
        return None


async def evaluate_faithfulness_with_llm(
        db,
        user_id: int,
        model_name: str,
        answer: str,
        contexts: Sequence[str],
) -> Dict[str, Any]:
    """Use an LLM judge to evaluate whether answer claims are supported."""

    claims = split_claims(answer)
    if not claims:
        return {
            "score": None,
            "supported_claims": 0,
            "claim_count": 0,
            "unsupported_claims": [],
            "details": [],
            "method": "llm_judge",
        }

    context_text = "\n\n".join(contexts or [])[:12000]
    user_message = (
        "请判断答案中的每条事实陈述是否被参考资料支持。\n"
        "只返回 JSON，不要返回 Markdown。\n\n"
        f"参考资料:\n{context_text}\n\n"
        f"答案:\n{answer}\n\n"
        "返回格式:\n"
        "{\"claims\":[{\"claim\":\"...\",\"supported\":true,\"reason\":\"...\"}]}"
    )
    raw = await llm_service.async_chat(
        db=db,
        user_id=user_id,
        model_name=model_name,
        system_prompt="你是严谨的 RAG 忠诚度评估器。只判断答案是否被给定参考资料支持。",
        history=[],
        user_message=user_message,
        temperature=0,
    )
    parsed = _safe_parse_json(raw)
    judged_claims = parsed.get("claims") if isinstance(parsed, dict) else None
    if not isinstance(judged_claims, list):
        return {
            "score": None,
            "supported_claims": 0,
            "claim_count": len(claims),
            "unsupported_claims": claims,
            "details": [],
            "method": "llm_judge",
            "error": "judge 返回不是可解析的 claims JSON",
            "raw": raw[:1000],
        }

    details = []
    supported = 0
    unsupported = []
    for item in judged_claims:
        claim = str(item.get("claim", "")).strip()
        is_supported = bool(item.get("supported"))
        if is_supported:
            supported += 1
        elif claim:
            unsupported.append(claim)
        details.append({
            "claim": claim,
            "supported": is_supported,
            "reason": str(item.get("reason", ""))[:300],
        })

    claim_count = len(details)
    return {
        "score": round(supported / claim_count, 4) if claim_count else None,
        "supported_claims": supported,
        "claim_count": claim_count,
        "unsupported_claims": unsupported,
        "details": details,
        "method": "llm_judge",
        "model_name": model_name,
    }


def evaluate_retrieval_case(
        *,
        question: str,
        results: Sequence[Dict[str, Any]],
        expected_chunk_ids: Optional[Sequence[int]] = None,
        expected_knowledge_ids: Optional[Sequence[int]] = None,
        expected_texts: Optional[Sequence[str]] = None,
        answer: Optional[str] = None,
        text_match_threshold: float = DEFAULT_TEXT_MATCH_THRESHOLD,
        faithfulness_threshold: float = DEFAULT_FAITHFULNESS_THRESHOLD,
) -> Dict[str, Any]:
    retrieved_chunk_ids, retrieved_knowledge_ids = _retrieved_keys(results)
    expected_chunk_set = {int(item) for item in expected_chunk_ids or []}
    expected_knowledge_set = {int(item) for item in expected_knowledge_ids or []}
    retrieved_texts = [item.get("content", "") or "" for item in results]
    text_matches = _match_expected_texts(expected_texts or [], retrieved_texts, text_match_threshold)
    relevance = _result_relevance(
        results,
        expected_chunk_set,
        expected_knowledge_set,
        expected_texts or [],
        text_match_threshold,
    )
    ranking = _ranking_metrics(relevance, len(results) or 1)

    expected_units = 0
    matched_units = 0
    if expected_chunk_set:
        expected_units += len(expected_chunk_set)
        matched_units += len(expected_chunk_set & retrieved_chunk_ids)
    if expected_knowledge_set:
        expected_units += len(expected_knowledge_set)
        matched_units += len(expected_knowledge_set & retrieved_knowledge_ids)
    if text_matches:
        expected_units += len(text_matches)
        matched_units += len([item for item in text_matches if item["matched"]])

    hit = matched_units > 0 if expected_units else None
    recall = matched_units / expected_units if expected_units else None
    faithfulness = (
        evaluate_faithfulness(answer, retrieved_texts, faithfulness_threshold)
        if answer is not None
        else None
    )

    return {
        "question": question,
        "hit": hit,
        "recall": round(recall, 4) if recall is not None else None,
        "matched_units": matched_units,
        "expected_units": expected_units,
        "retrieved_count": len(results),
        "ranking": ranking,
        "retrieved": [
            {
                "rank": index + 1,
                "chunk_id": item.get("chunk_id"),
                "knowledge_id": item.get("knowledge_id"),
                "chunk_index": item.get("chunk_index"),
                "score": item.get("score"),
                "file_name": item.get("file_name", ""),
                "content_preview": (item.get("content") or "")[:240],
            }
            for index, item in enumerate(results)
        ],
        "expected": {
            "chunk_ids": sorted(expected_chunk_set),
            "knowledge_ids": sorted(expected_knowledge_set),
            "text_matches": text_matches,
        },
        "relevance": relevance,
        "faithfulness": faithfulness,
    }


async def evaluate_rag_dataset(
        db,
        user_id: int,
        agent_id: int,
        cases: Sequence[Dict[str, Any]],
        top_k: int = 5,
        knowledge_id: int = None,
        text_match_threshold: float = DEFAULT_TEXT_MATCH_THRESHOLD,
        faithfulness_threshold: float = DEFAULT_FAITHFULNESS_THRESHOLD,
        faithfulness_judge_model: Optional[str] = None,
) -> Dict[str, Any]:
    case_reports = []
    for case in cases:
        question = (case.get("question") or "").strip()
        if not question:
            continue
        results = await rag_service.async_search(
            db=db,
            user_id=user_id,
            agent_id=agent_id,
            query=question,
            top_k=top_k,
            knowledge_id=case.get("knowledge_id", knowledge_id),
        )
        case_report = evaluate_retrieval_case(
            question=question,
            results=results,
            expected_chunk_ids=case.get("expected_chunk_ids"),
            expected_knowledge_ids=case.get("expected_knowledge_ids"),
            expected_texts=case.get("expected_texts"),
            answer=case.get("answer"),
            text_match_threshold=text_match_threshold,
            faithfulness_threshold=faithfulness_threshold,
        )
        if faithfulness_judge_model and case.get("answer") is not None:
            try:
                case_report["faithfulness"] = await evaluate_faithfulness_with_llm(
                    db=db,
                    user_id=user_id,
                    model_name=faithfulness_judge_model,
                    answer=case.get("answer") or "",
                    contexts=[item.get("content", "") or "" for item in results],
                )
            except Exception as exc:
                case_report["faithfulness_judge_error"] = str(exc)[:500]
        case_reports.append(case_report)

    evaluated_retrieval = [item for item in case_reports if item["hit"] is not None]
    evaluated_faithfulness = [
        item["faithfulness"]
        for item in case_reports
        if item.get("faithfulness") and item["faithfulness"]["score"] is not None
    ]
    hit_rate = (
        len([item for item in evaluated_retrieval if item["hit"]]) / len(evaluated_retrieval)
        if evaluated_retrieval else None
    )
    recall = (
        sum(item["recall"] for item in evaluated_retrieval if item["recall"] is not None)
        / len(evaluated_retrieval)
        if evaluated_retrieval else None
    )
    faithfulness_score = (
        sum(item["score"] for item in evaluated_faithfulness) / len(evaluated_faithfulness)
        if evaluated_faithfulness else None
    )
    precision_values = [
        item["ranking"]["precision_at_k"]
        for item in evaluated_retrieval
        if item.get("ranking") and item["ranking"]["precision_at_k"] is not None
    ]
    mrr_values = [
        item["ranking"]["mrr"]
        for item in evaluated_retrieval
        if item.get("ranking") and item["ranking"]["mrr"] is not None
    ]

    return {
        "case_count": len(case_reports),
        "evaluated_retrieval_count": len(evaluated_retrieval),
        "evaluated_faithfulness_count": len(evaluated_faithfulness),
        "metrics": {
            "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "precision_at_k": round(sum(precision_values) / len(precision_values), 4) if precision_values else None,
            "mrr": round(sum(mrr_values) / len(mrr_values), 4) if mrr_values else None,
            "faithfulness": round(faithfulness_score, 4) if faithfulness_score is not None else None,
        },
        "settings": {
            "top_k": top_k,
            "knowledge_id": knowledge_id,
            "text_match_threshold": text_match_threshold,
            "faithfulness_threshold": faithfulness_threshold,
            "faithfulness_judge_model": faithfulness_judge_model,
        },
        "cases": case_reports,
    }
