import os
import unittest
from unittest.mock import patch

from service.knowledge_diagnostics_service import build_knowledge_recommendations, check_crawl_urls


class KnowledgeDiagnosticsServiceTest(unittest.TestCase):
    def setUp(self):
        os.environ["APP_ENV"] = "production"
        os.environ.pop("CRAWLER_ALLOW_PRIVATE_NETWORK", None)
        os.environ.pop("CRAWLER_ALLOW_PRIVATE_DNS", None)

    def test_recommendations_explain_missing_embedding(self):
        items = build_knowledge_recommendations(
            has_embedding_model=False,
            done_docs=0,
            failed_docs=0,
            failed_tasks=0,
            working_docs=0,
            queued_tasks=0,
            browser_fallback=False,
        )

        self.assertEqual(items[0]["key"], "embedding-model")
        self.assertEqual(items[0]["level"], "danger")
        self.assertIn("no-searchable-doc", {item["key"] for item in items})

    @patch("service.web_crawler_service.socket.getaddrinfo")
    def test_crawl_check_reports_allowed_and_blocked_urls(self, getaddrinfo):
        def fake_getaddrinfo(hostname, *args, **kwargs):
            address = "127.0.0.1" if hostname == "localhost" else "93.184.216.34"
            return [(None, None, None, None, (address, 0))]

        getaddrinfo.side_effect = fake_getaddrinfo
        result = check_crawl_urls(["example.com/a", "http://localhost/admin"])

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["ok_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["items"][0]["normalized_url"], "https://example.com/a")
        self.assertFalse(result["items"][1]["ok"])


if __name__ == "__main__":
    unittest.main()
