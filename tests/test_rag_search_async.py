"""彻底 async 的 RAG 检索链路（`search_entry.*_async` / `rag_service.search_async` /
`space_search.search_spaces_async`）—— 与同步版逐条对齐 + 归属校验。

向量化客户端、ChromaDB `search_similar`、rerank 全部 mock，只验证编排 / DAO / 事务。
需要本地 MySQL（建 fixture）；连不上则整体 skip。
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()

_VEC = [0.11, 0.22, 0.33]


def _arun(coro):
    """跑一个协程并在同一 loop 里 dispose 掉 async_engine，
    避免 asyncio.run() 反复建/拆 loop 时 asyncmy 连接池的 teardown 噪音。"""
    from models.async_db import async_engine

    async def _wrap():
        try:
            return await coro
        finally:
            await async_engine.dispose()

    return asyncio.run(_wrap())


class _FakeEmb:
    model_name = "fake-emb"

    def embed_query(self, q):
        return list(_VEC)

    async def aembed_query(self, q):
        return list(_VEC)

    def get_dimension(self):
        return len(_VEC)


def _patch_embedding():
    return (
        patch("service.rag.embedding_service._get_client", return_value=_FakeEmb()),
        patch("service.rag.embedding_service._get_client_async",
              new=AsyncMock(return_value=_FakeEmb())),
    )


# ----------------------------------------------------------------- 纯逻辑：rerank


class MaybeRerankAsyncParityTest(unittest.IsolatedAsyncioTestCase):
    """`_maybe_rerank_async` 与同步 `_maybe_rerank` 结果一致。"""

    def _fixture(self):
        from service.rag import space_search as ss

        def _hit(kid, score):
            return {"knowledge_id": kid, "content": f"内容{kid}", "score": score,
                    "rerank_score": None, "source": {}}

        merged = [_hit(1, 0.4), _hit(2, 0.9), _hit(3, 0.5)]

        class FakeReranker:
            def rerank(self, query, docs, top_n):
                return [(2, 0.99), (0, 0.6), (1, 0.55)]

        class FakeRag:
            @staticmethod
            def _get_rerank_client():
                return FakeReranker()

        return ss, merged, FakeRag

    async def test_reorders_like_sync(self):
        ss, merged, FakeRag = self._fixture()
        sync_out = ss._maybe_rerank("q", [dict(m) for m in merged], 3, True, FakeRag)
        async_out = await ss._maybe_rerank_async("q", [dict(m) for m in merged], 3, True, FakeRag)
        self.assertEqual([h["knowledge_id"] for h in async_out],
                         [h["knowledge_id"] for h in sync_out])
        self.assertEqual([h["score"] for h in async_out], [h["score"] for h in sync_out])
        self.assertEqual(async_out[0]["rerank_score"], 0.99)

    async def test_skipped_when_disabled_or_single(self):
        ss, merged, _ = self._fixture()

        class Boom:
            @staticmethod
            def _get_rerank_client():
                raise AssertionError("不应被调用")

        one = [merged[0]]
        self.assertIs(await ss._maybe_rerank_async("q", one, 3, False, Boom), one)
        self.assertIs(await ss._maybe_rerank_async("q", one, 3, True, Boom), one)


# ----------------------------------------------------------------- DB 落地：agent 私有库


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AgentPrivateSearchParityTest(unittest.TestCase):
    """未绑定知识库空间 → `search_scoped` / `search_for_agent` 的同步与 async 版结果逐条一致。"""

    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("rsa")
        cls.other = rc.create_user("rsa_other")
        cls._build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls._wipe()
        rc.cleanup()

    @classmethod
    def _build_fixture(cls):
        from models.init_db import SessionLocal
        from models.agent_dao import create_agent
        from models.knowledge_dao import create_knowledge
        from models.knowledge_chunk_dao import create_chunks_batch
        db = SessionLocal()
        try:
            agent = create_agent(db, name="rsa-agent", user_id=cls.user["id"],
                                 model_name="glm-4", rag_enabled=1)
            db.flush()
            cls.agent_id = agent.id
            kn = create_knowledge(db, user_id=cls.user["id"], agent_id=agent.id,
                                  file_name="制度.pdf", file_path="/x/制度.pdf",
                                  file_type="pdf", file_size=100)
            db.flush()
            cls.knowledge_id = kn.id
            create_chunks_batch(db, [
                {"knowledge_id": kn.id, "chunk_index": 0, "content": "报销上限 2000 元。",
                 "vector_id": "rsa_v1", "token_count": 10},
                {"knowledge_id": kn.id, "chunk_index": 1, "content": "差旅需提前申请。",
                 "vector_id": "rsa_v2", "token_count": 8},
            ])
            db.commit()
        finally:
            db.close()

    @classmethod
    def _wipe(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM knowledge_chunk WHERE knowledge_id=:k"), {"k": cls.knowledge_id})
            db.execute(text("DELETE FROM knowledge WHERE id=:k"), {"k": cls.knowledge_id})
            db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": cls.agent_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _fake_similar(self, *args, **kwargs):
        return [
            {"id": "rsa_v1", "distance": 0.10},
            {"id": "rsa_v2", "distance": 0.40},
        ]

    def test_scoped_sync_vs_async_identical(self):
        from service.rag import search_entry
        p_emb, p_emb_async = _patch_embedding()
        with p_emb, p_emb_async, \
             patch("service.rag.rag_service.search_similar", side_effect=self._fake_similar):
            sync_hits = search_entry.search_scoped(self.user["id"], self.agent_id, "报销", top_k=5)
            async_hits = _arun(
                search_entry.search_scoped_async(self.user["id"], self.agent_id, "报销", top_k=5)
            )

        self.assertEqual(len(async_hits), 2)
        keys = ("content", "knowledge_id", "chunk_index", "score", "distance", "file_name", "file_type")
        self.assertEqual([{k: h[k] for k in keys} for h in async_hits],
                         [{k: h[k] for k in keys} for h in sync_hits])
        self.assertEqual(async_hits[0]["content"], "报销上限 2000 元。")
        self.assertEqual(async_hits[0]["file_name"], "制度.pdf")

    def test_for_agent_sync_vs_async_identical(self):
        from service.rag import search_entry
        p_emb, p_emb_async = _patch_embedding()
        with p_emb, p_emb_async, \
             patch("service.rag.rag_service.search_similar", side_effect=self._fake_similar):
            sync_res = search_entry.search_for_agent(self.user["id"], self.agent_id, "报销")
            async_res = _arun(
                search_entry.search_for_agent_async(self.user["id"], self.agent_id, "报销")
            )

        self.assertEqual(async_res["mode"], "agent")
        self.assertEqual(async_res["mode"], sync_res["mode"])
        self.assertEqual(async_res["context"], sync_res["context"])
        self.assertIn("报销上限 2000", async_res["context"])
        self.assertIn("【来源1】", async_res["context"])   # 私有库也统一用 【来源N】
        self.assertEqual(async_res["citations"], sync_res["citations"])
        self.assertEqual(async_res["citations"][0]["index"], 1)
        self.assertIn("报销上限 2000", async_res["citations"][0]["snippet"])
        self.assertIsNone(async_res["citations"][0]["space_id"])
        self.assertEqual(len(async_res["hits"]), len(sync_res["hits"]))

        # 上下文压缩统计（async 版特有，聊天/调试台展示用）
        stats = async_res["stats"]
        self.assertEqual(stats["recall_chunks"], 2)
        self.assertEqual(stats["context_chars"], len(async_res["context"]))
        self.assertGreater(stats["source_doc_chars"], 0)
        self.assertGreaterEqual(stats["saved_ratio"], 0.0)
        self.assertLessEqual(stats["saved_ratio"], 1.0)

    def test_disabled_doc_raises_valueerror(self):
        from models.init_db import SessionLocal
        from sqlalchemy import text
        from service.rag import search_entry

        db = SessionLocal()
        try:
            db.execute(text("UPDATE knowledge SET is_enabled=0 WHERE id=:k"), {"k": self.knowledge_id})
            db.commit()
        finally:
            db.close()
        try:
            with self.assertRaises(ValueError):
                _arun(search_entry.search_scoped_async(
                    self.user["id"], self.agent_id, "报销", knowledge_id=self.knowledge_id))
        finally:
            db = SessionLocal()
            try:
                db.execute(text("UPDATE knowledge SET is_enabled=1 WHERE id=:k"), {"k": self.knowledge_id})
                db.commit()
            finally:
                db.close()

    def test_cross_user_raises_permissionerror(self):
        from service.rag import search_entry
        with self.assertRaises(PermissionError):
            _arun(search_entry.search_for_agent_async(
                self.other["id"], self.agent_id, "报销"))

    def test_empty_query_raises_valueerror(self):
        from service.rag import search_entry
        with self.assertRaises(ValueError):
            _arun(search_entry.search_scoped_async(self.user["id"], self.agent_id, "  "))


# ----------------------------------------------------------------- DB 落地：多空间联合


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class SpaceSearchParityTest(unittest.TestCase):
    """绑定知识库空间 → `search_spaces` 的同步与 async 版结果一致（含 citations / 【来源N】）。"""

    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("rss")
        cls._build_fixture()

    @classmethod
    def tearDownClass(cls):
        cls._wipe()
        rc.cleanup()

    @classmethod
    def _build_fixture(cls):
        from models.init_db import SessionLocal
        from models.agent_dao import create_agent
        from models.knowledge_dao import create_knowledge
        from models.knowledge_chunk_dao import create_chunks_batch
        from models.knowledge_space_dao import create_space
        from models.agent_knowledge_space_dao import set_agent_spaces
        db = SessionLocal()
        try:
            space = create_space(db, cls.user["id"], {"name": "rss-制度库"})
            cls.space_id = space.id
            agent = create_agent(db, name="rss-agent", user_id=cls.user["id"],
                                 model_name="glm-4", rag_enabled=1)
            db.flush()
            cls.agent_id = agent.id
            set_agent_spaces(db, agent.id, [space.id], commit=False)
            kn = create_knowledge(db, user_id=cls.user["id"], agent_id=agent.id,
                                  file_name="报销规范.pdf", file_path="/x/报销规范.pdf",
                                  file_type="pdf", file_size=100, space_id=space.id)
            db.flush()
            cls.knowledge_id = kn.id
            create_chunks_batch(db, [
                {"knowledge_id": kn.id, "chunk_index": 0, "content": "机票按实报销，餐补每日 100。",
                 "vector_id": "rss_v1", "token_count": 12},
            ])
            db.commit()
        finally:
            db.close()

    @classmethod
    def _wipe(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM knowledge_chunk WHERE knowledge_id=:k"), {"k": cls.knowledge_id})
            db.execute(text("DELETE FROM knowledge WHERE id=:k"), {"k": cls.knowledge_id})
            db.execute(text("DELETE FROM agent_knowledge_space WHERE agent_id=:a"), {"a": cls.agent_id})
            db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": cls.agent_id})
            db.execute(text("DELETE FROM knowledge_space WHERE id=:s"), {"s": cls.space_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _fake_similar(self, key, query_vector, top_k=5, where=None):
        from service.rag.vector_store_service import space_collection_key
        if key == space_collection_key(self.space_id):
            return [{"id": "rss_v1", "distance": 0.12}]
        return []

    def test_spaces_sync_vs_async_identical(self):
        from service.rag import search_entry
        p_emb, p_emb_async = _patch_embedding()
        with p_emb, p_emb_async, \
             patch("service.rag.vector_store_service.search_similar", side_effect=self._fake_similar):
            sync_res = search_entry.search_for_agent(self.user["id"], self.agent_id, "报销")
            async_res = _arun(
                search_entry.search_for_agent_async(self.user["id"], self.agent_id, "报销")
            )

        self.assertEqual(async_res["mode"], "spaces")
        self.assertEqual(async_res["mode"], sync_res["mode"])
        self.assertEqual(async_res["context"], sync_res["context"])
        self.assertIn("【来源1】", async_res["context"])
        self.assertIn("机票按实报销", async_res["context"])
        self.assertEqual(async_res["citations"], sync_res["citations"])
        self.assertEqual(async_res["citations"][0]["knowledge_id"], self.knowledge_id)
        self.assertFalse(async_res["refused"])

    def test_cross_user_space_denied(self):
        from service.rag.space_search import search_spaces_async
        other = rc.create_user("rss_evil")
        try:
            with self.assertRaises(PermissionError):
                _arun(search_spaces_async(other["id"], [self.space_id], "报销"))
        finally:
            pass


if __name__ == "__main__":
    unittest.main()
