"""忘记密码（手机验证码重置）链路的单测。

按项目现有异步 service 测试惯例：mock 掉 DAO 层和验证码校验，只跑
service.auth_async_service.reset_password_with_phone 里的业务分支。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from service import auth_async_service


def _fake_user(**overrides):
    defaults = dict(id=1, name="alice", phone="13900000000")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _FakeDb:
    pass


class ResetPasswordTest(unittest.IsolatedAsyncioTestCase):
    async def test_reset_password_success(self):
        db = _FakeDb()
        user = _fake_user()
        with patch.object(auth_async_service, "verify_verification_code", return_value="13900000000") as mock_verify, \
             patch.object(auth_async_service, "get_user_by_phone_async", new=AsyncMock(return_value=user)), \
             patch.object(auth_async_service, "update_user_password_async", new=AsyncMock()) as mock_update:
            result = await auth_async_service.reset_password_with_phone(db, "13900000000", "123456", "new-password")

        self.assertEqual(result, {"message": "密码已重置，请使用新密码登录"})
        mock_update.assert_awaited_once()
        # 第一次校验不消费验证码（万一后面找不到用户还能重试），成功后再消费一次
        self.assertEqual(mock_verify.call_count, 2)
        self.assertEqual(mock_verify.call_args_list[0].args[-2:], ("reset", False))
        self.assertEqual(mock_verify.call_args_list[1].args[-2:], ("reset", True))

    async def test_reset_password_rejects_unknown_phone(self):
        """验证码本身按手机号发放，理论上不会出现手机号查不到用户；仍要有兜底且不 500。"""
        db = _FakeDb()
        with patch.object(auth_async_service, "verify_verification_code", return_value="13900000099"), \
             patch.object(auth_async_service, "get_user_by_phone_async", new=AsyncMock(return_value=None)), \
             patch.object(auth_async_service, "update_user_password_async", new=AsyncMock()) as mock_update:
            with self.assertRaises(HTTPException) as ctx:
                await auth_async_service.reset_password_with_phone(db, "13900000099", "123456", "new-password")
        self.assertEqual(ctx.exception.status_code, 400)
        mock_update.assert_not_awaited()

    async def test_reset_password_propagates_invalid_code(self):
        db = _FakeDb()
        with patch.object(
            auth_async_service, "verify_verification_code",
            side_effect=HTTPException(400, detail="验证码错误"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await auth_async_service.reset_password_with_phone(db, "13900000000", "000000", "new-password")
        self.assertEqual(ctx.exception.detail, "验证码错误")


if __name__ == "__main__":
    unittest.main()
