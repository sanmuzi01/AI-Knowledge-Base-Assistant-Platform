import os
import unittest

from fastapi import HTTPException

from service.phone_verification_service import send_register_code, verify_register_code


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


if __name__ == "__main__":
    unittest.main()
