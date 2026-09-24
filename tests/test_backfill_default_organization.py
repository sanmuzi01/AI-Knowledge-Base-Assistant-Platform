"""scripts/backfill_default_organization.py 的幂等性测试：真实 DB，真实建用户。

不重新造一个假的空库场景——直接在当前真实开发库上验证"新用户会被补进默认企业，
跑两遍不会重复"，这正是这个脚本在生产上要做的事。
"""
import unittest

from sqlalchemy import text

from models.init_db import SessionLocal
from scripts.backfill_default_organization import run
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class BackfillDefaultOrganizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alice = rc.create_user("backfill-alice")
        cls.bob = rc.create_user("backfill-bob")

    @classmethod
    def tearDownClass(cls):
        rc.cleanup()

    def _org_role(self, user_id: int):
        db = SessionLocal()
        try:
            row = db.execute(
                text(
                    "SELECT er.scope, er.code FROM organization_members om "
                    "JOIN enterprise_role er ON om.role_id = er.id WHERE om.user_id = :uid"
                ),
                {"uid": user_id},
            ).first()
            return tuple(row) if row else None
        finally:
            db.close()

    def test_new_users_get_backfilled_as_members_and_rerun_is_idempotent(self):
        # 跑之前两个新用户都不该在 organization_members 里
        self.assertIsNone(self._org_role(self.alice["id"]))
        self.assertIsNone(self._org_role(self.bob["id"]))

        run(dry_run=False)
        self.assertEqual(self._org_role(self.alice["id"]), ("organization", "member"))
        self.assertEqual(self._org_role(self.bob["id"]), ("organization", "member"))

        # 再跑一遍：角色不变，且不会插出第二条（uq_org_member 唯一索引 + 脚本自己的
        # existing_member_ids 过滤，任何一层失效都会在这里炸出来）
        run(dry_run=False)
        self.assertEqual(self._org_role(self.alice["id"]), ("organization", "member"))

        db = SessionLocal()
        try:
            count = db.execute(
                text("SELECT COUNT(*) FROM organization_members WHERE user_id = :uid"),
                {"uid": self.alice["id"]},
            ).scalar()
        finally:
            db.close()
        self.assertEqual(count, 1, "重复跑不应该插出第二条 organization_members")


if __name__ == "__main__":
    unittest.main()
