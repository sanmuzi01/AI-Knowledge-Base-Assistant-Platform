"""数据点保留策略（纯函数）：条数上限、失败限额、过期清理、永远保留最新 + 最新成功。"""

import unittest
from datetime import datetime, timedelta

from service.widgets.retention import select_ids_to_delete


def _pts(specs):
    """specs: list of (id, age_days, ok)。age_days 越大越旧。"""
    now = datetime(2026, 6, 1, 12, 0, 0)
    return [
        {"id": pid, "recorded_at": now - timedelta(days=age), "ok": ok}
        for pid, age, ok in specs
    ], now


class RetentionTest(unittest.TestCase):
    def test_keeps_most_recent_n_points(self):
        points, now = _pts([(i, i, 1) for i in range(1, 11)])
        drop = select_ids_to_delete(points, now=now, keep_points=5, keep_days=9999, keep_error_points=99)
        # 保留 id 1..5（最新），删 6..10
        self.assertEqual(drop, {6, 7, 8, 9, 10})

    def test_error_points_have_their_own_small_quota(self):
        # 10 个数据点里 8 个是失败，keep_points=10 但 keep_error_points=2
        specs = [(1, 1, 1), (2, 2, 1)] + [(i, i, 0) for i in range(3, 11)]
        points, now = _pts(specs)
        drop = select_ids_to_delete(points, now=now, keep_points=10, keep_days=9999, keep_error_points=2)
        # 最新的两个失败点 id 3、4 保留，其余失败点 5..10 删掉；成功点 1、2 保留
        self.assertEqual(drop, {5, 6, 7, 8, 9, 10})

    def test_expired_points_are_dropped_but_latest_success_survives(self):
        specs = [(1, 1, 0), (2, 5, 0), (3, 200, 1), (4, 300, 0)]
        points, now = _pts(specs)
        drop = select_ids_to_delete(points, now=now, keep_points=100, keep_days=90, keep_error_points=100)
        # id 3 是最新成功（虽然 200 天前）-> 必须保留；id 1 最新 -> 保留；
        # id 2（5 天前失败）在窗口内 -> 保留；id 4（300 天前失败）过期 -> 删
        self.assertEqual(drop, {4})

    def test_always_keeps_latest_and_latest_success(self):
        specs = [(1, 0, 0), (2, 1, 1), (3, 2, 0)]
        points, now = _pts(specs)
        drop = select_ids_to_delete(points, now=now, keep_points=1, keep_days=0, keep_error_points=0)
        # keep_points=1 -> 只留最新 id1；但 id2 是最新成功也必须留；id3 删
        self.assertEqual(drop, {3})

    def test_empty_input(self):
        self.assertEqual(select_ids_to_delete([], now=datetime(2026, 1, 1), keep_points=10, keep_days=10, keep_error_points=10), set())


if __name__ == "__main__":
    unittest.main()
