"""处理器 threshold_alert：取值 + 阈值判定 + 分级文案 + 需关注标记。"""

import json
import unittest
from datetime import datetime
from types import SimpleNamespace

from service.widgets.context import WidgetRunContext
from service.widgets.processors import PROCESSORS
from service.widget_async_service import _attention_from_point


def _ctx():
    return WidgetRunContext(user_id=1, now=datetime(2026, 5, 1, 9, 0, 0))


class ThresholdAlertTest(unittest.TestCase):
    def setUp(self):
        self.proc = PROCESSORS.get("threshold_alert")

    def test_shorthand_gt_triggers_alert(self):
        out = self.proc(_ctx(), {"value": 130, "unit": "ms"}, {"gt": 100})
        self.assertEqual(out["level"], "alert")
        self.assertEqual(out["value"], 130)
        self.assertIn("🔴", out["text"])

    def test_ok_when_no_rule_matches(self):
        out = self.proc(_ctx(), {"value": 42}, {"gt": 100})
        self.assertEqual(out["level"], "ok")
        self.assertIn("🟢", out["text"])

    def test_rules_pick_worst_level(self):
        cfg = {"field": "value", "rules": [
            {"level": "warn", "op": "gt", "value": 50, "message": "偏高"},
            {"level": "alert", "op": "gt", "value": 90, "message": "严重偏高"},
        ]}
        self.assertEqual(self.proc(_ctx(), {"value": 60}, cfg)["level"], "warn")
        worst = self.proc(_ctx(), {"value": 95}, cfg)
        self.assertEqual(worst["level"], "alert")
        self.assertIn("严重偏高", worst["text"])

    def test_reads_last_point_of_series(self):
        raw = {"points": [{"t": "d1", "y": 3}, {"t": "d2", "y": 12}], "unit": "个"}
        out = self.proc(_ctx(), raw, {"gt": 10})
        self.assertEqual(out["value"], 12)
        self.assertEqual(out["level"], "alert")

    def test_no_number_is_ok_with_note(self):
        out = self.proc(_ctx(), {"text": "没有数字"}, {"gt": 1})
        self.assertEqual(out["level"], "ok")
        self.assertIsNone(out["value"])


class AttentionFlagTest(unittest.TestCase):
    def _point(self, result):
        return SimpleNamespace(payload_json=json.dumps({"result": result}))

    def test_alert_level_becomes_attention(self):
        self.assertEqual(_attention_from_point(self._point({"level": "alert"})), "alert")
        self.assertEqual(_attention_from_point(self._point({"level": "warn"})), "warn")
        self.assertIsNone(_attention_from_point(self._point({"level": "ok"})))

    def test_web_page_changed_becomes_attention(self):
        self.assertEqual(_attention_from_point(self._point({"changed": True})), "changed")
        self.assertIsNone(_attention_from_point(self._point({"changed": False})))

    def test_none_point(self):
        self.assertIsNone(_attention_from_point(None))


if __name__ == "__main__":
    unittest.main()
