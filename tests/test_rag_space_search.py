"""多空间联合检索：纯逻辑单测（候选数 / 拒答阈值 / context+citations 组装 / rerank）。

不依赖 DB：只测 `service/rag/space_search.py` 里可独立验证的编排逻辑。
端到端（权限校验、向量检索、越权 403）由 `tests/test_routes_isolation.py` 覆盖。
"""

import os
import unittest
from unittest.mock import patch

from service.rag import space_search as ss


def _hit(kid, score, *, space_id=1, space_name="制度库", file_name="a.pdf", version=None):
    return {
        "chunk_id": kid * 10,
        "content": f"内容{kid}",
        "score": score,
        "rerank_score": None,
        "knowledge_id": kid,
        "chunk_index": 0,
        "source": {
            "space_id": space_id, "space_name": space_name,
            "file_name": file_name, "file_type": "pdf",
            "category": None, "version": version, "source_url": None,
        },
    }


class CandidateCountTest(unittest.TestCase):
    def test_rerank_widens_candidate_pool(self):
        self.assertEqual(ss._candidate_count(5, rerank=False), 5)
        self.assertEqual(ss._candidate_count(3, rerank=False), 5)   # 下限 5
        self.assertEqual(ss._candidate_count(5, rerank=True), 10)
        self.assertEqual(ss._candidate_count(8, rerank=True), 16)


class MinScoreTest(unittest.TestCase):
    def test_default_and_env_override(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RAG_MIN_SCORE", None)
            self.assertEqual(ss._min_score(), 0.2)
        with patch.dict(os.environ, {"RAG_MIN_SCORE": "0.45"}):
            self.assertEqual(ss._min_score(), 0.45)
        with patch.dict(os.environ, {"RAG_MIN_SCORE": "abc"}):
            self.assertEqual(ss._min_score(), 0.2)


class RefuseTest(unittest.TestCase):
    def test_no_refuse_when_disabled(self):
        self.assertFalse(ss._should_refuse([], 0.2, refuse_when_empty=False))

    def test_refuse_on_empty(self):
        self.assertTrue(ss._should_refuse([], 0.2, refuse_when_empty=True))

    def test_refuse_when_top_score_below_threshold(self):
        self.assertTrue(ss._should_refuse([_hit(1, 0.1), _hit(2, 0.05)], 0.2, True))

    def test_keep_when_any_hit_clears_threshold(self):
        self.assertFalse(ss._should_refuse([_hit(1, 0.1), _hit(2, 0.9)], 0.2, True))


class AssembleTest(unittest.TestCase):
    def test_context_numbered_and_citations_deduped_by_doc(self):
        hits = [_hit(44, 0.9, version="v3"), _hit(44, 0.8), _hit(51, 0.7, space_id=2, space_name="产品库", file_name="b.pdf")]
        context, citations = ss._assemble(hits)

        self.assertIn("【来源1】制度库 / a.pdf（v3）", context)
        self.assertIn("【来源2】产品库 / b.pdf", context)
        # 同一文档的两个 chunk 共用来源编号 1
        self.assertEqual([h["citation_index"] for h in hits], [1, 1, 2])
        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0], {
            "index": 1, "knowledge_id": 44, "file_name": "a.pdf",
            "space_id": 1, "space_name": "制度库",
        })
        self.assertEqual(citations[1]["space_id"], 2)


class RerankTest(unittest.TestCase):
    def test_rerank_reorders_and_sets_scores(self):
        merged = [_hit(1, 0.4), _hit(2, 0.9), _hit(3, 0.5)]

        class FakeReranker:
            def rerank(self, query, docs, top_n):
                # 把最后一条顶到最前
                return [(2, 0.99), (0, 0.6), (1, 0.55)]

        class FakeRagService:
            @staticmethod
            def _get_rerank_client():
                return FakeReranker()

        out = ss._maybe_rerank("q", merged, top_k=3, use_rerank=True, rag_service=FakeRagService)
        self.assertEqual([h["knowledge_id"] for h in out], [3, 1, 2])
        self.assertEqual(out[0]["score"], 0.99)
        self.assertEqual(out[0]["rerank_score"], 0.99)

    def test_rerank_skipped_when_disabled_or_single(self):
        merged = [_hit(1, 0.4)]

        class Boom:
            @staticmethod
            def _get_rerank_client():
                raise AssertionError("不应被调用")

        self.assertIs(ss._maybe_rerank("q", merged, 3, use_rerank=False, rag_service=Boom), merged)
        self.assertIs(ss._maybe_rerank("q", merged, 3, use_rerank=True, rag_service=Boom), merged)


class EmptyResultTest(unittest.TestCase):
    def test_shape(self):
        r = ss._empty_result("q", [1, 2], 5, True, refused=True)
        self.assertEqual(r["hits"], [])
        self.assertEqual(r["citations"], [])
        self.assertEqual(r["context"], "")
        self.assertTrue(r["refused"])
        self.assertEqual(r["space_ids"], [1, 2])


if __name__ == "__main__":
    unittest.main()
