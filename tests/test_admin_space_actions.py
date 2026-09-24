"""管理员直接改知识库空间启停/归档状态（admin_update_space）的回归测试。

关键点：管理员不需要是这个空间的成员/所有者就能操作——这是它和普通的
update_space（service/knowledge_space/space_async_service.py）的核心区别。
"""
import unittest

from service.exceptions import InvalidInput, NotFound
from tests import _route_client as rc
from tests._async_helpers import run_async as _run

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AdminUpdateSpaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.init_db import SessionLocal, KnowledgeSpace

        cls.owner = rc.create_user("rt-adminspace-owner")
        cls.admin = rc.create_user("rt-adminspace-admin")
        db = SessionLocal()
        try:
            space = KnowledgeSpace(user_id=cls.owner["id"], name="rt-adminspace-target")
            db.add(space)
            db.commit()
            cls.space_id = space.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM kb_audit_log WHERE space_id=:s"), {"s": cls.space_id})
            db.execute(text("DELETE FROM knowledge_spaces WHERE id=:s"), {"s": cls.space_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def test_admin_not_a_member_can_disable_and_archive(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import admin_update_space

        async def _do():
            async with AsyncSessionLocal() as db:
                result = await admin_update_space(
                    db, self.admin["id"], self.space_id, {"is_enabled": False, "status": "archived"},
                )
                await db.commit()
                return result

        result = _run(_do())
        self.assertEqual(result["is_enabled"], False)
        self.assertEqual(result["status"], "archived")

        # 直接查库确认真的落库了
        from models.init_db import SessionLocal, KnowledgeSpace
        db = SessionLocal()
        try:
            space = db.query(KnowledgeSpace).filter(KnowledgeSpace.id == self.space_id).first()
            self.assertEqual(space.is_enabled, 0)
            self.assertEqual(space.status, "archived")
        finally:
            db.close()

    def test_records_audit_log_with_admin_as_actor(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import admin_update_space

        async def _do():
            async with AsyncSessionLocal() as db:
                await admin_update_space(db, self.admin["id"], self.space_id, {"is_enabled": True})
                await db.commit()

        _run(_do())

        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT user_id, action FROM kb_audit_log WHERE space_id=:s ORDER BY id DESC LIMIT 1"),
                {"s": self.space_id},
            ).first()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], self.admin["id"])
            self.assertEqual(row[1], "admin.space.update")
        finally:
            db.close()

    def test_nonexistent_space_raises_not_found(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import admin_update_space

        async def _do():
            async with AsyncSessionLocal() as db:
                await admin_update_space(db, self.admin["id"], 999999, {"is_enabled": True})

        with self.assertRaises(NotFound):
            _run(_do())

    def test_empty_patch_raises_invalid_input(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import admin_update_space

        async def _do():
            async with AsyncSessionLocal() as db:
                await admin_update_space(db, self.admin["id"], self.space_id, {})

        with self.assertRaises(InvalidInput):
            _run(_do())


if __name__ == "__main__":
    unittest.main()
