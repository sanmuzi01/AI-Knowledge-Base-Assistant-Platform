"""RAG「上下文压缩 / Token 节省」纯逻辑单测（service/rag/rag_stats.py）。"""

import unittest

from service.rag.rag_stats import build_savings, hit_knowledge_ids


class BuildSavingsTest(unittest.TestCase):
    def test_typical_compression(self):
        s = build_savings(source_doc_chars=10000, context="x" * 800, hit_count=4)
        self.assertEqual(s["source_doc_chars"], 10000)
        self.assertEqual(s["recall_chunks"], 4)
        self.assertEqual(s["context_chars"], 800)
        self.assertEqual(s["saved_ratio"], 0.92)
        self.assertEqual(s["est_tokens_full"], 5000)
        self.assertEqual(s["est_tokens_context"], 400)
        self.assertEqual(s["est_tokens_saved"], 4600)

    def test_zero_source_gives_zero_ratio(self):
        s = build_savings(0, "abc", 0)
        self.assertEqual(s["saved_ratio"], 0.0)
        self.assertEqual(s["est_tokens_saved"], 0)

    def test_context_longer_than_source_never_negative(self):
        s = build_savings(100, "x" * 500, 1)
        self.assertEqual(s["saved_ratio"], 0.0)
        self.assertEqual(s["est_tokens_saved"], 0)

    def test_none_inputs_safe(self):
        s = build_savings(None, None, None)
        self.assertEqual(s["source_doc_chars"], 0)
        self.assertEqual(s["context_chars"], 0)
        self.assertEqual(s["recall_chunks"], 0)


class HitKnowledgeIdsTest(unittest.TestCase):
    def test_dedupes_and_keeps_order_and_drops_none(self):
        hits = [{"knowledge_id": 3}, {"knowledge_id": 3}, {"knowledge_id": 5}, {}, {"knowledge_id": None}]
        self.assertEqual(hit_knowledge_ids(hits), [3, 5])

    def test_empty(self):
        self.assertEqual(hit_knowledge_ids([]), [])
        self.assertEqual(hit_knowledge_ids(None), [])


if __name__ == "__main__":
    unittest.main()
