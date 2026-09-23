import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import inspect

from models.init_db import User
from service import dependencies


class CurrentUserDependencyTest(unittest.IsolatedAsyncioTestCase):
    async def test_seen_timestamp_is_not_left_dirty_after_committed_touch(self):
        user = User(id=1, name="admin", password="hash", is_disabled=0, last_seen_at=None, auth_version=0)

        with (
            patch.object(dependencies, "_decode_payload", return_value={"user_id": 1, "ver": 0}),
            patch.object(dependencies, "get_user_by_id_async", new=AsyncMock(return_value=user)),
            patch.object(dependencies, "touch_user_seen_async", new=AsyncMock(return_value=True)) as touch,
        ):
            result = await dependencies.get_current_user_async(object(), async_db=object())

        self.assertIs(result, user)
        touch.assert_awaited_once()
        self.assertIsNotNone(user.last_seen_at)
        self.assertFalse(inspect(user).attrs.last_seen_at.history.has_changes())


class SessionVersionCheckTest(unittest.IsolatedAsyncioTestCase):
    def test_matching_version_passes(self):
        user = User(id=1, name="admin", password="hash", auth_version=2)
        dependencies._check_session_version(user, {"user_id": 1, "ver": 2})  # 不抛就是通过

    def test_missing_ver_in_token_is_treated_as_version_zero(self):
        """改密码/加这个功能之前签发的旧 token 没有 ver 字段——只有用户从没改过密码（auth_version 仍是 0）才放行。"""
        user = User(id=1, name="admin", password="hash", auth_version=0)
        dependencies._check_session_version(user, {"user_id": 1})  # 没有 ver key，不抛

    def test_stale_token_is_rejected_with_401_and_a_specific_message(self):
        user = User(id=1, name="admin", password="hash", auth_version=1)
        with self.assertRaises(HTTPException) as ctx:
            dependencies._check_session_version(user, {"user_id": 1, "ver": 0})
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("失效", ctx.exception.detail)

    async def test_get_current_user_async_rejects_a_stale_token_before_touching_seen_at(self):
        user = User(id=1, name="admin", password="hash", is_disabled=0, auth_version=5)
        with (
            patch.object(dependencies, "_decode_payload", return_value={"user_id": 1, "ver": 0}),
            patch.object(dependencies, "get_user_by_id_async", new=AsyncMock(return_value=user)),
            patch.object(dependencies, "touch_user_seen_async", new=AsyncMock()) as touch,
        ):
            with self.assertRaises(HTTPException) as ctx:
                await dependencies.get_current_user_async(object(), async_db=object())
        self.assertEqual(ctx.exception.status_code, 401)
        touch.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
