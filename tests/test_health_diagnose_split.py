"""/health 和 /system/diagnose 的拆分：之前 /health 完全公开地返回数据库连接池、
缓存/限流后端、熔断器状态这些内部运行细节，任何匿名请求都能看到——对研判
"这套系统好不好打"是有效的踩点信息。现在 /health 只回 {"ok": bool}，完整诊断
挪到需要登录的 /system/diagnose。这组测试锁定这个边界。
"""
import unittest

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class HealthDiagnoseSplitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.user = rc.create_user("healthsplit")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def test_health_is_public_and_minimal(self):
        r = self.client.get("/health")  # 不带 Authorization
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("ok", body)
        self.assertIsInstance(body["ok"], bool)
        # 之前会暴露的内部细节，现在一个都不该出现在公开端点里
        for leaked_field in ("database", "cache", "limits", "resilience", "tasks", "checks", "config"):
            self.assertNotIn(leaked_field, body, f"{leaked_field} 不应该出现在公开的 /health 里")

    def test_diagnose_requires_login(self):
        r = self.client.get("/system/diagnose")  # 不带 Authorization
        self.assertEqual(r.status_code, 401)

    def test_diagnose_returns_full_payload_when_logged_in(self):
        r = self.client.get("/system/diagnose", headers=self.user["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        for expected_field in ("ok", "checks", "database", "cache", "limits", "resilience", "tasks", "config"):
            self.assertIn(expected_field, body)
        self.assertIn("pool", body["database"])


if __name__ == "__main__":
    unittest.main()
