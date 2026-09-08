import os
import unittest
from unittest.mock import patch

from service.web_crawler_service import CrawlerError, crawl_url_to_markdown, validate_crawl_url


class _FakeResponse:
    status_code = 200
    is_redirect = False
    url = "https://example.com/docs/page"
    encoding = "utf-8"
    apparent_encoding = "utf-8"
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=16384):
        yield (
            b"<html><head><title>Test Page</title><script>bad()</script></head>"
            b"<body><h1>Hello</h1><p>This is useful crawler content for knowledge base.</p></body></html>"
        )


class _JsonLdResponse(_FakeResponse):
    def iter_content(self, chunk_size=16384):
        yield (
            b'<html><head><title>Shell Page</title>'
            b'<script type="application/ld+json">'
            b'{"@type":"Article","headline":"JSON Article","articleBody":"This article body is rendered from structured data and should be indexed."}'
            b"</script></head><body><div>Short</div></body></html>"
        )


class WebCrawlerServiceTestCase(unittest.TestCase):
    def setUp(self):
        os.environ["APP_ENV"] = "production"
        os.environ["CRAWLER_MIN_TEXT_LENGTH"] = "10"
        os.environ.pop("CRAWLER_ALLOW_PRIVATE_NETWORK", None)
        os.environ.pop("CRAWLER_ALLOW_PRIVATE_DNS", None)

    @patch("service.web_crawler_service.socket.getaddrinfo")
    def test_private_address_rejected(self, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("127.0.0.1", 0))]

        with self.assertRaises(CrawlerError):
            validate_crawl_url("http://localhost/admin")

    @patch("service.web_crawler_service.socket.getaddrinfo")
    def test_development_allows_proxy_private_dns_for_domain(self, getaddrinfo):
        os.environ["APP_ENV"] = "development"
        getaddrinfo.return_value = [(None, None, None, None, ("198.18.0.131", 0))]

        self.assertEqual(validate_crawl_url("https://example.com/a"), "https://example.com/a")

    @patch("service.web_crawler_service.socket.getaddrinfo")
    def test_url_without_scheme_defaults_to_https(self, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", 0))]

        self.assertEqual(validate_crawl_url("example.com/a"), "https://example.com/a")

    @patch("service.web_crawler_service.socket.getaddrinfo")
    @patch("service.web_crawler_service.requests.Session.get")
    def test_html_is_converted_to_markdown(self, session_get, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", 0))]
        session_get.return_value = _FakeResponse()

        result = crawl_url_to_markdown("https://example.com/docs/page")

        self.assertEqual(result["file_type"], "md")
        self.assertTrue(result["file_name"].endswith(".md"))
        content = result["content"].decode("utf-8")
        self.assertIn("# Test Page", content)
        self.assertIn("This is useful crawler content", content)
        self.assertNotIn("bad()", content)

    @patch("service.web_crawler_service.socket.getaddrinfo")
    @patch("service.web_crawler_service.requests.Session.get")
    def test_jsonld_article_body_is_indexed(self, session_get, getaddrinfo):
        getaddrinfo.return_value = [(None, None, None, None, ("93.184.216.34", 0))]
        session_get.return_value = _JsonLdResponse()

        result = crawl_url_to_markdown("https://example.com/docs/page")

        content = result["content"].decode("utf-8")
        self.assertIn("JSON Article", content)
        self.assertIn("structured data and should be indexed", content)


if __name__ == "__main__":
    unittest.main()
