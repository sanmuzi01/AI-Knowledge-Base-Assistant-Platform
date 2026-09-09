"""知识库调试台：纯逻辑单测（hit 归一化 / 样例序列化 / 导出评估用例 / 入参校验）。

不依赖 DB。端到端（跑检索、存样例、越权 403/404）由路由级测试覆盖。
"""

import json
import unittest
from types import SimpleNamespace

from service.exceptions import InvalidInput
from service.rag import debug_service as ds


class NormalizeHitsTest(unittest.TestCase):
    def test_space_hit_keeps_source(self):
        h = {
            "chunk_id": 9, "knowledge_id": 4, "chunk_index": 1, "content": "x",
            "score": 0.8, "rerank_score": 0.9, "distance": 0.2, "citation_index": 1,
            "source": {"space_id": 3, "space_name": "制度库", "file_name": "a.pdf",
                       "file_type": "pdf", "category": "制度", "version": "v2", "source_url": None},
        }
        out = ds._normalize_hits([h])[0]
        self.assertEqual(out["source"]["space_name"], "制度库")
        self.assertEqual(out["rerank_score"], 0.9)
        self.assertEqual(out["citation_index"], 1)

    def test_agent_hit_gets_synthetic_source(self):
        h = {"chunk_id": 1, "knowledge_id": 2, "content": "y", "score": 0.5,
             "file_name": "note.txt", "file_type": "txt"}
        out = ds._normalize_hits([h])[0]
        self.assertEqual(out["source"]["space_id"], None)
        self.assertEqual(out["source"]["file_name"], "note.txt")
        self.assertEqual(out["source"]["space_name"], "本助手私有库")
        self.assertIsNone(out["rerank_score"])


class SampleDictTest(unittest.TestCase):
    def test_shape_and_json_parse(self):
        s = SimpleNamespace(
            id=7, query="年假几天", space_id=3, space_ids_json=json.dumps([3]),
            agent_id=None, top_k=5, rerank_enabled=1, verdict="useful", in_eval_set=1,
            result_json=json.dumps({"hits": [{"knowledge_id": 4}], "answer": "10天"}),
            created_at=None, updated_at=None,
        )
        d = ds._sample_dict(s)
        self.assertEqual(d["id"], 7)
        self.assertEqual(d["space_ids"], [3])
        self.assertTrue(d["in_eval_set"])
        self.assertEqual(d["hit_count"], 1)
        self.assertTrue(d["has_answer"])

    def test_bad_json_degrades(self):
        s = SimpleNamespace(
            id=1, query="q", space_id=None, space_ids_json="{bad", agent_id=1,
            top_k=None, rerank_enabled=0, verdict=None, in_eval_set=0,
            result_json="not json", created_at=None, updated_at=None,
        )
        d = ds._sample_dict(s)
        self.assertEqual(d["space_ids"], [])
        self.assertIsNone(d["result"])
        self.assertEqual(d["hit_count"], 0)


class EvalCaseTest(unittest.TestCase):
    def test_useful_sample_carries_expected_hits(self):
        result = {"hits": [{"knowledge_id": 4, "chunk_id": 40}, {"knowledge_id": 4, "chunk_id": 41},
                           {"knowledge_id": 7, "chunk_id": 70}], "answer": "十天"}
        case = ds._row_to_eval_case("年假", "useful", result)
        self.assertEqual(case["question"], "年假")
        self.assertEqual(case["expected_knowledge_ids"], [4, 7])
        self.assertEqual(case["expected_chunk_ids"], [40, 41, 70])
        self.assertEqual(case["answer"], "十天")

    def test_useless_sample_expects_no_hits(self):
        result = {"hits": [{"knowledge_id": 4, "chunk_id": 40}]}
        case = ds._row_to_eval_case("无关问题", "useless", result)
        self.assertEqual(case["expected_knowledge_ids"], [])
        self.assertEqual(case["expected_chunk_ids"], [])


class TrimResultTest(unittest.TestCase):
    def test_truncates_content_context_answer_keeps_ids(self):
        result = {
            "space_ids": [3], "agent_id": None,
            "hits": [{"knowledge_id": 4, "chunk_id": 40, "content": "长" * 5000}],
            "context": "上" * 20000,
            "answer": "答" * 9000,
        }
        out = ds._trim_result_for_storage(result)
        self.assertEqual(len(out["hits"][0]["content"]), 600)
        self.assertEqual(out["hits"][0]["knowledge_id"], 4)
        self.assertEqual(len(out["context"]), 8000)
        self.assertEqual(len(out["answer"]), 4000)
        self.assertEqual(out["space_ids"], [3])


class RunRetrievalGuardTest(unittest.TestCase):
    def test_empty_query_rejected(self):
        with self.assertRaises(InvalidInput):
            ds.run_retrieval(1, query="  ")

    def test_missing_scope_rejected(self):
        with self.assertRaises(InvalidInput):
            ds.run_retrieval(1, query="有内容但没指定范围")


if __name__ == "__main__":
    unittest.main()
