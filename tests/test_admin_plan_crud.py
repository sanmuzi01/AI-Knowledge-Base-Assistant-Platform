"""管理员套餐管理（service/admin_async_service.py 的 *_plan 系列函数）回归测试。"""
import unittest

from service.exceptions import Conflict, InvalidInput, NotFound
from tests import _route_client as rc
from tests._async_helpers import run_async as _run

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AdminPlanCrudTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = rc.create_user("rt-planadmin")
        cls.target = rc.create_user("rt-plantarget")

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM kb_audit_log WHERE user_id=:u"), {"u": cls.admin["id"]})
            db.execute(text("DELETE FROM user_subscription WHERE user_id=:u"), {"u": cls.target["id"]})
            db.execute(text("DELETE FROM plan WHERE name LIKE 'rt-plan-%'"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def test_create_then_update_then_delete_plan(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import create_plan, delete_plan, update_plan

        async def _create():
            async with AsyncSessionLocal() as db:
                return await create_plan(db, self.admin["id"], {
                    "name": "rt-plan-pro", "display_name": "专业版", "monthly_token_limit": 500000,
                })

        created = _run(_create())
        self.assertEqual(created["monthly_token_limit"], 500000)
        self.assertFalse(created["is_default"])
        plan_id = created["id"]

        async def _update():
            async with AsyncSessionLocal() as db:
                return await update_plan(db, self.admin["id"], plan_id, {"monthly_token_limit": 800000})

        updated = _run(_update())
        self.assertEqual(updated["monthly_token_limit"], 800000)

        async def _delete():
            async with AsyncSessionLocal() as db:
                return await delete_plan(db, self.admin["id"], plan_id)

        result = _run(_delete())
        self.assertEqual(result["message"], "套餐已删除")

    def test_duplicate_name_raises_invalid_input(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import create_plan

        async def _create_first():
            async with AsyncSessionLocal() as db:
                return await create_plan(db, self.admin["id"], {
                    "name": "rt-plan-dup", "display_name": "重复测试",
                })

        _run(_create_first())

        async def _create_dup():
            async with AsyncSessionLocal() as db:
                return await create_plan(db, self.admin["id"], {
                    "name": "rt-plan-dup", "display_name": "重复测试2",
                })

        with self.assertRaises(InvalidInput):
            _run(_create_dup())

    def test_cannot_delete_default_plan(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import create_plan, delete_plan

        async def _create():
            async with AsyncSessionLocal() as db:
                return await create_plan(db, self.admin["id"], {
                    "name": "rt-plan-def", "display_name": "默认候选", "is_default": True,
                })

        created = _run(_create())

        async def _delete():
            async with AsyncSessionLocal() as db:
                return await delete_plan(db, self.admin["id"], created["id"])

        with self.assertRaises(InvalidInput):
            _run(_delete())

    def test_cannot_delete_plan_with_subscribers(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import assign_user_plan, create_plan, delete_plan

        async def _create():
            async with AsyncSessionLocal() as db:
                return await create_plan(db, self.admin["id"], {
                    "name": "rt-plan-inuse", "display_name": "被订阅中",
                })

        created = _run(_create())

        async def _assign():
            async with AsyncSessionLocal() as db:
                return await assign_user_plan(db, self.admin["id"], self.target["id"], created["id"])

        assigned = _run(_assign())
        self.assertEqual(assigned["plan_name"], "rt-plan-inuse")

        async def _delete():
            async with AsyncSessionLocal() as db:
                return await delete_plan(db, self.admin["id"], created["id"])

        with self.assertRaises(Conflict):
            _run(_delete())

    def test_nonexistent_plan_raises_not_found(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import update_plan

        async def _do():
            async with AsyncSessionLocal() as db:
                return await update_plan(db, self.admin["id"], 999999999, {"monthly_token_limit": 1})

        with self.assertRaises(NotFound):
            _run(_do())


if __name__ == "__main__":
    unittest.main()
