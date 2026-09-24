"""配额阈值提醒（service/quota_service.py::check_and_notify_threshold_async）回归测试。

只测"接线对不对"：80%/95%/100% 跨越判定的边界条件，以及 dispatch_alert_async 调用
本身 mock 掉（真实推送已经在 tests/test_notification_channel.py 里测过）。
"""
import unittest
from unittest.mock import AsyncMock, patch

from tests import _route_client as rc
from tests._async_helpers import run_async as _run

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class QuotaThresholdAlertTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("rt-quota-alert")
        from models.init_db import SessionLocal, Plan

        db = SessionLocal()
        try:
            plan = Plan(
                name=f"rt-quota-alert-plan-{cls.user['id']}", display_name="阈值测试套餐",
                monthly_token_limit=100, is_default=0, is_enabled=1,
            )
            db.add(plan)
            db.commit()
            cls.plan_id = plan.id
        finally:
            db.close()

        from models.async_db import AsyncSessionLocal
        from models.plan_async_dao import set_user_plan_async

        async def _subscribe():
            async with AsyncSessionLocal() as db2:
                await set_user_plan_async(db2, cls.user["id"], cls.plan_id)

        _run(_subscribe())

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM agent_run WHERE user_id=:u"), {"u": cls.user["id"]})
            db.execute(text("DELETE FROM user_subscription WHERE user_id=:u"), {"u": cls.user["id"]})
            db.execute(text("DELETE FROM plan WHERE id=:p"), {"p": cls.plan_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def setUp(self):
        # 每个测试方法独立：先清掉这个用户之前测试方法留下的 AgentRun，
        # 保证 used_after 只反映本方法自己 seed 的数据，不受执行顺序影响。
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM agent_run WHERE user_id=:u"), {"u": self.user["id"]})
            db.commit()
        finally:
            db.close()

    def _seed_run(self, tokens: int):
        from models.init_db import SessionLocal, Agent, AgentRun

        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.user_id == self.user["id"]).first()
            if not agent:
                agent = Agent(user_id=self.user["id"], name="rt-quota-alert-agent")
                db.add(agent)
                db.flush()
            db.add(AgentRun(
                user_id=self.user["id"], agent_id=agent.id,
                user_message="hi", status="finished", total_tokens=tokens,
            ))
            db.commit()
        finally:
            db.close()

    def test_crossing_80_percent_fires_once(self):
        from models.async_db import AsyncSessionLocal
        from service.quota_service import check_and_notify_threshold_async

        self._seed_run(85)  # 限额 100，用量 0 -> 85，跨过 80%

        mock_dispatch = AsyncMock()

        async def _do():
            async with AsyncSessionLocal() as db:
                with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
                    await check_and_notify_threshold_async(db, self.user["id"], used_before=0)

        _run(_do())
        mock_dispatch.assert_awaited_once()
        title = mock_dispatch.call_args.kwargs.get("title", "")
        self.assertIn("80%", title + str(mock_dispatch.call_args))

    def test_not_crossing_any_threshold_does_not_fire(self):
        from models.async_db import AsyncSessionLocal
        from service.quota_service import check_and_notify_threshold_async

        mock_dispatch = AsyncMock()

        async def _do():
            async with AsyncSessionLocal() as db:
                with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
                    # used_before=10, 这次运行后 used_after 也还在 10（模拟没有新 run），不跨过任何阈值
                    await check_and_notify_threshold_async(db, self.user["id"], used_before=10)

        _run(_do())
        mock_dispatch.assert_not_awaited()

    def test_crossing_multiple_thresholds_in_one_jump_fires_each(self):
        from models.async_db import AsyncSessionLocal
        from service.quota_service import check_and_notify_threshold_async

        self._seed_run(120)  # 一次运行直接从 0 冲到 120，同时跨过 80%/95%/100%

        mock_dispatch = AsyncMock()

        async def _do():
            async with AsyncSessionLocal() as db:
                with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
                    await check_and_notify_threshold_async(db, self.user["id"], used_before=0)

        _run(_do())
        self.assertEqual(mock_dispatch.call_count, 3)

    def test_dispatch_failure_does_not_raise(self):
        from models.async_db import AsyncSessionLocal
        from service.quota_service import check_and_notify_threshold_async

        self._seed_run(90)

        async def _do():
            async with AsyncSessionLocal() as db:
                with patch("service.notification_service.dispatch_alert_async", side_effect=Exception("boom")):
                    await check_and_notify_threshold_async(db, self.user["id"], used_before=0)

        _run(_do())  # 不应该抛异常


if __name__ == "__main__":
    unittest.main()
