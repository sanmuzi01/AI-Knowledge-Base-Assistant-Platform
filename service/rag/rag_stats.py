"""RAG「上下文压缩 / Token 节省」统计。

产品口径：一次检索把「命中文档的全文」压成「喂给模型的上下文」，
展示压了多少。纯计算 + 一个「命中文档总字数」的 DB 汇总。

token 估算沿用项目里既有的粗口径：中文每 2 字符 ≈ 1 token（见 rag_service 切块处）。
"""

from typing import Any, Dict, Iterable

_CHARS_PER_TOKEN = 2


def _est_tokens(chars: int) -> int:
    return max(0, int(chars) // _CHARS_PER_TOKEN)


def build_savings(source_doc_chars: int, context: str, hit_count: int) -> Dict[str, Any]:
    """给定「命中文档总字数」+ 最终上下文 + 命中片段数，算出展示用的一组数。

    - source_doc_chars: 本次命中涉及的源文档切块内容总字数（≈ 原文字数）
    - context: 实际拼进 system prompt 的知识库上下文
    - saved_ratio: 0~1，= 1 - 上下文字数 / 源文档字数（源文档为 0 或上下文反而更长时给 0）
    """
    ctx_chars = len((context or ""))
    src = max(0, int(source_doc_chars or 0))
    saved_ratio = 0.0
    if src > 0 and ctx_chars < src:
        saved_ratio = round(1 - ctx_chars / src, 4)
    return {
        "source_doc_chars": src,
        "recall_chunks": int(hit_count or 0),
        "context_chars": ctx_chars,
        "saved_ratio": saved_ratio,
        "est_tokens_full": _est_tokens(src),
        "est_tokens_context": _est_tokens(ctx_chars),
        "est_tokens_saved": max(0, _est_tokens(src) - _est_tokens(ctx_chars)),
    }


def hit_knowledge_ids(hits: Iterable[Dict[str, Any]]) -> list:
    """从 hits 里取去重后的 knowledge_id（保持出现顺序）。"""
    seen = []
    for h in hits or []:
        kid = h.get("knowledge_id")
        if kid is not None and kid not in seen:
            seen.append(kid)
    return seen
