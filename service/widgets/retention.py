"""组件数据点保留策略（纯函数，便于脱离数据库单测）。

P1 只按「最多保留 N 条」裁剪。P2 收敛成一套更完整的规则：

1. 按时间倒序，保留最近 ``keep_points`` 条；
2. 失败数据点单独限额：只保留最近 ``keep_error_points`` 条，避免一串失败把
   有用的成功历史挤掉；
3. 超过 ``keep_days`` 天的老数据点直接清理；
4. 但无论如何都保留「最新一条」和「最新一条成功」——这样长期没跑的组件
   仍然能显示上一次的有效结果。

``select_ids_to_delete`` 只依赖每个数据点的 id / recorded_at / ok 三个字段，
返回需要删除的 id 集合。
"""

from datetime import datetime, timedelta
from typing import Iterable, List, Set

DEFAULT_KEEP_POINTS = 200
DEFAULT_KEEP_DAYS = 90
DEFAULT_KEEP_ERROR_POINTS = 20


class _Point:
    __slots__ = ("id", "recorded_at", "ok")

    def __init__(self, pid, recorded_at, ok):
        self.id = pid
        self.recorded_at = recorded_at
        self.ok = ok


def _coerce(points: Iterable) -> List[_Point]:
    out: List[_Point] = []
    for p in points:
        pid = getattr(p, "id", None) if not isinstance(p, dict) else p.get("id")
        recorded_at = getattr(p, "recorded_at", None) if not isinstance(p, dict) else p.get("recorded_at")
        ok = getattr(p, "ok", 1) if not isinstance(p, dict) else p.get("ok", 1)
        if pid is None:
            continue
        out.append(_Point(pid, recorded_at, 1 if (ok is None or int(ok) != 0) else 0))
    return out


def _sort_key(p: _Point):
    # recorded_at 可能为 None（刚插入未刷新），排到最后
    return (p.recorded_at or datetime.min, p.id)


def select_ids_to_delete(
    points: Iterable,
    *,
    now: datetime,
    keep_points: int = DEFAULT_KEEP_POINTS,
    keep_days: int = DEFAULT_KEEP_DAYS,
    keep_error_points: int = DEFAULT_KEEP_ERROR_POINTS,
) -> Set:
    """返回应当删除的数据点 id 集合。"""
    items = _coerce(points)
    if not items:
        return set()

    ordered = sorted(items, key=_sort_key, reverse=True)  # 新 -> 旧
    all_ids = {p.id for p in ordered}

    keep: Set = set()

    # 规则 4：最新一条 + 最新一条成功，永远保留
    keep.add(ordered[0].id)
    for p in ordered:
        if p.ok:
            keep.add(p.id)
            break

    # 规则 1：最近 keep_points 条
    recent = {p.id for p in ordered[: max(0, keep_points)]}

    # 规则 2：失败数据点单独限额
    errors_seen = 0
    allowed_errors: Set = set()
    for p in ordered:
        if not p.ok:
            errors_seen += 1
            if errors_seen <= max(0, keep_error_points):
                allowed_errors.add(p.id)

    # 规则 3：超过 keep_days 的老数据点
    cutoff = now - timedelta(days=max(0, keep_days))

    for p in ordered:
        if p.id in keep:
            continue
        if p.id not in recent:
            continue
        if not p.ok and p.id not in allowed_errors:
            continue
        if p.recorded_at is not None and p.recorded_at < cutoff:
            continue
        keep.add(p.id)

    return all_ids - keep
