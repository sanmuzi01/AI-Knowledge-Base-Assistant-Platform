"""关键词补充召回的回归测试。

- `_extract_keyword_tokens`：纯逻辑，测哪些串会被当成"编号/型号"抓出来。
- `search_chunks_by_keyword` / `_async`：真实 MySQL，验证关键词命中、排除已有 chunk_id、
  只覆盖 Knowledge.space_id 有值的文档这几条边界。
"""
import unittest

from service.rag.space_search import _extract_keyword_tokens
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


class ExtractKeywordTokensTest(unittest.TestCase):
    def test_extracts_alnum_codes(self):
        tokens = _extract_keyword_tokens("请问型号ABC-100的价格是多少")
        self.assertIn("ABC-100", tokens)

    def test_pure_chinese_query_has_no_tokens(self):
        self.assertEqual(_extract_keyword_tokens("回收站文件能保留多久"), [])

    def test_dedupes_and_caps_at_limit(self):
        query = " ".join([f"CODE-{i}" for i in range(10)] + ["CODE-1"])
        tokens = _extract_keyword_tokens(query, limit=5)
        self.assertEqual(len(tokens), 5)
        self.assertEqual(len(tokens), len(set(tokens)))

    def test_short_alnum_not_treated_as_code(self):
        # 长度阈值：纯两位英文数字混排太容易误伤普通词，不当作关键词
        self.assertEqual(_extract_keyword_tokens("A1 是什么"), [])


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class SearchChunksByKeywordDbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.init_db import SessionLocal, Knowledge, KnowledgeChunk, KnowledgeSpace

        cls.user = rc.create_user("kwsearch")
        db = SessionLocal()
        try:
            space = KnowledgeSpace(user_id=cls.user["id"], name="kw-space")
            db.add(space)
            db.flush()
            cls.space_id = space.id

            doc = Knowledge(
                user_id=cls.user["id"], space_id=cls.space_id,
                file_name="spec.pdf", file_path="/tmp/spec.pdf", file_type="pdf",
                status="done", is_enabled=1,
            )
            db.add(doc)
            db.flush()
            cls.knowledge_id = doc.id

            chunk_hit = KnowledgeChunk(
                knowledge_id=cls.knowledge_id, chunk_index=0,
                content="型号 ABC-100 的价格是 39 元/月", vector_id="kw-test-v0",
            )
            chunk_excluded = KnowledgeChunk(
                knowledge_id=cls.knowledge_id, chunk_index=1,
                content="型号 ABC-100 还支持团队版", vector_id="kw-test-v1",
            )
            chunk_miss = KnowledgeChunk(
                knowledge_id=cls.knowledge_id, chunk_index=2,
                content="这段内容完全不相关", vector_id="kw-test-v2",
            )
            db.add_all([chunk_hit, chunk_excluded, chunk_miss])
            db.commit()
            cls.chunk_hit_id = chunk_hit.id
            cls.chunk_excluded_id = chunk_excluded.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM knowledge_chunk WHERE knowledge_id=:k"), {"k": cls.knowledge_id})
            db.execute(text("DELETE FROM knowledge WHERE id=:k"), {"k": cls.knowledge_id})
            db.execute(text("DELETE FROM knowledge_spaces WHERE id=:s"), {"s": cls.space_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def test_finds_keyword_hit_excludes_given_id(self):
        from models.init_db import SessionLocal
        from models.knowledge_chunk_dao import search_chunks_by_keyword

        db = SessionLocal()
        try:
            results = search_chunks_by_keyword(
                db, [self.space_id], ["ABC-100"],
                exclude_chunk_ids={self.chunk_excluded_id}, limit=10,
            )
        finally:
            db.close()

        ids = {c.id for c in results}
        self.assertIn(self.chunk_hit_id, ids)
        self.assertNotIn(self.chunk_excluded_id, ids, "已排除的 chunk 不应该出现在结果里")

    def test_no_tokens_or_no_spaces_returns_empty(self):
        from models.init_db import SessionLocal
        from models.knowledge_chunk_dao import search_chunks_by_keyword

        db = SessionLocal()
        try:
            self.assertEqual(search_chunks_by_keyword(db, [self.space_id], [], limit=10), [])
            self.assertEqual(search_chunks_by_keyword(db, [], ["ABC-100"], limit=10), [])
        finally:
            db.close()

    def test_async_variant_matches_sync(self):
        import asyncio
        from models.async_db import AsyncSessionLocal
        from models.knowledge_async_dao import search_chunks_by_keyword_async

        async def _run():
            async with AsyncSessionLocal() as db:
                return await search_chunks_by_keyword_async(
                    db, [self.space_id], ["ABC-100"],
                    exclude_chunk_ids={self.chunk_excluded_id}, limit=10,
                )

        results = asyncio.run(_run())
        ids = {c.id for c in results}
        self.assertIn(self.chunk_hit_id, ids)
        self.assertNotIn(self.chunk_excluded_id, ids)


if __name__ == "__main__":
    unittest.main()
