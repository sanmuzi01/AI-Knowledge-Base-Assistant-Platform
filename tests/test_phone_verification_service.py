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


if __name__ == "__main__":
    unittest.main()
