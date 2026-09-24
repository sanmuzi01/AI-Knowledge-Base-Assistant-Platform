"""service/enterprise_access.py 的单元测试：真实 DB，直接调用依赖工厂返回的函数
（FastAPI 的 Depends(...) 只是默认值标记，显式传参调用完全等价于走真实请求）。

不经过 HTTP 层——这一步（Phase 3B 第 2 步）本来就还没往任何路由上接，见
docs/enterprise-rbac-plan.md 第 3 节的说明。
"""
import unittest

from sqlalchemy import text

from models.init_db import SessionLocal
from service.enterprise_access import (
    get_accessible_space_ids,
    require_org_role,
    require_space_permission,
    require_team_role,
)
from service.exceptions import NotFound, PermissionDenied
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


def _role_id(db, scope: str, code: str) -> int:
    return db.execute(
        text("SELECT id FROM enterprise_role WHERE scope=:s AND code=:c"),
        {"s": scope, "c": code},
    ).scalar()


def _add_org_member(db, org_id: int, user_id: int, code: str) -> None:
    db.execute(
        text(
            "INSERT INTO organization_members (organization_id, user_id, role_id, status, created_at, updated_at) "
            "VALUES (:org, :uid, :role, 'active', NOW(), NOW())"
        ),
        {"org": org_id, "uid": user_id, "role": _role_id(db, "organization", code)},
    )
    db.commit()


def _set_org_member_role(db, org_id: int, user_id: int, code: str) -> None:
    db.execute(
        text("UPDATE organization_members SET role_id=:role WHERE organization_id=:org AND user_id=:uid"),
        {"role": _role_id(db, "organization", code), "org": org_id, "uid": user_id},
    )
    db.commit()


def _create_org(db, name: str, owner_user_id: int) -> int:
    db.execute(
        text("INSERT INTO organizations (name, owner_user_id, status, created_at) VALUES (:n, :o, 'active', NOW())"),
        {"n": name, "o": owner_user_id},
    )
    db.commit()
    return db.execute(text("SELECT id FROM organizations WHERE name=:n ORDER BY id DESC LIMIT 1"), {"n": name}).scalar()


def _create_team(db, org_id: int, name: str, owner_user_id: int) -> int:
    db.execute(
        text(
            "INSERT INTO teams (organization_id, name, owner_user_id, status, created_at) "
            "VALUES (:org, :n, :o, 'active', NOW())"
        ),
        {"org": org_id, "n": name, "o": owner_user_id},
    )
    db.commit()
    return db.execute(text("SELECT id FROM teams WHERE name=:n ORDER BY id DESC LIMIT 1"), {"n": name}).scalar()


def _add_team_member(db, team_id: int, user_id: int, code: str) -> None:
    db.execute(
        text(
            "INSERT INTO team_members (team_id, user_id, role_id, status, created_at, updated_at) "
            "VALUES (:t, :uid, :role, 'active', NOW(), NOW())"
        ),
        {"t": team_id, "uid": user_id, "role": _role_id(db, "team", code)},
    )
    db.commit()


def _create_space(db, owner_user_id: int, name: str, team_id=None) -> int:
    db.execute(
        text(
            "INSERT INTO knowledge_spaces (user_id, name, is_enabled, status, doc_count, chunk_count, "
            "vector_migrated, team_id, created_at, updated_at) "
            "VALUES (:uid, :name, 1, 'active', 0, 0, 1, :team_id, NOW(), NOW())"
        ),
        {"uid": owner_user_id, "name": name, "team_id": team_id},
    )
    db.commit()
    return db.execute(text("SELECT id FROM knowledge_spaces WHERE name=:n ORDER BY id DESC LIMIT 1"), {"n": name}).scalar()


def _add_space_member(db, space_id: int, user_id: int, role: str) -> None:
    db.execute(
        text(
            "INSERT INTO space_members (space_id, user_id, role, created_at, updated_at) "
            "VALUES (:s, :u, :r, NOW(), NOW())"
        ),
        {"s": space_id, "u": user_id, "r": role},
    )
    db.commit()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class RequireOrgRoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.owner = rc.create_user("ea-org-owner")
        cls.member = rc.create_user("ea-org-member")
        cls.outsider = rc.create_user("ea-org-outsider")
        cls.org_id = _create_org(cls.db, "ea-test-org", cls.owner["id"])
        _add_org_member(cls.db, cls.org_id, cls.owner["id"], "owner")
        _add_org_member(cls.db, cls.org_id, cls.member["id"], "member")

    @classmethod
    def tearDownClass(cls):
        # 先让 rc.cleanup() 删掉这几个测试用户（连带级联删掉 organization_members），
        # organizations 这行才没有子行引用，才能真的删掉——反过来会撞 fk_om_org。
        rc.cleanup()
        cls.db.execute(text("DELETE FROM organizations WHERE id=:i"), {"i": cls.org_id})
        cls.db.commit()
        cls.db.close()

    def _user_obj(self, uid):
        from models.init_db import User
        return self.db.get(User, uid)

    def test_non_member_is_not_found(self):
        dep = require_org_role("member")
        with self.assertRaises(NotFound):
            dep(current_user=self._user_obj(self.outsider["id"]), db=self.db)

    def test_member_role_passes_member_requirement(self):
        dep = require_org_role("member")
        result = dep(current_user=self._user_obj(self.member["id"]), db=self.db)
        self.assertEqual(result.id, self.member["id"])

    def test_member_role_fails_admin_requirement(self):
        dep = require_org_role("admin")
        with self.assertRaises(PermissionDenied):
            dep(current_user=self._user_obj(self.member["id"]), db=self.db)

    def test_higher_rank_satisfies_lower_requirement(self):
        # owner 的 rank(3) 应该满足只要求 member(0) 的接口——不用在 roles 里把上级角色都列一遍
        dep = require_org_role("member")
        result = dep(current_user=self._user_obj(self.owner["id"]), db=self.db)
        self.assertEqual(result.id, self.owner["id"])


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class RequireTeamRoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.admin_user = rc.create_user("ea-team-admin")
        cls.member_user = rc.create_user("ea-team-member")
        cls.other_org_user = rc.create_user("ea-team-otherorg")

        cls.org_id = _create_org(cls.db, "ea-team-test-org", cls.admin_user["id"])
        _add_org_member(cls.db, cls.org_id, cls.admin_user["id"], "member")
        _add_org_member(cls.db, cls.org_id, cls.member_user["id"], "member")

        cls.other_org_id = _create_org(cls.db, "ea-team-other-org", cls.other_org_user["id"])
        _add_org_member(cls.db, cls.other_org_id, cls.other_org_user["id"], "member")

        cls.team_id = _create_team(cls.db, cls.org_id, "ea-test-team", cls.admin_user["id"])
        _add_team_member(cls.db, cls.team_id, cls.admin_user["id"], "admin")
        _add_team_member(cls.db, cls.team_id, cls.member_user["id"], "member")

    @classmethod
    def tearDownClass(cls):
        # 同上：先 cleanup() 删掉测试用户（连带 team_members/organization_members），
        # teams/organizations 才没有子行引用。
        rc.cleanup()
        cls.db.execute(text("DELETE FROM teams WHERE id=:i"), {"i": cls.team_id})
        cls.db.execute(text("DELETE FROM organizations WHERE id IN (:a, :b)"),
                        {"a": cls.org_id, "b": cls.other_org_id})
        cls.db.commit()
        cls.db.close()

    def _user_obj(self, uid):
        from models.init_db import User
        return self.db.get(User, uid)

    def test_team_admin_passes(self):
        dep = require_team_role("admin")
        result = dep(self.team_id, current_user=self._user_obj(self.admin_user["id"]), db=self.db)
        self.assertEqual(result.id, self.admin_user["id"])

    def test_team_member_fails_admin_requirement(self):
        dep = require_team_role("admin")
        with self.assertRaises(PermissionDenied):
            dep(self.team_id, current_user=self._user_obj(self.member_user["id"]), db=self.db)

    def test_user_from_different_organization_is_not_found(self):
        # other_org_user 在自己企业里是成员，但这个 team 属于另一个企业——应该 404，
        # 不应该因为"至少是某个企业的成员"就放行。
        dep = require_team_role("member")
        with self.assertRaises(NotFound):
            dep(self.team_id, current_user=self._user_obj(self.other_org_user["id"]), db=self.db)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class RequireSpacePermissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.owner = rc.create_user("ea-space-owner")
        cls.viewer = rc.create_user("ea-space-viewer")
        cls.outsider = rc.create_user("ea-space-outsider")
        cls.space_id = _create_space(cls.db, cls.owner["id"], "ea-test-space")
        _add_space_member(cls.db, cls.space_id, cls.viewer["id"], "viewer")

    @classmethod
    def tearDownClass(cls):
        # rc.cleanup() 按 owner 的 user_id 级联删 knowledge_spaces（连带 space_members），
        # 不用在这里手动删——顺序也一样要它先跑，不然 space_members 会挡住。
        cls.db.close()
        rc.cleanup()

    def _user_obj(self, uid):
        from models.init_db import User
        return self.db.get(User, uid)

    def test_owner_passes_even_admin_requirement(self):
        dep = require_space_permission("admin")
        result = dep(self.space_id, current_user=self._user_obj(self.owner["id"]), db=self.db)
        self.assertEqual(result.id, self.owner["id"])

    def test_viewer_passes_viewer_requirement(self):
        dep = require_space_permission("viewer")
        result = dep(self.space_id, current_user=self._user_obj(self.viewer["id"]), db=self.db)
        self.assertEqual(result.id, self.viewer["id"])

    def test_viewer_fails_editor_requirement(self):
        dep = require_space_permission("editor")
        with self.assertRaises(PermissionDenied):
            dep(self.space_id, current_user=self._user_obj(self.viewer["id"]), db=self.db)

    def test_outsider_is_not_found(self):
        dep = require_space_permission("viewer")
        with self.assertRaises(NotFound):
            dep(self.space_id, current_user=self._user_obj(self.outsider["id"]), db=self.db)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class GetAccessibleSpaceIdsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()
        cls.user = rc.create_user("ea-accessible")
        cls.other = rc.create_user("ea-accessible-other")

        cls.org_id = _create_org(cls.db, "ea-accessible-org", cls.user["id"])
        _add_org_member(cls.db, cls.org_id, cls.user["id"], "member")
        cls.team_id = _create_team(cls.db, cls.org_id, "ea-accessible-team", cls.user["id"])
        _add_team_member(cls.db, cls.team_id, cls.user["id"], "admin")

        cls.owned_space_id = _create_space(cls.db, cls.user["id"], "ea-owned-space")
        cls.member_space_id = _create_space(cls.db, cls.other["id"], "ea-member-space")
        _add_space_member(cls.db, cls.member_space_id, cls.user["id"], "viewer")
        cls.team_admin_space_id = _create_space(
            cls.db, cls.other["id"], "ea-team-admin-space", team_id=cls.team_id
        )
        cls.inaccessible_space_id = _create_space(cls.db, cls.other["id"], "ea-inaccessible-space")

    @classmethod
    def tearDownClass(cls):
        # 顺序同前两个类：先 cleanup()（按 owner 级联删 knowledge_spaces/space_members，
        # 也删 team_members/organization_members），teams/organizations 才没有子行引用。
        rc.cleanup()
        cls.db.execute(text("DELETE FROM teams WHERE id=:i"), {"i": cls.team_id})
        cls.db.execute(text("DELETE FROM organizations WHERE id=:i"), {"i": cls.org_id})
        cls.db.commit()
        cls.db.close()

    def test_three_sources_combined_without_duplicates_or_extras(self):
        from models.init_db import User
        user = self.db.get(User, self.user["id"])
        ids = set(get_accessible_space_ids(self.db, user))
        self.assertEqual(
            ids,
            {self.owned_space_id, self.member_space_id, self.team_admin_space_id},
        )
        self.assertNotIn(self.inaccessible_space_id, ids)


if __name__ == "__main__":
    unittest.main()
