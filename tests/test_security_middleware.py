import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.security_middleware import SecurityHeadersMiddleware


def make_app():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.post("/echo")
    def echo(payload: dict):
        return payload

    return app


class SecurityMiddlewareTest(unittest.TestCase):
    def test_security_headers_are_added(self):
        client = TestClient(make_app())
        response = client.post("/echo", json={"ok": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("strict-origin", response.headers["Referrer-Policy"])

    def test_large_request_body_is_rejected(self):
        with patch.dict(os.environ, {"MAX_REQUEST_BODY_BYTES": "10"}, clear=False):
            client = TestClient(make_app())
            response = client.post("/echo", json={"content": "x" * 50})

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "请求体过大")


if __name__ == "__main__":
    unittest.main()
