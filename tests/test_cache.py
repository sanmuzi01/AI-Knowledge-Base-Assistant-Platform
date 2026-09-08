import time
import unittest

from utils.cache import TTLCache


class TTLCacheTest(unittest.TestCase):
    def test_get_set_and_expire(self):
        cache = TTLCache(default_ttl=1, namespace="unit_cache")
        cache.set(("item", 1), {"name": "value"}, ttl=1)

        self.assertEqual(cache.get(("item", 1)), {"name": "value"})

        time.sleep(1.1)
        self.assertIsNone(cache.get(("item", 1)))

    def test_get_or_set_returns_copy(self):
        cache = TTLCache(default_ttl=30, namespace="unit_copy")
        value = cache.get_or_set("key", lambda: {"items": []})
        value["items"].append("changed")

        self.assertEqual(cache.get("key"), {"items": []})


if __name__ == "__main__":
    unittest.main()
