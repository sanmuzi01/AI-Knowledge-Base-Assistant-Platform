import os
import unittest

import requests

from service.http_resilience import CircuitBreaker, CircuitOpenError, request_with_retry


def _response(status_code: int) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = b"{}"
    return response


class HttpResilienceTest(unittest.TestCase):
    def setUp(self):
        os.environ["HTTP_CLIENT_MAX_RETRIES"] = "2"
        os.environ["HTTP_CLIENT_RETRY_BASE_SECONDS"] = "0"
        os.environ["HTTP_CIRCUIT_FAILURE_THRESHOLD"] = "20"

    def test_retries_retryable_status_then_success(self):
        calls = {"count": 0}

        def sender(timeout):
            calls["count"] += 1
            return _response(503 if calls["count"] == 1 else 200)

        response = request_with_retry(
            service_name="unit_retry_success",
            sender=sender,
            timeout_env="UNIT_TIMEOUT",
            default_timeout=1,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls["count"], 2)

    def test_circuit_breaker_opens_after_failures(self):
        breaker = CircuitBreaker()
        os.environ["HTTP_CIRCUIT_FAILURE_THRESHOLD"] = "2"
        os.environ["HTTP_CIRCUIT_COOLDOWN_SECONDS"] = "60"

        breaker.record_failure("unit")
        breaker.record_failure("unit")

        with self.assertRaises(CircuitOpenError):
            breaker.before_call("unit")


if __name__ == "__main__":
    unittest.main()
