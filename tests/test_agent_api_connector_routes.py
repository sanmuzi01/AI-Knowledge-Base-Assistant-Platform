"""企业接口连接器路由的端到端测试：真实 TestClient + 真 JWT + 真 DB，
覆盖创建/列表/启停/删除的正常路径，以及跨用户越权应该 404 不该泄露存在性。

Step 0 安全收口后，创建连接器默认只留给管理员（见 FasdtApi/agent.py 的
create_api_connector）：alice 在这个类里全程被 admin_env 标成管理员，才能走通
创建/列表/启停/删除这条正常路径；bob 全程保持普通用户身份，专门验证默认关闭。
"""
import unittest
from unittest.mock import patch

from service.web_crawler_service import CrawlerError
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class ApiConnectorRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.alice = rc.create_user("apirt-alice")
        cls.bob = rc.create_user("apirt-bob")
        # 本类专门测连接器 CRUD 本身（创建/列表/启停/删除、跨用户越权），不是测
        # "谁能创建"的权限策略——那条策略单独有 test_normal_user_cannot_create_connector_
        # by_default 覆盖，用没被标管理员的 bob。这里把 alice 标成管理员，让她能走通
        # 正常路径。
        cls._admin_patch = rc.admin_env(cls.alice["name"])
        cls._admin_patch.__enter__()
        r = cls.client.post("/agent", json={"name": f"apirt-agent-{cls.alice['id']}"}, headers=cls.alice["headers"])
        assert r.status_code == 200, r.text
        cls.agent_id = r.json()["agent_id"]

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM agent_api_connector WHERE agent_id=:a"), {"a": cls.agent_id})
            db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": cls.agent_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        try:
            cls._admin_patch.__exit__(None, None, None)
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def _create(self):
        with patch("service.tools.http_connector_service.validate_crawl_url", lambda u: u):
            return self.client.post(
                f"/agent/{self.agent_id}/api-connectors",
                headers=self.alice["headers"],
                json={
                    "name": "query_order",
                    "description": "查询订单状态",
                    "url": "https://api.example.com/orders",
                    "method": "GET",
                    "param_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}},
                },
            )

    def test_create_list_toggle_delete(self):
        r = self._create()
        self.assertEqual(r.status_code, 200, r.text)
        connector_id = r.json()["id"]
        self.assertFalse("headers" in r.json())

        r = self.client.get(f"/agent/{self.agent_id}/api-connectors", headers=self.alice["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([c["id"] for c in r.json()], [connector_id])

        r = self.client.patch(
            f"/agent/api-connectors/{connector_id}",
            headers=self.alice["headers"], json={"is_enabled": False},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["is_enabled"])

        r = self.client.delete(f"/agent/api-connectors/{connector_id}", headers=self.alice["headers"])
        self.assertEqual(r.status_code, 200, r.text)

        r = self.client.get(f"/agent/{self.agent_id}/api-connectors", headers=self.alice["headers"])
        self.assertEqual(r.json(), [])

    def test_invalid_url_rejected(self):
        with patch("service.tools.http_connector_service.validate_crawl_url",
                   side_effect=CrawlerError("不允许抓取内网")):
            r = self.client.post(
                f"/agent/{self.agent_id}/api-connectors",
                headers=self.alice["headers"],
                json={"name": "bad", "description": "desc", "url": "http://169.254.169.254/", "method": "GET"},
            )
        self.assertEqual(r.status_code, 400, r.text)

    def test_cross_user_access_is_not_found_not_forbidden(self):
        r = self._create()
        connector_id = r.json()["id"]

        r = self.client.get(f"/agent/{self.agent_id}/api-connectors", headers=self.bob["headers"])
        self.assertEqual(r.status_code, 404)

        r = self.client.patch(
            f"/agent/api-connectors/{connector_id}",
            headers=self.bob["headers"], json={"is_enabled": False},
        )
        self.assertEqual(r.status_code, 404)

        r = self.client.delete(f"/agent/api-connectors/{connector_id}", headers=self.bob["headers"])
        self.assertEqual(r.status_code, 404)

    def test_normal_user_cannot_create_connector_by_default(self):
        """Step 0 收口：bob 全程不是管理员，也没开 FEATURE_USER_API_CONNECTORS，
        自己给（自己拥有的）agent 配连接器应该直接 403，不应该走到 URL 校验那一步。"""
        r = self.client.post("/agent", json={"name": f"apirt-bob-agent-{self.bob['id']}"},
                              headers=self.bob["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        bob_agent_id = r.json()["agent_id"]
        try:
            with patch("service.tools.http_connector_service.validate_crawl_url", lambda u: u):
                r = self.client.post(
                    f"/agent/{bob_agent_id}/api-connectors",
                    headers=self.bob["headers"],
                    json={"name": "query_order", "description": "查询订单状态",
                          "url": "https://api.example.com/orders", "method": "GET"},
                )
            self.assertEqual(r.status_code, 403, r.text)
        finally:
            from sqlalchemy import text
            from models.init_db import SessionLocal
            db = SessionLocal()
            try:
                db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": bob_agent_id})
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()

    def test_feature_flag_lets_normal_user_create_connector(self):
        """开了 FEATURE_USER_API_CONNECTORS 之后，普通用户也能自己创建——这个开关本身
        要生效，不只是"默认关闭"生效。"""
        r = self.client.post("/agent", json={"name": f"apirt-bob-flag-agent-{self.bob['id']}"},
                              headers=self.bob["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        bob_agent_id = r.json()["agent_id"]
        try:
            with patch("service.tools.http_connector_service.validate_crawl_url", lambda u: u), \
                 patch.dict("os.environ", {"FEATURE_USER_API_CONNECTORS": "true"}):
                r = self.client.post(
                    f"/agent/{bob_agent_id}/api-connectors",
                    headers=self.bob["headers"],
                    json={"name": "query_order", "description": "查询订单状态",
                          "url": "https://api.example.com/orders", "method": "GET"},
                )
            self.assertEqual(r.status_code, 200, r.text)
        finally:
            from sqlalchemy import text
            from models.init_db import SessionLocal
            db = SessionLocal()
            try:
                db.execute(text("DELETE FROM agent_api_connector WHERE agent_id=:a"), {"a": bob_agent_id})
                db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": bob_agent_id})
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
