"""P2 外部数据源连接器：http / web_page / knowledge_base。

外部调用（HTTP、爬虫、RAG 检索）全部打桩，只验证连接器自己的行为：
config 校验、SSRF 校验被调用、响应体裁剪、网页变化检测、按用户隔离。
"""

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from service.exceptions import AppError

from service.widgets.connectors import CONNECTORS
from service.widgets.context import WidgetRunContext


def _ctx(db=None, widget_id=None):
    return WidgetRunContext(user_id=42, now=datetime(2026, 3, 1, 8, 0, 0), db=db, widget_id=widget_id)


class _Resp:
    def __init__(self, content=b"", status=200, encoding="utf-8"):
        self.content = content
        self.status_code = status
        self.encoding = encoding

    def raise_for_status(self):
        return None


class HttpConnectorTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conn = CONNECTORS.get("http")

    def test_validate_config(self):
        self.assertTrue(self.conn.validate_config({}))
        self.assertTrue(self.conn.validate_config({"url": "ftp://x"}))
        self.assertTrue(self.conn.validate_config({"url": "http://x", "method": "DELETE"}))
        self.assertEqual(self.conn.validate_config({"url": "https://api.example.com/x"}), [])

    async def test_fetch_parses_json_and_checks_ssrf(self):
        calls = {}

        def fake_validate(url):
            calls["validated"] = url
            return url

        async def fake_request(**kwargs):
            calls["service_name"] = kwargs["service_name"]
            return _Resp(content=b'{"rows": [{"date": "2026-01-01", "value": 5}]}')

        with patch("service.web_crawler_service.validate_crawl_url", fake_validate), \
             patch("service.http_resilience.async_request_with_retry", fake_request):
            out = await self.conn.fetch(_ctx(), {"url": "https://api.example.com/data"})

        self.assertEqual(calls["validated"], "https://api.example.com/data")
        self.assertTrue(calls["service_name"].startswith("widget_http:"))
        self.assertEqual(out["rows"], [{"date": "2026-01-01", "value": 5}])
        self.assertEqual(out["_meta"]["status"], 200)

    async def test_fetch_rejects_oversized_response(self):
        with patch("service.web_crawler_service.validate_crawl_url", lambda u: u), \
             patch("service.http_resilience.async_request_with_retry",
                   lambda **kw: _async(_Resp(content=b"x" * (2 * 1024 * 1024)))):
            with self.assertRaises(AppError):
                await self.conn.fetch(_ctx(), {"url": "https://api.example.com/big"})

    async def test_fetch_blocked_url_becomes_friendly_error(self):
        from service.web_crawler_service import CrawlerError

        def boom(url):
            raise CrawlerError("不允许抓取内网")

        with patch("service.web_crawler_service.validate_crawl_url", boom):
            with self.assertRaises(AppError) as ctx:
                await self.conn.fetch(_ctx(), {"url": "http://169.254.169.254/"})
        self.assertIn("不允许", str(ctx.exception))


class WebPageConnectorTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conn = CONNECTORS.get("web_page")

    def test_validate_config(self):
        self.assertTrue(self.conn.validate_config({}))
        self.assertTrue(self.conn.validate_config({"url": "https://x", "mode": "weird"}))
        self.assertEqual(self.conn.validate_config({"url": "https://x", "mode": "monitor"}), [])

    async def test_fetch_text_mode(self):
        doc = {"url": "https://news.example.com/a", "title": "标题", "content": "正文内容".encode("utf-8")}
        with patch("service.web_crawler_service.crawl_url_to_markdown", lambda u: doc):
            out = await self.conn.fetch(_ctx(), {"url": "https://news.example.com/a", "mode": "text"})
        self.assertEqual(out["title"], "标题")
        self.assertEqual(out["text"], "正文内容")
        self.assertTrue(out["content_hash"])
        self.assertFalse(out["changed"])

    async def test_monitor_mode_detects_change_against_last_point(self):
        doc = {"url": "https://x", "title": "", "content": b"new-body"}
        prev_payload = '{"result": {"content_hash": "OLDHASH"}}'
        fake_point = SimpleNamespace(payload_json=prev_payload)

        with patch("service.web_crawler_service.crawl_url_to_markdown", lambda u: doc), \
             patch("models.user_widget_async_dao.latest_data_point_async",
                   new=lambda db, wid: _async(fake_point)):
            out = await self.conn.fetch(_ctx(db=object(), widget_id=7), {"url": "https://x", "mode": "monitor"})

        self.assertTrue(out["changed"])
        self.assertEqual(out["previous_hash"], "OLDHASH")
        self.assertFalse(out["first_seen"])


class KnowledgeBaseConnectorTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conn = CONNECTORS.get("knowledge_base")

    def test_validate_config(self):
        self.assertTrue(self.conn.validate_config({}))
        self.assertTrue(self.conn.validate_config({"agent_id": 1}))  # 缺 query
        self.assertTrue(self.conn.validate_config({"agent_id": 1, "query": "x", "top_k": 99}))
        self.assertEqual(self.conn.validate_config({"agent_id": 3, "query": "合同风险", "top_k": 5}), [])

    async def test_fetch_passes_user_scope_to_rag_entrypoint(self):
        seen = {}

        def fake_search(user_id, agent_id, query, top_k):
            seen.update(user_id=user_id, agent_id=agent_id, query=query, top_k=top_k)
            return [{"content": "命中片段", "score": 0.9, "file_name": "a.pdf", "knowledge_id": 11}]

        with patch("service.rag.widget_search.search_for_widget", fake_search):
            out = await self.conn.fetch(_ctx(db=object()), {"agent_id": 3, "query": "合同风险", "top_k": 4})

        self.assertEqual(seen, {"user_id": 42, "agent_id": 3, "query": "合同风险", "top_k": 4})
        self.assertEqual(out["hit_count"], 1)
        self.assertEqual(out["rows"][0]["file_name"], "a.pdf")

    async def test_permission_error_becomes_runtime_error(self):
        def denies(*a, **k):
            raise PermissionError("知识库不存在或无权访问")

        with patch("service.rag.widget_search.search_for_widget", denies):
            with self.assertRaises(AppError):
                await self.conn.fetch(_ctx(db=object()), {"agent_id": 9, "query": "x", "top_k": 3})


def _async(value):
    async def _coro(*a, **k):
        return value
    return _coro()


if __name__ == "__main__":
    unittest.main()
