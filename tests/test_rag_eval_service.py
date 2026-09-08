import unittest

from service.evaluation.rag_eval_service import (
    evaluate_faithfulness,
    evaluate_retrieval_case,
    lexical_overlap,
    split_claims,
)


class RagEvalServiceTest(unittest.TestCase):
    def test_lexical_overlap_supports_chinese_bigrams(self):
        self.assertGreaterEqual(
            lexical_overlap("长期记忆按用户隔离", "系统支持长期记忆，并且按用户和 Agent 隔离。"),
            0.5,
        )

    def test_retrieval_case_calculates_hit_and_recall(self):
        report = evaluate_retrieval_case(
            question="RAG 怎么工作？",
            results=[
                {"chunk_id": 1, "knowledge_id": 10, "content": "上传文档后切片并写入向量库"},
                {"chunk_id": 2, "knowledge_id": 11, "content": "无关片段"},
            ],
            expected_chunk_ids=[1, 3],
            expected_knowledge_ids=[10],
        )

        self.assertTrue(report["hit"])
        self.assertEqual(report["matched_units"], 2)
        self.assertEqual(report["expected_units"], 3)
        self.assertAlmostEqual(report["recall"], 0.6667)
        self.assertEqual(report["ranking"]["precision_at_k"], 0.5)
        self.assertEqual(report["ranking"]["mrr"], 1.0)

    def test_expected_texts_can_match_without_chunk_id_labels(self):
        report = evaluate_retrieval_case(
            question="后台任务怎么处理？",
            results=[
                {"chunk_id": 8, "knowledge_id": 2, "content": "Worker 领取 queued 任务，执行失败后支持重试。"},
            ],
            expected_texts=["Worker 支持任务领取和失败重试"],
        )

        self.assertTrue(report["hit"])
        self.assertEqual(report["recall"], 1.0)

    def test_faithfulness_marks_unsupported_claims(self):
        report = evaluate_faithfulness(
            "系统使用 Redis 做限流。系统已经接入 Kubernetes 自动扩容。",
            ["Redis 用于缓存、验证码、限流、并发控制。"],
        )

        self.assertEqual(report["claim_count"], 2)
        self.assertEqual(report["supported_claims"], 1)
        self.assertEqual(report["score"], 0.5)
        self.assertIn("Kubernetes", report["unsupported_claims"][0])

    def test_split_claims_ignores_tiny_fragments(self):
        self.assertEqual(split_claims("好的。Redis 用于限流和缓存！"), ["Redis 用于限流和缓存"])

    def test_ranking_metrics_reflect_relevant_result_position(self):
        report = evaluate_retrieval_case(
            question="怎么做限流？",
            results=[
                {"chunk_id": 1, "knowledge_id": 1, "content": "无关内容"},
                {"chunk_id": 2, "knowledge_id": 1, "content": "Redis 可以用于接口限流"},
                {"chunk_id": 3, "knowledge_id": 1, "content": "另一个无关内容"},
            ],
            expected_texts=["Redis 用于接口限流"],
        )

        self.assertTrue(report["hit"])
        self.assertEqual(report["ranking"]["first_relevant_rank"], 2)
        self.assertEqual(report["ranking"]["mrr"], 0.5)
        self.assertAlmostEqual(report["ranking"]["precision_at_k"], 0.3333)


if __name__ == "__main__":
    unittest.main()
