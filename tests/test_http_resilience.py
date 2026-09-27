import os
import unittest
from unittest.mock import patch

import requests

from service.http_resilience import CircuitBreaker, CircuitOpenError, request_with_retry


class _FakeRedis:
    """极简的 redis.Redis 替身：只实现 CircuitBreaker 用到的那几个命令，
    没有真实 Redis/fakeredis 依赖时也能验证"Redis 优先"这条路径的逻辑本身
    （key 怎么设、TTL 怎么用、stats() 怎么拼），不是验证 Redis 服务器本身。"""

    def __init__(self):
        self.store = {}
        self.sets = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = str(value)

    def incr(self, key):
        self.store[key] = str(int(self.store.get(key, 0)) + 1)
        return int(self.store[key])

    def expire(self, key, seconds):
        pass  # 假实现不模拟真实过期，测试里不依赖 TTL 自动生效

    def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def smembers(self, key):
        return self.sets.get(key, set())


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


class RedisBackedCircuitBreakerTest(unittest.TestCase):
    """Phase 4：多实例共享熔断（docs/project-status.md 之前记录的风险项）。
    本机没有真实 Redis，用 _FakeRedis 验证"Redis 优先"这条路径本身的逻辑
    （key/TTL/stats 拼法），不是验证 Redis 服务器——那部分交给生产环境的
    多实例联调验证。"""

    def setUp(self):
        os.environ["HTTP_CIRCUIT_FAILURE_THRESHOLD"] = "2"
        os.environ["HTTP_CIRCUIT_COOLDOWN_SECONDS"] = "60"
        self.fake_redis = _FakeRedis()
        self.breaker = CircuitBreaker()
        # 直接把假客户端塞进 RedisClientManager 的缓存槛位（`_client`），走它真实的
        # `get_client()`/`mark_failed()` 逻辑——不是整个方法打桩，这样 mark_failed()
        # 之后 get_client() 真的会返回 None（受 `_next_retry_at` 约束），
        # test_redis_exception_falls_back_to_memory 才测的是真实的降级路径。
        self.breaker._redis._client = self.fake_redis

    def test_opens_after_threshold_via_redis(self):
        self.breaker.record_failure("redis-svc")
        self.breaker.record_failure("redis-svc")
        with self.assertRaises(CircuitOpenError):
            self.breaker.before_call("redis-svc")
        self.assertIn("circuit:redis-svc:opened_until", self.fake_redis.store)

    def test_stays_closed_below_threshold(self):
        self.breaker.record_failure("redis-svc2")
        self.breaker.before_call("redis-svc2")  # 没到阈值，不应该抛异常

    def test_record_success_clears_state(self):
        self.breaker.record_failure("redis-svc3")
        self.breaker.record_failure("redis-svc3")
        self.breaker.record_success("redis-svc3")
        self.breaker.before_call("redis-svc3")  # 清过了，不应该抛异常
        self.assertNotIn("circuit:redis-svc3:opened_until", self.fake_redis.store)

    def test_stats_reflects_redis_state(self):
        self.breaker.record_failure("redis-svc4")
        self.breaker.record_failure("redis-svc4")
        stats = self.breaker.stats()
        self.assertEqual(stats["redis-svc4"]["failures"], 2)
        self.assertTrue(stats["redis-svc4"]["open"])

    def test_redis_exception_falls_back_to_memory(self):
        with patch.object(self.fake_redis, "incr", side_effect=RuntimeError("boom")):
            self.breaker.record_failure("redis-svc5")
        self.breaker.record_failure("redis-svc5")  # 这一次 Redis 客户端已经被标记失效，走内存
        with self.assertRaises(CircuitOpenError):
            self.breaker.before_call("redis-svc5")


if __name__ == "__main__":
    unittest.main()
