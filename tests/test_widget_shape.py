"""数据形态识别：时间序列 -> auto_view 折线图建议。"""

import unittest

from service.widgets.shape import detect_categorical, detect_series
from service.widgets.runner import build_success_payload


class DetectSeriesTest(unittest.TestCase):
    def test_normalize_timeseries_output_is_recognized(self):
        processed = {"points": [{"t": "2026-01-01", "y": 1}, {"t": "2026-01-02", "y": 2},
                                {"t": "2026-01-03", "y": 3}], "unit": "℃"}
        s = detect_series(processed)
        self.assertIsNotNone(s)
        self.assertEqual(len(s["points"]), 3)
        self.assertEqual(s["suggested_view"]["kind"], "chart")
        self.assertEqual(s["suggested_view"]["config"]["unit"], "℃")

    def test_list_of_rows_with_date_and_value(self):
        rows = [{"date": "2026-03-01", "value": 10}, {"date": "2026-03-02", "value": 12},
                {"date": "2026-03-03", "value": 9}, {"date": "2026-03-04", "value": 15}]
        s = detect_series(rows)
        self.assertIsNotNone(s)
        self.assertEqual(s["points"][0], {"t": "2026-03-01", "y": 10.0})

    def test_rows_key_container(self):
        s = detect_series({"rows": [{"day": "d1", "count": 1}, {"day": "d2", "count": 2}, {"day": "d3", "count": 4}]})
        self.assertIsNotNone(s)

    def test_too_few_points_is_not_series(self):
        self.assertIsNone(detect_series([{"date": "d1", "value": 1}, {"date": "d2", "value": 2}]))

    def test_plain_text_is_not_series(self):
        self.assertIsNone(detect_series({"text": "一段摘要"}))
        self.assertIsNone(detect_series("hello"))

    def test_non_numeric_values_not_series(self):
        self.assertIsNone(detect_series([{"date": "d1", "value": "a"}, {"date": "d2", "value": "b"},
                                         {"date": "d3", "value": "c"}]))


class DetectCategoricalTest(unittest.TestCase):
    def test_counts_mapping_becomes_bar(self):
        s = detect_categorical({"counts": {"成功": 12, "失败": 3, "超时": 1}})
        self.assertIsNotNone(s)
        self.assertEqual(s["suggested_view"]["config"]["chart_type"], "bar")
        self.assertEqual(len(s["points"]), 3)

    def test_by_status_mapping(self):
        s = detect_categorical({"by_status": {"finished": 8, "failed": 2}})
        self.assertIsNotNone(s)

    def test_rows_with_label_and_value(self):
        s = detect_categorical([{"name": "北京", "value": 30}, {"name": "上海", "value": 28}, {"name": "广州", "value": 33}])
        self.assertIsNotNone(s)

    def test_too_many_categories_rejected(self):
        self.assertIsNone(detect_categorical({"counts": {str(i): i for i in range(20)}}))

    def test_time_labels_not_categorical(self):
        self.assertIsNone(detect_categorical([{"name": "2026-01-01", "value": 1},
                                              {"name": "2026-01-02", "value": 2},
                                              {"name": "2026-01-03", "value": 3}]))


class AutoViewPayloadTest(unittest.TestCase):
    def _spec(self, view_kind):
        return {"view": {"kind": view_kind, "config": {}}, "data_source": {"kind": "sample", "config": {}}}

    def test_markdown_view_over_series_gets_auto_view(self):
        processed = {"points": [{"t": f"d{i}", "y": i} for i in range(6)]}
        payload = build_success_payload(self._spec("markdown"), {"kind": "sample", "config": {}}, processed, "2026-01-01 00:00:00")
        self.assertIn("auto_view", payload)
        self.assertEqual(payload["auto_view"]["kind"], "chart")
        self.assertEqual(len(payload["auto_view"]["data"]["points"]), 6)
        self.assertTrue(payload["auto_view_reason"])

    def test_chart_view_does_not_get_auto_view(self):
        processed = {"points": [{"t": f"d{i}", "y": i} for i in range(6)]}
        payload = build_success_payload(self._spec("chart"), {"kind": "sample", "config": {}}, processed, "2026-01-01 00:00:00")
        self.assertNotIn("auto_view", payload)

    def test_markdown_view_over_text_has_no_auto_view(self):
        payload = build_success_payload(self._spec("markdown"), {"kind": "sample", "config": {}}, {"text": "摘要"}, "2026-01-01 00:00:00")
        self.assertNotIn("auto_view", payload)

    def test_table_view_over_categorical_gets_bar_auto_view(self):
        processed = {"by_status": {"finished": 8, "failed": 2, "running": 1}}
        payload = build_success_payload(self._spec("table"), {"kind": "agent_runs", "config": {}}, processed, "2026-01-01 00:00:00")
        self.assertEqual(payload["auto_view"]["config"]["chart_type"], "bar")


if __name__ == "__main__":
    unittest.main()
