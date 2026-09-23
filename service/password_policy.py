"""统一密码策略：注册、修改密码、找回密码、管理员重置密码共用同一份判断。

只在这一个模块里改规则，四个入口跟着一起生效——避免以前那种"改了一处校验，
另一处忘了改"的问题。这里只管"密码本身够不够好"（长度、是否等于用户名/手机号、
是否常见弱密码）；"新密码是否和旧密码相同"要拿旧密码的哈希才能判断，由调用方
（已经查到 user 记录）自己用 `password_matches` 再检查一次。
"""
from typing import Optional

MIN_LENGTH = 10
MAX_LENGTH = 72  # bcrypt 只认前 72 字节，超过部分会被静默截断；设成上限，避免用户以为设了个更长的密码却不生效

# 不是穷举字典，只挡撞库工具第一轮最先试的这一批常见弱口令/键盘序列
_COMMON_WEAK_PASSWORDS = frozenset({
    "123456", "1234567890", "12345678", "123456789", "1234567", "87654321",
    "password", "p@ssw0rd", "passw0rd", "qwertyuiop", "qwerty123",
    "111111", "000000", "123123", "123321", "abc123", "abcd1234",
    "password1", "admin123", "666666", "888888", "a12345678",
    "1qaz2wsx", "1q2w3e4r", "iloveyou", "5201314", "woaini123",
})


class PasswordPolicyError(ValueError):
    """message 可以直接展示给用户。"""


def check_password_policy(password: str, *, username: str = "", phone: str = "") -> None:
    """校验新密码是否满足统一策略，不满足抛 PasswordPolicyError。"""
    pw = password or ""
    if len(pw) < MIN_LENGTH or len(pw) > MAX_LENGTH:
        raise PasswordPolicyError(f"密码长度需在 {MIN_LENGTH}～{MAX_LENGTH} 位之间")
    if username and pw.lower() == username.strip().lower():
        raise PasswordPolicyError("密码不能和用户名相同")
    if phone and pw == phone.strip():
        raise PasswordPolicyError("密码不能和手机号相同")
    if pw.lower() in _COMMON_WEAK_PASSWORDS:
        raise PasswordPolicyError("这个密码太常见，容易被猜到，换一个更安全的")


def check_not_same_as_old(new_password: str, old_password_hash: Optional[str], matcher) -> None:
    """新密码不能等于旧密码。`matcher` 传 `service.auth_service.password_matches`，
    这里不直接依赖 auth_service，避免和它互相 import 造成循环依赖。
    """
    if old_password_hash and matcher(new_password, old_password_hash):
        raise PasswordPolicyError("新密码不能和旧密码相同")
