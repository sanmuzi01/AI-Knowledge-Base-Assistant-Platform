"""运行引擎：唯一入口 run_widget 的成功/失败路径 + 下次运行时间计算。"""

import json
import unittest
from datetime import datetime
from types import SimpleNamespace

import models.user_widget_async_dao as real_dao
from service.widgets import runner
from service.widgets.connectors import CONNECTORS
from service.widgets.connectors.base import BaseConnector


class _OkConnector(BaseConnector):
    kind = "unittest_ok"

    async def fetch(self, ctx, config):
        return {"unit": "x", "rows": [{"date": "2026-01-01", "value": 1}, {"date": "2026-01-02", "value": 3}]}


class _BoomConnector(BaseConnector):
    kind = "unittest_boom"

    async def fetch(self, ctx, config):
        raise RuntimeError("上游炸了")


class _FakeDB:
    def __init__(self):
        self.flushed = 0

    async def flush(self):
        self.flushed += 1


def _widget(**over):
    base = dict(
        id=5, user_id=1, name="w", type="chart", description="", spec_version=1,
        capabilities_json=json.dumps(["fetch"]),
        data_source_json=json.dumps({"kind": "unittest_ok", "config": {}}),
        processor_json=json.dumps({"kind": "normalize_timeseries", "config": {}}),
        view_json=json.dumps({"kind": "chart", "config": {"chart_type": "line"}}),
        trigger_json=json.dumps({"kind": "daily", "config": {"run_at": "09:00", "timezone": "Asia/Shanghai"}}),
        actions_json=json.dumps(["refresh", "delete"]),
        last_run_at=None, last_status=None, fail_count=0, next_run_at=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


class RunnerTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        if not CONNECTORS.has("unittest_ok"):
            CONNECTORS.add("unittest_ok", _OkConnector())
        if not CONNECTORS.has("unittest_boom"):
            CONNECTORS.add("unittest_boom", _BoomConnector())

    def setUp(self):
        self.points = []
        self.widget = _widget()
        self._orig = {
            n: getattr(real_dao, n)
            for n in ("get_owned_widget_async", "add_data_point_async", "apply_retention_async")
        }
        widget = self.widget
        points = self.points

        async def get_owned(db, user_id, widget_id):
            return widget if widget_id == widget.id and user_id == widget.user_id else None

        async def add_point(db, wid, **kw):
            points.append(kw)

        async def apply_retention(db, wid, **kw):
            return 0

        real_dao.get_owned_widget_async = get_owned
        real_dao.add_data_point_async = add_point
        real_dao.apply_retention_async = apply_retention

    def tearDown(self):
        for n, fn in self._orig.items():
            setattr(real_dao, n, fn)

    async def test_happy_path_writes_point_and_schedules_next_run(self):
        result = await runner.run_widget(_FakeDB(), user_id=1, widget_id=5)
        self.assertTrue(result.ok)
        self.assertEqual(len(self.points), 1)
        self.assertEqual(self.points[0]["ok"], 1)
        self.assertEqual(self.widget.last_status, "ok")
        self.assertEqual(self.widget.fail_count, 0)
        self.assertIsNotNone(self.widget.next_run_at)          # daily -> 有下次运行时间
        payload = json.loads(self.points[0]["payload_json"])
        self.assertEqual(payload["view"]["kind"], "chart")
        self.assertEqual(len(payload["result"]["points"]), 2)

    async def test_failure_path_records_error_and_bumps_fail_count(self):
        self.widget.data_source_json = json.dumps({"kind": "unittest_boom", "config": {}})
        result = await runner.run_widget(_FakeDB(), user_id=1, widget_id=5)
        self.assertFalse(result.ok)
        self.assertIn("上游炸了", result.error)
        self.assertEqual(self.points[0]["ok"], 0)
        self.assertEqual(self.widget.last_status, "error")
        self.assertEqual(self.widget.fail_count, 1)

    async def test_missing_widget_raises(self):
        from service.exceptions import NotFound
        with self.assertRaises(NotFound):
            await runner.run_widget(_FakeDB(), user_id=1, widget_id=999)


class ComputeNextRunAtTest(unittest.TestCase):
    def test_manual_has_no_next_run(self):
        self.assertIsNone(runner.compute_next_run_at({"kind": "manual"}, datetime(2026, 1, 1, 12)))

    def test_hourly_rolls_to_next_hour(self):
        nxt = runner.compute_next_run_at({"kind": "hourly", "config": {"minute": 0}}, datetime(2026, 1, 1, 12, 30))
        self.assertEqual(nxt, datetime(2026, 1, 1, 13, 0))

    def test_daily_converts_local_time_to_utc(self):
        # 09:00 Asia/Shanghai == 01:00 UTC
        nxt = runner.compute_next_run_at(
            {"kind": "daily", "config": {"run_at": "09:00", "timezone": "Asia/Shanghai"}},
            datetime(2026, 1, 1, 0, 0),
        )
        self.assertEqual(nxt, datetime(2026, 1, 1, 1, 0))


if __name__ == "__main__":
    unittest.main()
