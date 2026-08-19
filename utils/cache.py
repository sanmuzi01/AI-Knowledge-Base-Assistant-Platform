import copy
import time
from threading import RLock
from typing import Any, Callable, Dict, Hashable, Optional, Tuple


class TTLCache:
    """Simple in-process TTL cache for stable config data."""

    def __init__(self, default_ttl: int = 60):
        self.default_ttl = default_ttl
        self._items: Dict[Hashable, Tuple[float, Any]] = {}
        self._lock = RLock()

    def get_or_set(self, key: Hashable, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        now = time.time()
        with self._lock:
            item = self._items.get(key)
            if item and item[0] > now:
                return copy.deepcopy(item[1])
        value = factory()
        expires_at = now + (ttl if ttl is not None else self.default_ttl)
        with self._lock:
            self._items[key] = (expires_at, copy.deepcopy(value))
        return value

    def set(self, key: Hashable, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            self._items[key] = (time.time() + (ttl if ttl is not None else self.default_ttl), copy.deepcopy(value))

    def invalidate(self, key: Hashable = None, prefix: Tuple[Any, ...] = None) -> int:
        with self._lock:
            if key is not None:
                return 1 if self._items.pop(key, None) is not None else 0
            if prefix is None:
                count = len(self._items)
                self._items.clear()
                return count
            keys = [item_key for item_key in self._items if isinstance(item_key, tuple) and item_key[:len(prefix)] == prefix]
            for item_key in keys:
                self._items.pop(item_key, None)
            return len(keys)

    def stats(self) -> Dict[str, int]:
        now = time.time()
        with self._lock:
            expired = [key for key, item in self._items.items() if item[0] <= now]
            for key in expired:
                self._items.pop(key, None)
            return {"size": len(self._items), "expired_removed": len(expired)}


config_cache = TTLCache(default_ttl=120)
skill_cache = TTLCache(default_ttl=60)
