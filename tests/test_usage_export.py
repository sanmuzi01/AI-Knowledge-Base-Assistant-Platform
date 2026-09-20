"""用量报表 CSV 导出（管理员用量/日志、用户个人用量）路由级回归测试。

真实 FastAPI 应用 + 真实 JWT + 真实 DB。
"""
import unittest

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class UsageExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.user = rc.create_user("rt-export-user")
        cls.admin = rc.create_user("rt-export-admin")
        cls._admin_env = rc.admin_env(cls.admin["name"])
        cls._admin_env.start()

    @classmethod
    def tearDownClass(cls):
        cls._admin_env.stop()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def test_admin_usage_export_returns_csv(self):
        resp = self.client.get("/admin/usage/export?days=7", headers=self.admin["headers"])
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers["content-type"])
        self.assertIn("attachment", resp.headers["content-disposition"])
        text = resp.content.decode("utf-8-sig")
        self.assertIn("汇总", text)
        self.assertIn("每日明细", text)
        self.assertIn("Top用户", text)

    def test_admin_logs_export_returns_csv(self):
        resp = self.client.get("/admin/logs/export?days=7", headers=self.admin["headers"])
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers["content-type"])
        text = resp.content.decode("utf-8-sig")
        self.assertIn("ID", text)
        self.assertIn("状态码", text)

    def test_non_admin_cannot_export_admin_usage(self):
        resp = self.client.get("/admin/usage/export", headers=self.user["headers"])
        self.assertEqual(resp.status_code, 403)

    def test_non_admin_cannot_export_admin_logs(self):
        resp = self.client.get("/admin/logs/export", headers=self.user["headers"])
        self.assertEqual(resp.status_code, 403)

    def test_user_usage_export_returns_csv(self):
        resp = self.client.get("/user/usage/export", headers=self.user["headers"])
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers["content-type"])
        self.assertIn("attachment", resp.headers["content-disposition"])
        text = resp.content.decode("utf-8-sig")
        self.assertIn("套餐概况", text)
        self.assertIn("本月运行明细", text)

    def test_export_requires_login(self):
        resp = self.client.get("/user/usage/export")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
