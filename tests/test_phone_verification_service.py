import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from service.phone_verification_service import (
    send_register_code,
    send_verification_code,
    verify_register_code,
    verify_verification_code,
)
from utils.cache import verification_cache


class PhoneVerificationServiceTest(unittest.TestCase):
    def setUp(self):
        os.environ["SMS_PROVIDER"] = "console"
        os.environ["SMS_EXPOSE_DEV_CODE"] = "1"
        os.environ["SMS_CODE_PHONE_LIMIT"] = "100"
        os.environ["SMS_CODE_DAILY_LIMIT"] = "100"
        os.environ["SMS_CODE_IP_LIMIT"] = "100"
        os.environ["SMS_CODE_GLOBAL_HOURLY_LIMIT"] = "0"
        os.environ["SMS_CODE_GLOBAL_DAILY_LIMIT"] = "0"

    def test_send_and_consume_register_code(self):
        phone = "13921810001"
        result = send_register_code(phone, client_ip="127.0.0.1")

        self.assertEqual(result["message"], "验证码已发送")
        self.assertEqual(result["provider"], "console")
        self.assertRegex(result["dev_code"], r"^\d{6}$")
        self.assertEqual(verify_register_code(phone, result["dev_code"]), phone)

        with self.assertRaises(HTTPException):
            verify_register_code(phone, result["dev_code"])

    def test_invalid_phone_rejected(self):
        with self.assertRaises(HTTPException):
            send_register_code("12345", client_ip="127.0.0.1")

    def test_register_and_reset_codes_do_not_interfere(self):
        """同一个手机号同时有一个未用的注册码和一个未用的重置码，互相校验不通过、互不消费。"""
        phone = "13921810002"
        register_result = send_verification_code(phone, client_ip="127.0.0.1", scene="register")
        reset_result = send_verification_code(phone, client_ip="127.0.0.1", scene="reset")

        with self.assertRaises(HTTPException):
            verify_verification_code(phone, reset_result["dev_code"], scene="register")
        with self.assertRaises(HTTPException):
            verify_verification_code(phone, register_result["dev_code"], scene="reset")

        # 用对场景才能通过，且两个验证码依然独立有效
        self.assertEqual(verify_verification_code(phone, register_result["dev_code"], scene="register"), phone)
        self.assertEqual(verify_verification_code(phone, reset_result["dev_code"], scene="reset"), phone)

    def test_aliyun_provider_uses_local_verification(self):
        os.environ["SMS_PROVIDER"] = "aliyun"
        phone = "13921810003"
        with patch("service.phone_verification_service._send_by_aliyun") as send:
            result = send_register_code(phone, client_ip="127.0.0.1")
        code = send.call_args.args[1]
        self.assertEqual(result["provider"], "aliyun")
        self.assertIsNone(result["dev_code"])
        self.assertEqual(verify_register_code(phone, code), phone)

    def test_aliyun_failure_does_not_cache_code(self):
        os.environ["SMS_PROVIDER"] = "aliyun"
        phone = "13921810004"
        with patch("service.phone_verification_service._send_by_aliyun", side_effect=RuntimeError("send failed")):
            with self.assertRaises(RuntimeError):
                send_register_code(phone, client_ip="127.0.0.1")
        self.assertIsNone(verification_cache.get(("sms_register", phone)))


class SmsLimitsTest(unittest.TestCase):
    """发送、全站总量、校验三处限制。每个用例用独立的限流器，互不串扰。"""

    KEYS = (
        "SMS_PROVIDER", "SMS_EXPOSE_DEV_CODE", "SMS_CODE_PHONE_LIMIT", "SMS_CODE_DAILY_LIMIT", "SMS_CODE_IP_LIMIT",
        "SMS_CODE_GLOBAL_HOURLY_LIMIT", "SMS_CODE_GLOBAL_DAILY_LIMIT", "SMS_CODE_VERIFY_LIMIT",
    )

    def setUp(self):
        from utils import rate_limit

        self._saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.update({
            "SMS_PROVIDER": "console", "SMS_EXPOSE_DEV_CODE": "1",
            "SMS_CODE_PHONE_LIMIT": "100", "SMS_CODE_DAILY_LIMIT": "100", "SMS_CODE_IP_LIMIT": "100",
            "SMS_CODE_GLOBAL_HOURLY_LIMIT": "0", "SMS_CODE_GLOBAL_DAILY_LIMIT": "0",
        })
        os.environ.pop("SMS_CODE_VERIFY_LIMIT", None)
        # 用纯内存限流器（不连 Redis），并保证每个用例从零开始
        limiter = rate_limit.FixedWindowRateLimiter(namespace=f"t{id(self)}")
        limiter._redis.get_client = lambda: None
        self._patch = patch.object(rate_limit, "rate_limiter", limiter)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def assertTooMany(self, ctx):
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)

    def test_global_hourly_cap_blocks_different_phones_and_ips(self):
        os.environ["SMS_CODE_GLOBAL_HOURLY_LIMIT"] = "3"
        for i in range(3):
            send_register_code(f"1392181100{i}", client_ip=f"10.0.0.{i}")
        with self.assertRaises(HTTPException) as ctx:
            send_register_code("13921811009", client_ip="10.0.0.99")
        self.assertTooMany(ctx)

    def test_global_daily_cap_blocks_too(self):
        os.environ["SMS_CODE_GLOBAL_DAILY_LIMIT"] = "1"
        send_register_code("13921811101", client_ip="10.0.1.1")
        with self.assertRaises(HTTPException) as ctx:
            send_register_code("13921811102", client_ip="10.0.1.2")
        self.assertTooMany(ctx)

    def test_zero_turns_the_global_cap_off(self):
        for i in range(5):
            send_register_code(f"1392181120{i}", client_ip=f"10.0.2.{i}")

    def test_blocked_ip_does_not_burn_the_victims_phone_cooldown(self):
        os.environ["SMS_CODE_IP_LIMIT"] = "1"
        os.environ["SMS_CODE_PHONE_LIMIT"] = "1"
        send_register_code("13921811301", client_ip="10.0.3.1")          # 占满这个 IP 的额度
        with self.assertRaises(HTTPException):
            send_register_code("13921811302", client_ip="10.0.3.1")      # 被 IP 限制拦下
        # 受害号码没被上面那次消耗冷却：换个 IP 还能立刻发
        self.assertEqual(send_register_code("13921811302", client_ip="10.0.3.2")["message"], "验证码已发送")

    def test_verify_attempts_are_capped_per_phone(self):
        os.environ["SMS_CODE_VERIFY_LIMIT"] = "4"
        phone = "13921811401"
        code = send_register_code(phone, client_ip="10.0.4.1")["dev_code"]
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(4):
            with self.assertRaises(HTTPException) as ctx:
                verify_register_code(phone, wrong, consume=False)
            self.assertEqual(ctx.exception.status_code, 400)
        # 第 5 次起，连正确的验证码也先被频率限制拦住
        with self.assertRaises(HTTPException) as ctx:
            verify_register_code(phone, code)
        self.assertTooMany(ctx)

    def test_reset_flow_two_step_verify_stays_within_default_limit(self):
        phone = "13921811501"
        code = send_verification_code(phone, client_ip="10.0.5.1", scene="reset")["dev_code"]
        # 重置密码会先"只校验"再"校验并消费"，共 2 次，默认上限 10 次足够
        self.assertEqual(verify_verification_code(phone, code, scene="reset", consume=False), phone)
        self.assertEqual(verify_verification_code(phone, code, scene="reset", consume=True), phone)


if __name__ == "__main__":
    unittest.main()
