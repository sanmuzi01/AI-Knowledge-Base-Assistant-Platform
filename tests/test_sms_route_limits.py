"""短信相关路由的频率限制：注册发码（查库前）、重置密码提交（按 IP）。

走真实 FastAPI 应用；限流器换成每个用例独立的内存实例，不依赖 Redis，也不受别的用例影响。
"""

import os
import unittest
from unittest.mock import patch

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class SmsRouteLimitsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()

    def setUp(self):
        from utils import rate_limit

        self._env = {k: os.environ.get(k) for k in ("SMS_CODE_IP_LIMIT", "RESET_PASSWORD_RATE_LIMIT")}
        limiter = rate_limit.FixedWindowRateLimiter(namespace=f"sr{id(self)}")
        limiter._redis.get_client = lambda: None
        self._patch = patch.object(rate_limit, "rate_limiter", limiter)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_register_code_probe_is_limited_even_when_no_sms_is_sent(self):
        os.environ["SMS_CODE_IP_LIMIT"] = "2"
        # 号码格式正确但库里不一定有：这里只关心第 3 次起被限流，而不是被"手机号已注册"之类的业务错误放过
        statuses = [
            self.client.post("/user/register/sms-code", json={"phone": "13800000001"}).status_code for _ in range(3)
        ]
        self.assertNotEqual(statuses[0], 429)
        self.assertEqual(statuses[2], 429, statuses)

    def test_reset_password_submit_is_limited_per_ip(self):
        os.environ["RESET_PASSWORD_RATE_LIMIT"] = "2"
        body = {"phone": "13800000002", "sms_code": "123456", "new_password": "Passw0rd!x"}
        statuses = [self.client.post("/user/reset-password", json=body).status_code for _ in range(3)]
        self.assertNotEqual(statuses[0], 429)
        self.assertEqual(statuses[2], 429, statuses)

    def test_limit_response_carries_retry_after(self):
        os.environ["RESET_PASSWORD_RATE_LIMIT"] = "1"
        body = {"phone": "13800000003", "sms_code": "123456", "new_password": "Passw0rd!x"}
        self.client.post("/user/reset-password", json=body)
        r = self.client.post("/user/reset-password", json=body)
        self.assertEqual(r.status_code, 429)
        self.assertGreaterEqual(int(r.headers["Retry-After"]), 1)


if __name__ == "__main__":
    unittest.main()
