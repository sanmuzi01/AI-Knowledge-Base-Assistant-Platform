"""通用注册表工具。

connector / processor / catalog provider 都用它做「注册即扩展」：
新增一个实现 -> 用 @registry.register("kind") 装饰 -> 运行引擎通过 registry.get("kind")
拿到，不需要改 runner 主流程，也不需要在别处加 if/else。
"""

from typing import Callable, Dict, Generic, Iterable, List, Tuple, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, label: str) -> None:
        self._label = label
        self._items: Dict[str, T] = {}

    def register(self, key: str) -> Callable[[T], T]:
        def _wrap(obj: T) -> T:
            normalized = (key or "").strip()
            if not normalized:
                raise ValueError(f"{self._label} 注册键不能为空")
            if normalized in self._items:
                raise ValueError(f"{self._label} 重复注册: {normalized}")
            self._items[normalized] = obj
            return obj

        return _wrap

    def add(self, key: str, obj: T) -> None:
        """非装饰器写法（provider 之类批量注册时用）。"""
        self.register(key)(obj)

    def get(self, key: str) -> T:
        try:
            return self._items[(key or "").strip()]
        except KeyError:
            raise KeyError(f"未知的{self._label}: {key!r}（可用: {', '.join(self.keys()) or '无'}）")

    def has(self, key: str) -> bool:
        return (key or "").strip() in self._items

    def keys(self) -> List[str]:
        return sorted(self._items.keys())

    def items(self) -> Iterable[Tuple[str, T]]:
        return list(self._items.items())
