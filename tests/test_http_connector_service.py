"""企业接口连接器（AgentApiConnector）CRUD 的回归测试。

validate_crawl_url 会做真实 DNS 解析，测试里一律 mock 掉（跟
tests/test_widget_p2_connectors.py 的既有约定一致），不依赖网络。
"""
import json
import unittest
from unittest.mock import patch

from service.exceptions import InvalidInput, NotFound
from service.tools import http_connector_service as svc
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


class ValidationTest(unittest.TestCase):
    def setUp(self):
        patcher = patch("service.tools.http_connector_service.validate_crawl_url", lambda u: u)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_rejects_invalid_name(self):
        with self.assertRaises(InvalidInput):
            svc._validate("1bad-name", "desc", "https://api.example.com", "GET", {})

    def test_rejects_empty_description(self):
        with self.assertRaises(InvalidInput):
            svc._validate("query_order", "", "https://api.example.com", "GET", {})

    def test_rejects_bad_method(self):
        with self.assertRaises(InvalidInput):
            svc._validate("query_order", "desc", "https://api.example.com", "DELETE", {})

    def test_rejects_blocked_url(self):
        with patch("service.tools.http_connector_service.validate_crawl_url",
                   side_effect=svc.CrawlerError("不允许抓取内网")):
            with self.assertRaises(InvalidInput):
                svc._validate("query_order", "desc", "http://169.254.169.254/", "GET", {})

    def test_accepts_valid_input(self):
        svc._validate("query_order", "查询订单状态", "https://api.example.com/orders", "get", {
            "type": "object", "properties": {"order_id": {"type": "string"}},
        })  # 不抛异常即通过


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class LifecycleDbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.init_db import SessionLocal, Agent

        cls.user = rc.create_user("apiconn")
        db = SessionLocal()
        try:
            agent = Agent(user_id=cls.user["id"], name="conn-agent")
            db.add(agent)
            db.commit()
            cls.agent_id = agent.id
        finally:
            db.close()

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
        rc.cleanup()

    def setUp(self):
        patcher = patch("service.tools.http_connector_service.validate_crawl_url", lambda u: u)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_create_list_toggle_delete_and_headers_roundtrip(self):
        from models.init_db import SessionLocal

        db = SessionLocal()
        try:
            created = svc.create_connector(
                db, self.user["id"], self.agent_id,
                name="query_order", description="查询订单状态，输入订单号",
                url="https://api.example.com/orders", method="get",
                headers={"Authorization": "Bearer secret-token"},
                param_schema={"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
                static_query={"region": "cn"},
            )
            self.assertEqual(created["name"], "query_order")
            self.assertEqual(created["method"], "GET")
            self.assertTrue(created["has_headers"])
            self.assertNotIn("headers", created, "接口返回不应该带明文 headers")
            connector_id = created["id"]

            # 加密确实生效：数据库里存的不是明文
            from models.agent_api_connector_dao import get_owned_connector
            row = get_owned_connector(db, self.user["id"], connector_id)
            self.assertNotIn("secret-token", row.headers_encrypted)
            from utils.crypto import decrypt
            self.assertEqual(json.loads(decrypt(row.headers_encrypted))["Authorization"], "Bearer secret-token")

            listed = svc.list_connectors(db, self.user["id"], self.agent_id)
            self.assertEqual([c["id"] for c in listed], [connector_id])

            disabled = svc.set_connector_enabled(db, self.user["id"], connector_id, False)
            self.assertFalse(disabled["is_enabled"])

            from models.agent_api_connector_dao import list_connectors_by_agent
            self.assertEqual(list_connectors_by_agent(db, self.agent_id, enabled_only=True), [])

            svc.delete_connector(db, self.user["id"], connector_id)
            self.assertEqual(svc.list_connectors(db, self.user["id"], self.agent_id), [])
        finally:
            db.close()

    def test_operations_on_unowned_connector_raise(self):
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            with self.assertRaises(NotFound):
                svc.set_connector_enabled(db, self.user["id"], 999999, True)
            with self.assertRaises(NotFound):
                svc.delete_connector(db, self.user["id"], 999999)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
