"""service/password_policy.py 的纯规则单测，不连数据库。"""
import unittest

from service.password_policy import (
    MAX_LENGTH,
    MIN_LENGTH,
    PasswordPolicyError,
    check_not_same_as_old,
    check_password_policy,
)


class CheckPasswordPolicyTest(unittest.TestCase):
    def test_accepts_a_reasonable_password(self):
        check_password_policy("Tr0ub4dor&3xtra")  # 不抛就是通过

    def test_rejects_too_short(self):
        with self.assertRaises(PasswordPolicyError) as ctx:
            check_password_policy("a" * (MIN_LENGTH - 1))
        self.assertIn("长度", str(ctx.exception))

    def test_rejects_too_long(self):
        with self.assertRaises(PasswordPolicyError):
            check_password_policy("a" * (MAX_LENGTH + 1))

    def test_boundary_lengths_are_accepted(self):
        check_password_policy("x" * MIN_LENGTH + "1A!")  # 略超最短即可，纯重复字符不在弱密码表里
        check_password_policy("Ax9!" * (MAX_LENGTH // 4))  # 贴着上限

    def test_rejects_password_equal_to_username_case_insensitively(self):
        with self.assertRaises(PasswordPolicyError) as ctx:
            check_password_policy("AliceLogin1", username="AliceLogin1")
        self.assertIn("用户名", str(ctx.exception))
        with self.assertRaises(PasswordPolicyError):
            check_password_policy("alicelogin1", username="AliceLogin1")  # 大小写不敏感

    def test_rejects_password_equal_to_phone(self):
        with self.assertRaises(PasswordPolicyError) as ctx:
            check_password_policy("13900001234", phone="13900001234")
        self.assertIn("手机号", str(ctx.exception))

    def test_username_or_phone_check_ignored_when_not_supplied(self):
        # 找回密码场景可能只有 phone、没有 username；反过来也一样——没传的维度不参与比较
        check_password_policy("SomeStrongPw1", username="", phone="")

    def test_rejects_common_weak_passwords_case_insensitively(self):
        # 只挑长度已经 >= MIN_LENGTH 的弱密码——短的弱密码会先被"长度不够"拦下，测不到这条分支
        for weak in ("1234567890", "qwertyuiop", "QWERTYUIOP", "Qwertyuiop"):
            with self.assertRaises(PasswordPolicyError) as ctx:
                check_password_policy(weak)
            self.assertIn("常见", str(ctx.exception))

    def test_empty_password_is_rejected_not_crashed(self):
        with self.assertRaises(PasswordPolicyError):
            check_password_policy("")
        with self.assertRaises(PasswordPolicyError):
            check_password_policy(None)  # type: ignore[arg-type]


class CheckNotSameAsOldTest(unittest.TestCase):
    @staticmethod
    def _matcher(plain, stored):
        return plain == stored  # 假的"哈希比对"，测的是 check_not_same_as_old 本身的分支逻辑

    def test_raises_when_matcher_says_equal(self):
        with self.assertRaises(PasswordPolicyError) as ctx:
            check_not_same_as_old("same", "same", self._matcher)
        self.assertIn("旧密码", str(ctx.exception))

    def test_passes_when_matcher_says_different(self):
        check_not_same_as_old("new", "old", self._matcher)

    def test_missing_old_hash_never_raises(self):
        # 没有旧密码可比（比如测试用的假用户对象没有 password 字段）时不应该报错
        check_not_same_as_old("anything", None, self._matcher)
        check_not_same_as_old("anything", "", self._matcher)


if __name__ == "__main__":
    unittest.main()
