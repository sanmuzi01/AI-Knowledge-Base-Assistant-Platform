"""admin_service.delete_user 的回归测试。

审计时发现：这个函数原来只清理 LLMConfig/Memory/BackgroundTask/Chat/角色，完全不知道
知识库空间（KnowledgeSpace，现在所有新上传文档的默认路径）、企业接口连接器、
固定评估集这些表——对任何真实用过产品的用户（几乎必然有至少一个 KnowledgeSpace），
点"删除用户"会直接撞 FK 约束报错，这个按钮实际上是坏的，只是没有测试覆盖到
"删一个有真实业务数据的用户"这个场景才没被发现。
"""
import unittest

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class DeleteUserWithRealDataTest(unittest.TestCase):
    def test_delete_user_with_knowledge_space_connector_and_eval_set(self):
        from models.init_db import (
            SessionLocal, KnowledgeSpace, AgentApiConnector, EvalSet, EvalRun, Agent,
            Plan, UserSubscription,
        )
        from service.admin_service import delete_user

        target = rc.create_user("rt-deluser-target")
        operator = rc.create_user("rt-deluser-op")

        db = SessionLocal()
        try:
            agent = Agent(user_id=target["id"], name="rt-deluser-agent")
            db.add(agent)
            db.flush()

            space = KnowledgeSpace(user_id=target["id"], name="rt-deluser-space")
            db.add(space)
            db.flush()

            connector = AgentApiConnector(
                user_id=target["id"], agent_id=agent.id, name="rt_conn",
                description="desc", url="https://api.example.com", method="GET",
                param_schema_json="{}",
            )
            db.add(connector)

            eval_set = EvalSet(
                user_id=target["id"], agent_id=agent.id, name="rt-eval",
                cases_json="[]", settings_json="{}",
            )
            db.add(eval_set)
            db.flush()
            db.add(EvalRun(eval_set_id=eval_set.id, report_json="{}"))

            plan = db.query(Plan).filter(Plan.name == "rt-deluser-plan").first()
            if not plan:
                plan = Plan(name="rt-deluser-plan", display_name="rt-deluser-plan", monthly_token_limit=0)
                db.add(plan)
                db.flush()
            db.add(UserSubscription(user_id=target["id"], plan_id=plan.id))
            db.commit()

            space_id = space.id
        finally:
            db.close()

        # 之前这里会直接抛 IntegrityError（FK 约束），现在应该干净地成功
        db2 = SessionLocal()
        try:
            result = delete_user(db2, target["id"], operator["id"])
        finally:
            db2.close()
        self.assertEqual(result.get("message"), "用户已删除")

        # 确认真的删干净了：用户本身 + 关联的知识库空间都不在了
        from sqlalchemy import text
        db3 = SessionLocal()
        try:
            self.assertIsNone(db3.execute(
                text("SELECT id FROM `user` WHERE id=:u"), {"u": target["id"]},
            ).first())
            self.assertIsNone(db3.execute(
                text("SELECT id FROM knowledge_spaces WHERE id=:s"), {"s": space_id},
            ).first())
            self.assertIsNone(db3.execute(
                text("SELECT id FROM user_subscription WHERE user_id=:u"), {"u": target["id"]},
            ).first())
            db3.execute(text("DELETE FROM plan WHERE name='rt-deluser-plan'"))
            db3.commit()
        finally:
            db3.close()

        rc.cleanup()


if __name__ == "__main__":
    unittest.main()
