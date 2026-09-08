import os
import unittest
from unittest.mock import patch

from utils.redis_client import RedisClientManager


class _FailingRedisFactory:
    @staticmethod
    def from_url(*args, **kwargs):
        raise RuntimeError("redis down")


class RedisClientManagerTest(unittest.TestCase):
    def test_missing_url_disables_redis_without_error(self):
        manager = RedisClientManager()
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(manager.get_client())
            self.assertFalse(manager.is_available())

    def test_failed_connection_is_throttled(self):
        manager = RedisClientManager()
        with patch.dict(os.environ, {
            "REDIS_URL": "redis://example/0",
            "REDIS_RECONNECT_INTERVAL_SECONDS": "60",
        }):
            with patch("utils.redis_client.redis", _FailingRedisFactory):
                self.assertIsNone(manager.get_client())
                first_retry_at = manager._next_retry_at
                self.assertIsNone(manager.get_client())
                self.assertEqual(first_retry_at, manager._next_retry_at)


if __name__ == "__main__":
    unittest.main()
