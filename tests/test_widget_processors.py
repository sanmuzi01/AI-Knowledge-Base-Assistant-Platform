"""处理器注册表：每个命名处理函数的行为。"""

import unittest
from datetime import datetime

from service.widgets.context import WidgetRunContext
from service.widgets.processors import PROCESSORS, resolve_path


def _ctx():
    return WidgetRunContext(user_id=1, now=datetime(2026, 1, 1))


_RAW = {
    "unit": "USD/oz",
    "rows": [
        {"date": "2026-01-03", "value": 30},
        {"date": "2026-01-01", "value": 10},
        {"date": "2026-01-02", "value": 20},
    ],
}


class ProcessorTest(unittest.TestCase):
    def test_passthrough_returns_input(self):
        self.assertIs(PROCESSORS.get("passthrough")(_ctx(), _RAW, {}), _RAW)

    def test_normalize_timeseries_sorts_and_maps(self):
        out = PROCESSORS.get("normalize_timeseries")(_ctx(), _RAW, {})
        self.assertEqual([p["t"] for p in out["points"]], ["2026-01-01", "2026-01-02", "2026-01-03"])
        self.assertEqual([p["y"] for p in out["points"]], [10.0, 20.0, 30.0])
        self.assertEqual(out["unit"], "USD/oz")

    def test_normalize_timeseries_custom_fields(self):
        raw = {"rows": [{"day": "a", "n": "5"}, {"day": "b", "n": "bad"}]}
        out = PROCESSORS.get("normalize_timeseries")(_ctx(), raw, {"x_field": "day", "y_field": "n"})
        self.assertEqual(out["points"], [{"t": "a", "y": 5.0}])

    def test_aggregate_ops(self):
        agg = PROCESSORS.get("aggregate")
        self.assertEqual(agg(_ctx(), _RAW, {"op": "sum", "field": "value"})["value"], 60)
        self.assertEqual(agg(_ctx(), _RAW, {"op": "avg", "field": "value"})["value"], 20)
        self.assertEqual(agg(_ctx(), _RAW, {"op": "max", "field": "value"})["value"], 30)
        self.assertEqual(agg(_ctx(), _RAW, {"op": "count"})["value"], 3)
        last = agg(_ctx(), _RAW, {"op": "last", "field": "value"})
        self.assertEqual(last["value"], 20)          # rows 未排序 [30,10,20]，last=最后一行
        self.assertEqual(last["delta"], 10)          # 20 - 10（与前一个值比）

    def test_pick_fields(self):
        out = PROCESSORS.get("pick_fields")(_ctx(), _RAW, {"fields": ["value"]})
        self.assertEqual(out, [{"value": 30}, {"value": 10}, {"value": 20}])

    def test_json_extract_safe_path(self):
        out = PROCESSORS.get("json_extract")(_ctx(), _RAW, {"path": "rows.0.value"})
        self.assertEqual(out["value"], 30)

    def test_resolve_path_variants(self):
        data = {"a": {"b": [{"c": 1}, {"c": 2}]}}
        self.assertEqual(resolve_path(data, "a.b.1.c"), 2)
        self.assertEqual(resolve_path(data, "a.b[0].c"), 1)
        self.assertEqual(resolve_path(data, "a.b.*.c"), [1, 2])
        self.assertIsNone(resolve_path(data, "a.x.y"))
        self.assertIsNone(resolve_path(data, "a.b.9.c"))


if __name__ == "__main__":
    unittest.main()
