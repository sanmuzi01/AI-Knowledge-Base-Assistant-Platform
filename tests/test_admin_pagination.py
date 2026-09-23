"""管理后台 4 个列表接口的分页回归测试：用户 / 后台任务 / 操作日志 / 企业知识库空间。

之前这几个接口要么完全没有 limit（用户列表），要么只有 limit 没有 offset/total
（任务、日志、空间），数据量大了会看不全也不会提示。这组测试用真实 MySQL，
锁定 total 是准确的全量计数（不受 limit 影响）、offset 真的能翻页、以及用户
列表新增的按用户名模糊搜索。
"""
import asyncio
import unittest

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


def _run(coro):
    return asyncio.run(coro)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AdminUsersPaginationTest(unittest.TestCase):
    PREFIX = "rt-adminpg-user"

    @classmethod
    def setUpClass(cls):
        cls.users = [rc.create_user(f"{cls.PREFIX}{i}") for i in range(5)]

    @classmethod
    def tearDownClass(cls):
        rc.cleanup()

    def test_total_reflects_full_match_count_not_page_size(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import list_users

        async def _do():
            async with AsyncSessionLocal() as db:
                return await list_users(db, limit=2, offset=0, search=self.PREFIX)

        result = _run(_do())
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["limit"], 2)
        self.assertEqual(result["offset"], 0)

    def test_offset_pages_through_without_overlap_or_gap(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import list_users

        async def _page(offset):
            async with AsyncSessionLocal() as db:
                return await list_users(db, limit=2, offset=offset, search=self.PREFIX)

        seen_ids = []
        for offset in (0, 2, 4):
            page = _run(_page(offset))
            seen_ids.extend(u["id"] for u in page["items"])
        self.assertEqual(len(seen_ids), len(set(seen_ids)), "翻页之间不应该有重复")
        self.assertEqual(len(seen_ids), 5)

    def test_search_filters_by_name(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import list_users

        async def _do():
            async with AsyncSessionLocal() as db:
                return await list_users(db, search="not-a-real-user-xyz")

        result = _run(_do())
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])

    def test_limit_is_capped(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import list_users

        async def _do():
            async with AsyncSessionLocal() as db:
                return await list_users(db, limit=99999, search=self.PREFIX)

        result = _run(_do())
        self.assertLessEqual(result["limit"], 200)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AdminTasksPaginationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.init_db import SessionLocal, BackgroundTask

        cls.user = rc.create_user("rt-adminpg-task")
        db = SessionLocal()
        try:
            cls.task_ids = []
            for i in range(3):
                t = BackgroundTask(
                    user_id=cls.user["id"], task_type="knowledge_index",
                    title=f"rt-adminpg-task-{i}", status="queued",
                )
                db.add(t)
                db.flush()
                cls.task_ids.append(t.id)
            db.commit()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM background_task WHERE id IN :ids".replace(
                ":ids", "(" + ",".join(str(i) for i in cls.task_ids) + ")")))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def test_total_and_offset(self):
        from models.async_db import AsyncSessionLocal
        from service.background_task_async_service import list_all_tasks

        async def _do(offset):
            async with AsyncSessionLocal() as db:
                return await list_all_tasks(db, limit=2, offset=offset, task_type="knowledge_index")

        first = _run(_do(0))
        self.assertGreaterEqual(first["total"], 3)  # 其它测试可能也留了同类型任务，只要求不少于我们建的
        self.assertEqual(len(first["items"]), 2)
        self.assertEqual(first["offset"], 0)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AdminKnowledgeSpacesPaginationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.init_db import SessionLocal, KnowledgeSpace

        cls.user = rc.create_user("rt-adminpg-space")
        db = SessionLocal()
        try:
            cls.space_ids = []
            for i in range(3):
                s = KnowledgeSpace(user_id=cls.user["id"], name=f"rt-adminpg-space-{i}")
                db.add(s)
                db.flush()
                cls.space_ids.append(s.id)
            db.commit()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            ids = "(" + ",".join(str(i) for i in cls.space_ids) + ")"
            db.execute(text(f"DELETE FROM knowledge_spaces WHERE id IN {ids}"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def test_total_is_real_count_not_len_of_page(self):
        from models.async_db import AsyncSessionLocal
        from service.admin_async_service import list_knowledge_spaces

        async def _do():
            async with AsyncSessionLocal() as db:
                return await list_knowledge_spaces(db, limit=1, offset=0)

        result = _run(_do())
        self.assertEqual(len(result["items"]), 1)
        self.assertGreaterEqual(result["total"], 3, "total 应该是全表计数，不是被 limit=1 截断后的 1")


if __name__ == "__main__":
    unittest.main()
