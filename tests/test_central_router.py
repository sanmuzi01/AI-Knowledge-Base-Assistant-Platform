"""Phase 3D 阶段3：中央 Agent 受控路由（service/runtime/central_router.py）。

`match_department` 是纯函数，直接测。`resolve_target_agent[_async]` 需要真实 DB
（要查 Agent 表 + access_control 的可用性判断），真实 DB，同步+异步都测。

回归重点：现存 Agent 全部是 agent_type="personal"，路由函数对它们必须是原样
返回 agent_id 的空操作——这是这次改造"不影响现有行为"的核心承诺，两个
test_non_central_agent_* 就是专门盯着这条。
"""
import unittest

from models.init_db import Agent, Conversation, SessionLocal
from service.runtime import central_router
from tests import _route_client as rc
from tests._async_helpers import run_async as _run

_AVAILABLE, _WHY = rc.route_tests_available()


class MatchDepartmentTest(unittest.TestCase):
    def test_hr_keywords(self):
        self.assertEqual(central_router.match_department("我想请假三天"), "hr")
        self.assertEqual(central_router.match_department("新员工入职流程是什么"), "hr")

    def test_procurement_keywords(self):
        self.assertEqual(central_router.match_department("这个供应商的库存够吗"), "procurement")

    def test_sales_keywords(self):
        self.assertEqual(central_router.match_department("帮我查一下这个客户的商机"), "sales")

    def test_finance_keywords(self):
        self.assertEqual(central_router.match_department("这笔报销预算超了吗"), "finance")

    def test_it_keywords(self):
        self.assertEqual(central_router.match_department("我的账号登不上去，报故障"), "it")

    def test_no_match_returns_none(self):
        self.assertIsNone(central_router.match_department("今天天气怎么样"))

    def test_empty_message_returns_none(self):
        self.assertIsNone(central_router.match_department(""))
        self.assertIsNone(central_router.match_department(None))


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class ResolveTargetAgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = rc.create_user("router-owner")
        cls.outsider = rc.create_user("router-outsider")

        db = SessionLocal()
        try:
            central = Agent(user_id=cls.owner["id"], name="router-central", agent_type="central")
            personal = Agent(user_id=cls.owner["id"], name="router-personal")  # 默认 personal
            hr_dept = Agent(user_id=cls.owner["id"], name="router-hr-dept",
                             agent_type="department", department_code="hr")
            unowned_hr_dept = Agent(user_id=cls.outsider["id"], name="router-hr-dept-other-owner",
                                     agent_type="department", department_code="it")
            db.add_all([central, personal, hr_dept, unowned_hr_dept])
            db.commit()
            cls.central_id = central.id
            cls.personal_id = personal.id
            cls.hr_dept_id = hr_dept.id
            cls.unowned_it_dept_id = unowned_hr_dept.id

            conv = Conversation(user_id=cls.owner["id"], agent_id=cls.central_id, title="existing")
            db.add(conv)
            db.commit()
            cls.existing_conversation_id = conv.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM conversation WHERE id=:i"), {"i": cls.existing_conversation_id})
            db.execute(text("DELETE FROM agent WHERE id IN (:a,:b,:c,:d)"),
                       {"a": cls.central_id, "b": cls.personal_id, "c": cls.hr_dept_id, "d": cls.unowned_it_dept_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    # ---------------- 同步 ----------------

    def test_central_agent_routes_to_owned_department_agent(self):
        db = SessionLocal()
        try:
            target = central_router.resolve_target_agent(
                db, self.owner["id"], self.central_id, "我想请假两天", None,
            )
            self.assertEqual(target, self.hr_dept_id)
        finally:
            db.close()

    def test_central_agent_falls_back_when_no_department_agent_exists(self):
        db = SessionLocal()
        try:
            # sales 关键词命中，但没有任何 department_code="sales" 的 Agent
            target = central_router.resolve_target_agent(
                db, self.owner["id"], self.central_id, "查一下这个客户的商机", None,
            )
            self.assertEqual(target, self.central_id)
        finally:
            db.close()

    def test_central_agent_falls_back_when_department_agent_not_usable(self):
        db = SessionLocal()
        try:
            # it 关键词命中，存在 department_code="it" 的 Agent，但属于另一个不相关的用户
            # （personal 默认 scope，没共享），owner 用不了它——应该退回中央 Agent 自己回答。
            target = central_router.resolve_target_agent(
                db, self.owner["id"], self.central_id, "我的账号登不上去", None,
            )
            self.assertEqual(target, self.central_id)
        finally:
            db.close()

    def test_central_agent_no_keyword_match_answers_itself(self):
        db = SessionLocal()
        try:
            target = central_router.resolve_target_agent(
                db, self.owner["id"], self.central_id, "今天天气怎么样", None,
            )
            self.assertEqual(target, self.central_id)
        finally:
            db.close()

    def test_non_central_agent_is_untouched_regardless_of_message(self):
        # 回归重点：personal 类型的 Agent（现存 Agent 的默认值）不应该被路由改写，
        # 即使消息内容命中了某个部门的关键词。
        db = SessionLocal()
        try:
            target = central_router.resolve_target_agent(
                db, self.owner["id"], self.personal_id, "我想请假两天", None,
            )
            self.assertEqual(target, self.personal_id)
        finally:
            db.close()

    def test_existing_conversation_reuses_its_own_agent_not_rerouted(self):
        db = SessionLocal()
        try:
            # 已有会话固定用 central_id 创建；即使这次消息命中别的部门关键词，也不重新路由，
            # 沿用会话创建时定下的 agent_id。
            target = central_router.resolve_target_agent(
                db, self.owner["id"], self.central_id, "我想请假两天",
                self.existing_conversation_id,
            )
            self.assertEqual(target, self.central_id)
        finally:
            db.close()

    # ---------------- 异步 ----------------

    def test_async_central_agent_routes_to_owned_department_agent(self):
        async def _do():
            from models.async_db import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                target = await central_router.resolve_target_agent_async(
                    db, self.owner["id"], self.central_id, "我想请假两天", None,
                )
                self.assertEqual(target, self.hr_dept_id)
        _run(_do())

    def test_async_non_central_agent_is_untouched(self):
        async def _do():
            from models.async_db import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                target = await central_router.resolve_target_agent_async(
                    db, self.owner["id"], self.personal_id, "我想请假两天", None,
                )
                self.assertEqual(target, self.personal_id)
        _run(_do())


if __name__ == "__main__":
    unittest.main()
