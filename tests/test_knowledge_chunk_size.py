"""每篇文档可选 chunk 大小：上传时传，落到 Knowledge.chunk_size，入库/重建按它切分。

- 纯逻辑：clamp_chunk_size / _effective_chunk_params
- 路由级：POST /knowledge/{agent_id}/upload 带 chunk_size 表单字段 → 建的 Knowledge 行带上该值
  （后台入库任务打桩成 no-op，不打真实 embedding / ChromaDB）
"""

import unittest
from unittest.mock import patch

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


class ChunkParamPureTest(unittest.TestCase):
    def test_clamp(self):
        from service.rag.rag_service import clamp_chunk_size, CHUNK_SIZE_MIN, CHUNK_SIZE_MAX
        self.assertEqual(clamp_chunk_size("50"), CHUNK_SIZE_MIN)
        self.assertEqual(clamp_chunk_size(999999), CHUNK_SIZE_MAX)
        self.assertEqual(clamp_chunk_size(800), 800)
        self.assertIsNone(clamp_chunk_size("abc"))
        self.assertIsNone(clamp_chunk_size(None))

    def test_effective_params(self):
        from service.rag.rag_service import _effective_chunk_params

        class Doc:
            def __init__(self, cs):
                self.chunk_size = cs

        self.assertEqual(_effective_chunk_params(Doc(None)), (500, 50))     # 默认不变
        self.assertEqual(_effective_chunk_params(Doc(800)), (800, 50))      # overlap 固定 50
        self.assertEqual(_effective_chunk_params(Doc(50)), (120, 30))       # 夹到下限，overlap = size // 4
        self.assertEqual(_effective_chunk_params(Doc(99999)), (2000, 50))   # 夹到上限


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class UploadChunkSizeRouteTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.user = rc.create_user("kcs")
        r = cls.client.post("/agent", json={"name": f"kcs-{cls.user['id']}"}, headers=cls.user["headers"])
        assert r.status_code == 200, r.text
        cls.agent_id = r.json()["agent_id"]

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM knowledge WHERE user_id=:u"), {"u": cls.user["id"]})
            db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": cls.agent_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def _latest_chunk_size(self):
        from models.init_db import SessionLocal, Knowledge
        db = SessionLocal()
        try:
            row = (db.query(Knowledge).filter(Knowledge.user_id == self.user["id"])
                   .order_by(Knowledge.id.desc()).first())
            return row.chunk_size if row else "NO_ROW"
        finally:
            db.close()

    def test_upload_persists_chunk_size(self):
        with patch("service.background_task_service.schedule_task", lambda *a, **k: None):
            r = self.client.post(
                f"/knowledge/{self.agent_id}/upload",
                headers=self.user["headers"],
                files={"file": ("a.txt", b"hello world " * 50, "text/plain")},
                data={"chunk_size": "800"},
            )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._latest_chunk_size(), 800)

    def test_upload_out_of_range_is_clamped(self):
        with patch("service.background_task_service.schedule_task", lambda *a, **k: None):
            r = self.client.post(
                f"/knowledge/{self.agent_id}/upload",
                headers=self.user["headers"],
                files={"file": ("b.txt", b"hello world " * 50, "text/plain")},
                data={"chunk_size": "40"},
            )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self._latest_chunk_size(), 120)

    def test_upload_without_chunk_size_stays_null(self):
        with patch("service.background_task_service.schedule_task", lambda *a, **k: None):
            r = self.client.post(
                f"/knowledge/{self.agent_id}/upload",
                headers=self.user["headers"],
                files={"file": ("c.txt", b"hello world " * 50, "text/plain")},
            )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(self._latest_chunk_size())


if __name__ == "__main__":
    unittest.main()
