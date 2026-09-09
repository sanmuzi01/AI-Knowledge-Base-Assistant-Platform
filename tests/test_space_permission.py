"""知识库空间企业权限：角色解析 / 能力判定纯逻辑单测（不依赖 DB）。

端到端（成员增删、viewer/editor/admin 分级、非成员 404、审计落库、管理员总览）
由 tests/test_routes_isolation.py 覆盖。
"""

import unittest
from types import SimpleNamespace

from service.knowledge_space import membership as m


def _space(owner_id):
    return SimpleNamespace(user_id=owner_id)


class ResolveRoleTest(unittest.TestCase):
    def test_owner_by_space_user_id(self):
        self.assertEqual(m.resolve_role(7, _space(7)), "owner")
        self.assertEqual(m.resolve_role(7, _space(7), "viewer"), "owner")  # owner 压过成员表

    def test_member_role_passed_through(self):
        self.assertEqual(m.resolve_role(8, _space(7), "editor"), "editor")
        self.assertEqual(m.resolve_role(8, _space(7), "admin"), "admin")

    def test_stranger_is_none(self):
        self.assertIsNone(m.resolve_role(9, _space(7)))
        self.assertIsNone(m.resolve_role(9, _space(7), None))
        self.assertIsNone(m.resolve_role(9, _space(7), "bogus"))
        self.assertIsNone(m.resolve_role(9, None, "admin"))


class CapabilityTest(unittest.TestCase):
    def test_write_doc(self):
        self.assertTrue(m.can_write_doc("owner"))
        self.assertTrue(m.can_write_doc("admin"))
        self.assertTrue(m.can_write_doc("editor"))
        self.assertFalse(m.can_write_doc("viewer"))
        self.assertFalse(m.can_write_doc(None))

    def test_manage_space(self):
        self.assertTrue(m.can_manage_space("owner"))
        self.assertTrue(m.can_manage_space("admin"))
        self.assertFalse(m.can_manage_space("editor"))
        self.assertFalse(m.can_manage_space("viewer"))

    def test_delete_space_owner_only(self):
        self.assertTrue(m.can_delete_space("owner"))
        self.assertFalse(m.can_delete_space("admin"))

    def test_manage_members_owner_admin(self):
        self.assertTrue(m.can_manage_members("owner"))
        self.assertTrue(m.can_manage_members("admin"))
        self.assertFalse(m.can_manage_members("editor"))

    def test_at_least_ranking(self):
        self.assertTrue(m.at_least("owner", "admin"))
        self.assertTrue(m.at_least("admin", "editor"))
        self.assertTrue(m.at_least("editor", "editor"))
        self.assertFalse(m.at_least("editor", "admin"))
        self.assertFalse(m.at_least("viewer", "editor"))
        self.assertFalse(m.at_least(None, "viewer"))


class RolesConstantTest(unittest.TestCase):
    def test_roles_and_rank(self):
        self.assertEqual(set(m.ROLES), {"owner", "admin", "editor", "viewer"})
        self.assertEqual(m.ROLE_RANK["owner"], max(m.ROLE_RANK.values()))
        self.assertEqual(m.ROLE_RANK["viewer"], min(m.ROLE_RANK.values()))


if __name__ == "__main__":
    unittest.main()
