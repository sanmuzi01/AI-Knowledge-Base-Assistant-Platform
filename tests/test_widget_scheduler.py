"""组件调度：开关默认值、指数退避、到点批量运行的抢占 / 跳过 / 计数。"""

import os
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from service.widgets import runner, scheduler


class SchedulerSwitchTest(unittest.TestCase):
    def test_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WIDGET_SCHEDULER_ENABLED", None)
            self.assertTrue(scheduler.scheduler_enabled())

    def test_can_be_disabled(self):
        for value in ("0", "false", "off", "no"):
            with patch.dict(os.environ, {"WIDGET_SCHEDULER_ENABLED": value}):
                self.assertFalse(scheduler.scheduler_enabled())


class BackoffTest(unittest.TestCase):
    def test_exponential_with_cap(self):
        now = datetime(2026, 1, 1, 0, 0, 0)
        with patch.dict(os.environ, {"WIDGET_RETRY_BACKOFF_BASE_MINUTES": "5", "WIDGET_RETRY_BACKOFF_CAP_MINUTES": "60"}):
            self.assertEqual(runner.compute_backoff_next_run(1, now), now + timedelta(minutes=5))
            self.assertEqual(runner.compute_backoff_next_run(2, now), now + timedelta(minutes=10))
            self.assertEqual(runner.compute_backoff_next_run(4, now), now + timedelta(minutes=40))
            self.assertEqual(runner.compute_backoff_next_run(9, now), now + timedelta(minutes=60))  # capped

    def test_max_consecutive_fails_env(self):
        with patch.dict(os.environ, {"WIDGET_MAX_CONSECUTIVE_FAILS": "3"}):
            self.assertEqual(runner.max_consecutive_fails(), 3)


class _FakeDB:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class RunDueWidgetsTest(unittest.IsolatedAsyncioTestCase):
    async def test_claims_run_and_commit_per_widget(self):
        now = datetime(2026, 2, 1, 12, 0, 0)
        widgets = [
            SimpleNamespace(id=1, user_id=10, next_run_at=now - timedelta(minutes=1)),
            SimpleNamespace(id=2, user_id=10, next_run_at=now - timedelta(minutes=2)),
            SimpleNamespace(id=3, user_id=11, next_run_at=now - timedelta(minutes=3)),
        ]
        db = _FakeDB()
        claimed = []
        ran = []

        async def fake_due(_db, _now, _limit):
            return widgets

        async def fake_claim(_db, widget_id, expected, lease_until):
            claimed.append(widget_id)
            return widget_id != 2  # 组件 2 被别的 Worker 抢走了

        async def fake_run(_db, user_id, widget_id, trigger="schedule"):
            ran.append((widget_id, trigger))
            return SimpleNamespace(ok=(widget_id != 3))  # 组件 3 运行失败

        with patch.object(scheduler.dao, "due_widgets_async", fake_due), \
             patch.object(scheduler.dao, "claim_widget_async", fake_claim), \
             patch.object(scheduler, "run_widget", fake_run):
            summary = await scheduler.run_due_widgets(db, now=now)

        self.assertEqual(claimed, [1, 2, 3])
        self.assertEqual([w for w, _ in ran], [1, 3])          # 2 没抢到就没跑
        self.assertEqual(summary, {"due": 3, "ran": 2, "skipped": 1, "failed": 1})
        self.assertEqual(db.commits, 2)                        # 每个真正跑的组件各提交一次
        self.assertEqual(db.rollbacks, 1)                      # 没抢到的那次回滚

    async def test_empty_due_list_is_noop(self):
        db = _FakeDB()
        with patch.object(scheduler.dao, "due_widgets_async", lambda *a: _coro([])):
            summary = await scheduler.run_due_widgets(db)
        self.assertEqual(summary, {"due": 0, "ran": 0, "skipped": 0, "failed": 0})
        self.assertEqual(db.commits, 0)


def _coro(value):
    async def _c(*a, **k):
        return value
    return _c()


if __name__ == "__main__":
    unittest.main()
