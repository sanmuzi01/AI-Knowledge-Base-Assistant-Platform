import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from service.request_context_middleware import RequestContextMiddleware


def make_app():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


class RequestContextMiddlewareTest(unittest.TestCase):
    def test_request_id_is_added_to_response(self):
        client = TestClient(make_app())
        response = client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("X-Request-ID"))
        self.assertTrue(response.headers.get("X-Process-Time"))

    def test_valid_request_id_is_preserved(self):
        client = TestClient(make_app())
        response = client.get("/ping", headers={"X-Request-ID": "web-req-123456"})

        self.assertEqual(response.headers["X-Request-ID"], "web-req-123456")

    def test_invalid_request_id_is_replaced(self):
        client = TestClient(make_app())
        response = client.get("/ping", headers={"X-Request-ID": "../bad"})

        self.assertNotEqual(response.headers["X-Request-ID"], "../bad")


if __name__ == "__main__":
    unittest.main()

