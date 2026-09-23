"""登录 / 注册 / 改密核心链路的接口级回归测试。

按项目现有测试惯例（见 test_background_task_retry.py、test_user_profile_service.py）：
用 SimpleNamespace 充当 ORM 对象、mock 掉 DAO 层和外部依赖（token 签发、短信验证码），
只对 service.auth_service 里的业务分支做真实调用，不连真实数据库。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from service import auth_service


def _fake_user(**overrides):
    defaults = dict(
        id=1,
        name="alice",
        phone="13900000000",
        password=auth_service.hash_password("correct-horse"),
        age=20,
        is_disabled=0,
        auth_version=0,
        selected_agent_id=None,
        roles=[],
        last_login_at=None,
        last_seen_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class _FakeDb:
    def __init__(self):
        self.committed = False
        self.refreshed = None

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        self.refreshed = obj

    def rollback(self):
        pass


class LoginTest(unittest.TestCase):
    def test_login_rejects_unknown_user(self):
        db = _FakeDb()
        with patch.object(auth_service, "get_user_by_name", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                auth_service.login(db, "ghost", "whatever")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "账号或密码错误")
        self.assertFalse(db.committed)

    def test_login_rejects_disabled_account(self):
        db = _FakeDb()
        user = _fake_user(is_disabled=1)
        with patch.object(auth_service, "get_user_by_name", return_value=user):
            with self.assertRaises(HTTPException) as ctx:
                auth_service.login(db, "alice", "correct-horse")
        # 禁用信息只在凭证正确后暴露，且用 403 而非 401
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("禁用", ctx.exception.detail)
        self.assertFalse(db.committed)

    def test_login_wrong_password_is_indistinguishable_from_unknown_user(self):
        db = _FakeDb()
        user = _fake_user()
        with patch.object(auth_service, "get_user_by_name", return_value=user):
            with self.assertRaises(HTTPException) as ctx:
                auth_service.login(db, "alice", "wrong-password")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "账号或密码错误")
        self.assertFalse(db.committed)

    def test_login_success_returns_token_and_updates_last_login(self):
        db = _FakeDb()
        user = _fake_user()
        with patch.object(auth_service, "get_user_by_name", return_value=user), \
             patch.object(auth_service, "create_access_token", return_value="fake.jwt.token") as mock_token, \
             patch.object(auth_service, "role_names", return_value=["user"]), \
             patch.object(auth_service, "current_user_payload", return_value={"is_admin": False}):
            result = auth_service.login(db, "alice", "correct-horse")

        self.assertEqual(result["message"], "登录成功")
        self.assertEqual(result["user_id"], 1)
        self.assertEqual(result["access_token"], "fake.jwt.token")
        self.assertEqual(result["roles"], ["user"])
        self.assertFalse(result["is_admin"])
        self.assertTrue(db.committed)
        self.assertIsNotNone(user.last_login_at)
        mock_token.assert_called_once_with({"user_id": 1, "username": "alice", "ver": 0})

    def test_login_token_carries_the_users_current_auth_version(self):
        """auth_version 不是 0 时（改过密码 / 被强制下线过），新登录的 token 要带上最新版本号。"""
        db = _FakeDb()
        user = _fake_user(auth_version=3)
        with patch.object(auth_service, "get_user_by_name", return_value=user), \
             patch.object(auth_service, "create_access_token", return_value="fake.jwt.token") as mock_token, \
             patch.object(auth_service, "role_names", return_value=["user"]), \
             patch.object(auth_service, "current_user_payload", return_value={"is_admin": False}):
            auth_service.login(db, "alice", "correct-horse")
        mock_token.assert_called_once_with({"user_id": 1, "username": "alice", "ver": 3})

    def test_login_rejects_non_bcrypt_stored_password(self):
        """存量明文口令不再被接受：必须先跑 migrate_plaintext_passwords。"""
        db = _FakeDb()
        user = _fake_user(password="plain-text-password")
        with patch.object(auth_service, "get_user_by_name", return_value=user):
            with self.assertRaises(HTTPException) as ctx:
                auth_service.login(db, "alice", "plain-text-password")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "账号或密码错误")
        self.assertFalse(db.committed)


class PasswordHelperTest(unittest.TestCase):
    def test_is_bcrypt_hash(self):
        self.assertTrue(auth_service.is_bcrypt_hash(auth_service.hash_password("x")))
        self.assertFalse(auth_service.is_bcrypt_hash("plain"))
        self.assertFalse(auth_service.is_bcrypt_hash(""))
        self.assertFalse(auth_service.is_bcrypt_hash(None))

    def test_password_matches_only_accepts_bcrypt(self):
        hashed = auth_service.hash_password("s3cret")
        self.assertTrue(auth_service.password_matches("s3cret", hashed))
        self.assertFalse(auth_service.password_matches("wrong", hashed))
        # 非 bcrypt 存储值一律不匹配，即使明文完全相等
        self.assertFalse(auth_service.password_matches("plain", "plain"))
        # 损坏的哈希不抛异常
        self.assertFalse(auth_service.password_matches("x", "$2b$not-a-real-hash"))


class RegisterTest(unittest.TestCase):
    def test_register_requires_accepted_terms(self):
        db = _FakeDb()
        with self.assertRaises(HTTPException) as ctx:
            auth_service.register(db, "bob", "pw123456", 22, "13900000001", "000000", accepted_terms=False)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_register_rejects_reserved_admin_name(self):
        db = _FakeDb()
        result = auth_service.register(db, "Admin", "pw123456", 22, "13900000001", "000000", accepted_terms=True)
        self.assertEqual(result, {"message": "admin 为系统保留账号，不能注册"})

    def test_register_rejects_duplicate_username(self):
        db = _FakeDb()
        with patch.object(auth_service, "verify_register_code", return_value="13900000001"), \
             patch.object(auth_service, "get_user_by_name", return_value=_fake_user()):
            result = auth_service.register(db, "alice", "pw123456789", 22, "13900000001", "000000", accepted_terms=True)
        self.assertEqual(result, {"message": "用户已经存在"})

    def test_register_rejects_duplicate_phone(self):
        db = _FakeDb()
        with patch.object(auth_service, "verify_register_code", return_value="13900000001"), \
             patch.object(auth_service, "get_user_by_name", return_value=None), \
             patch.object(auth_service, "get_user_by_phone", return_value=_fake_user()):
            result = auth_service.register(db, "bob", "pw123456789", 22, "13900000001", "000000", accepted_terms=True)
        self.assertEqual(result, {"message": "手机号已经注册"})

    def test_register_success_creates_user_and_consumes_code(self):
        db = _FakeDb()
        new_user = _fake_user(id=2, name="bob", phone="13900000001")
        with patch.object(auth_service, "verify_register_code", return_value="13900000001") as mock_verify, \
             patch.object(auth_service, "get_user_by_name", return_value=None), \
             patch.object(auth_service, "get_user_by_phone", return_value=None), \
             patch.object(auth_service, "create_user", return_value=new_user) as mock_create:
            result = auth_service.register(db, "bob", "pw123456789", 22, "13900000001", "000000", accepted_terms=True)

        self.assertEqual(result["message"], "注册成功")
        self.assertEqual(result["user_id"], 2)
        mock_create.assert_called_once()
        # 第一次校验不消费验证码，注册成功后再消费一次
        self.assertEqual(mock_verify.call_count, 2)
        self.assertEqual(mock_verify.call_args_list[0].kwargs.get("consume"), False)
        self.assertEqual(mock_verify.call_args_list[1].kwargs.get("consume"), True)

    def test_register_rejects_weak_password_before_touching_the_database(self):
        """密码策略检查放在最前面：太弱的密码连验证码校验、查库都不会走到。"""
        db = _FakeDb()
        with patch.object(auth_service, "verify_register_code") as mock_verify, \
             patch.object(auth_service, "get_user_by_name") as mock_get_user:
            with self.assertRaises(HTTPException) as ctx:
                auth_service.register(db, "bob", "123456", 22, "13900000001", "000000", accepted_terms=True)
        self.assertEqual(ctx.exception.status_code, 400)
        mock_verify.assert_not_called()
        mock_get_user.assert_not_called()

    def test_register_rejects_password_equal_to_username(self):
        # 用户名也要够 10 位，否则会先被"密码太短"挡住，测不到"等于用户名"这条规则
        db = _FakeDb()
        with self.assertRaises(HTTPException) as ctx:
            auth_service.register(db, "bob1234567", "bob1234567", 22, "13900000001", "000000", accepted_terms=True)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("用户名", ctx.exception.detail)

    def test_register_rejects_password_equal_to_phone(self):
        db = _FakeDb()
        with self.assertRaises(HTTPException) as ctx:
            auth_service.register(db, "bob", "13900000001", 22, "13900000001", "000000", accepted_terms=True)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("手机号", ctx.exception.detail)


class ChangePasswordTest(unittest.TestCase):
    def test_change_password_rejects_wrong_old_password(self):
        db = _FakeDb()
        user = _fake_user()
        result = auth_service.change_password(db, user, "not-the-old-password", "new-password")
        self.assertEqual(result, {"message": "旧密码错误"})
        self.assertFalse(db.committed)

    def test_change_password_rejects_same_password(self):
        db = _FakeDb()
        user = _fake_user()
        result = auth_service.change_password(db, user, "correct-horse", "correct-horse")
        self.assertEqual(result, {"message": "新密码不能和旧密码相同"})
        self.assertFalse(db.committed)

    def test_change_password_success(self):
        db = _FakeDb()
        user = _fake_user()
        with patch.object(auth_service, "update_user_password") as mock_update:
            result = auth_service.change_password(db, user, "correct-horse", "new-password")
        self.assertEqual(result, {"message": "修改成功"})
        # 提交（以及 auth_version+1 让旧 token 失效）现在发生在 update_user_password 内部，
        # change_password 自己不再重复 commit，所以这里只断言调用参数，不再断言 db.committed
        mock_update.assert_called_once()
        called_db, called_user, called_hash = mock_update.call_args[0]
        self.assertIs(called_db, db)
        self.assertIs(called_user, user)
        self.assertTrue(auth_service.password_matches("new-password", called_hash))

    def test_change_password_rejects_weak_new_password(self):
        db = _FakeDb()
        user = _fake_user()
        result = auth_service.change_password(db, user, "correct-horse", "short")
        self.assertIn("长度", result["message"])
        self.assertFalse(db.committed)

    def test_change_password_rejects_new_password_equal_to_username(self):
        # 用户名长度也要够 10 位，否则会先被"密码太短"挡住，测不到"等于用户名"这条规则
        db = _FakeDb()
        user = _fake_user(name="alice12345")
        result = auth_service.change_password(db, user, "correct-horse", user.name)
        self.assertIn("用户名", result["message"])

    def test_change_password_policy_runs_before_the_same_as_old_check(self):
        """先判断"这个密码本身够不够格"，再判断"是不是跟旧密码一样"——弱密码即使凑巧等于旧密码，
        提示也应该是"太弱"，而不是掩盖成"和旧密码相同"。"""
        db = _FakeDb()
        user = _fake_user(password=auth_service.hash_password("123456"))
        result = auth_service.change_password(db, user, "123456", "123456")
        self.assertIn("长度", result["message"])


if __name__ == "__main__":
    unittest.main()
