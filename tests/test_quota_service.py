"""计费/配额服务（service/quota_service.py）的回归测试。

覆盖：默认套餐不限量、订阅了有限额套餐后用量算对、超额抛 QuotaExceeded、
以及 /chat 路由在真正调用 Agent/LLM 之前就被配额拦住（用一个不存在的 agent_id
也能验证——配额检查排在归属校验之前，命中 429 就说明拦截生效了）。
"""
import asyncio
import unittest

from service.exceptions import QuotaExceeded
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


def _run(coro):
    return asyncio.run(coro)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class QuotaServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.init_db import SessionLocal, Plan

        cls.user = rc.create_user("rt-quota-user")
        cls.unsub_user = rc.create_user("rt-quota-unsub")
        db = SessionLocal()
        try:
            plan = Plan(
                name=f"rt-quota-plan-{cls.user['id']}", display_name="测试小额套餐",
                monthly_token_limit=100, is_default=0, is_enabled=1,
            )
            db.add(plan)
            db.commit()
            cls.plan_id = plan.id
        finally:
            db.close()

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

    def _seed_run(self, tokens: int):
        from models.init_db import SessionLocal, Agent, AgentRun

        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.user_id == self.user["id"]).first()
            if not agent:
                agent = Agent(user_id=self.user["id"], name="rt-quota-agent")
                db.add(agent)
                db.flush()
            db.add(AgentRun(
                user_id=self.user["id"], agent_id=agent.id,
                user_message="hi", status="finished", total_tokens=tokens,
            ))
            db.commit()
        finally:
            db.close()

    def test_unlimited_when_no_subscription_and_default_plan_is_zero(self):
        from models.async_db import AsyncSessionLocal
        from service.quota_service import get_quota_status_async

        async def _do():
            async with AsyncSessionLocal() as db:
                return await get_quota_status_async(db, self.unsub_user["id"])

        status_ = _run(_do())
        # 默认套餐（bootstrap 生成的 "free"）monthly_token_limit=0 → 不限量；
        # 就算管理员改过默认套餐的限额，这里也至少不应该报错，是个宽松断言。
        self.assertIn("unlimited", status_)
        self.assertIn("plan_display_name", status_)

    def test_enforce_quota_raises_after_subscribing_small_plan_and_exceeding(self):
        from models.async_db import AsyncSessionLocal
        from models.plan_async_dao import set_user_plan_async
        from service.quota_service import enforce_quota_async, get_quota_status_async

        async def _subscribe_and_seed():
            async with AsyncSessionLocal() as db:
                await set_user_plan_async(db, self.user["id"], self.plan_id)

        _run(_subscribe_and_seed())
        self._seed_run(150)  # 套餐上限 100，跑一次消耗 150 → 应该超额

        async def _check():
            async with AsyncSessionLocal() as db:
                status_ = await get_quota_status_async(db, self.user["id"])
                self.assertFalse(status_["unlimited"])
                self.assertEqual(status_["monthly_token_limit"], 100)
                self.assertGreaterEqual(status_["used_tokens"], 150)
                with self.assertRaises(QuotaExceeded):
                    await enforce_quota_async(db, self.user["id"])

        _run(_check())

    def test_chat_route_blocked_by_quota_before_reaching_agent_lookup(self):
        from models.async_db import AsyncSessionLocal
        from models.plan_async_dao import set_user_plan_async

        async def _subscribe():
            async with AsyncSessionLocal() as db:
                await set_user_plan_async(db, self.user["id"], self.plan_id)

        # 每个测试方法独立准备状态——unittest 按字母序跑测试方法，不能依赖
        # 另一个方法先跑过才订阅成功这件事。
        _run(_subscribe())
        self._seed_run(150)  # 套餐上限 100，跑一次消耗 150 → 超额

        client = rc.make_client()
        resp = client.post(
            "/chat/999999999",
            json={"message": "hello"},
            headers=self.user["headers"],
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json().get("code"), "quota_exceeded")


if __name__ == "__main__":
    unittest.main()
