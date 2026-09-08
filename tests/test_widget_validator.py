"""组件配置校验器：白名单、归一、needs_clarification、默认值补齐。"""

import unittest

from service.widgets import schema
from service.widgets.validator import validate_and_normalize


def _chart_draft(**overrides):
    draft = {
        "name": "每日金价",
        "type": "chart",
        "description": "看金价走势",
        "data_source": {"kind": "catalog", "config": {"provider": "gold_price"}},
        "processor": {"kind": "normalize_timeseries", "config": {}},
        "view": {"kind": "chart", "config": {"chart_type": "line"}},
        "trigger": {"kind": "daily", "config": {"run_at": "09:00", "timezone": "Asia/Shanghai"}},
        "actions": ["refresh", "edit", "hide", "delete"],
    }
    draft.update(overrides)
    return draft


class WidgetValidatorTest(unittest.TestCase):
    def test_valid_chart_draft_passes_and_is_normalized(self):
        result = validate_and_normalize(_chart_draft())
        self.assertTrue(result.ok, result.errors)
        spec = result.spec
        self.assertEqual(spec["spec_version"], schema.SPEC_VERSION)
        self.assertEqual(spec["type"], "chart")
        self.assertEqual(spec["view"]["config"]["chart_type"], "line")
        self.assertIn("schedule", spec["capabilities"])  # daily -> schedule 能力被推导出来

    def test_unknown_type_returns_clarification(self):
        result = validate_and_normalize({"type": "hologram", "data_source": {"kind": "sample"}})
        self.assertTrue(result.needs_clarification)
        self.assertFalse(result.ok)
        self.assertTrue(result.message)

    def test_missing_data_source_returns_clarification(self):
        result = validate_and_normalize({"type": "chart"})
        self.assertTrue(result.needs_clarification)

    def test_llm_needs_clarification_passthrough(self):
        result = validate_and_normalize({"needs_clarification": True, "question": "你想看哪种数据？"})
        self.assertTrue(result.needs_clarification)
        self.assertEqual(result.message, "你想看哪种数据？")

    def test_unknown_view_kind_is_rejected(self):
        result = validate_and_normalize(_chart_draft(view={"kind": "wormhole"}))
        self.assertFalse(result.ok)
        self.assertTrue(any("展示方式" in e for e in result.errors))

    def test_unknown_connector_is_rejected(self):
        result = validate_and_normalize(_chart_draft(data_source={"kind": "http", "config": {}}))
        self.assertFalse(result.ok)
        self.assertTrue(any("数据来源" in e for e in result.errors))

    def test_bad_catalog_provider_is_rejected_by_connector(self):
        result = validate_and_normalize(_chart_draft(data_source={"kind": "catalog", "config": {"provider": "oil"}}))
        self.assertFalse(result.ok)

    def test_invalid_trigger_time_falls_back_to_default(self):
        result = validate_and_normalize(_chart_draft(trigger={"kind": "daily", "config": {"run_at": "99:99"}}))
        self.assertTrue(result.ok)
        self.assertEqual(result.spec["trigger"]["config"]["run_at"], "09:00")

    def test_actions_are_whitelisted_and_defaults_added(self):
        result = validate_and_normalize(_chart_draft(actions=["refresh", "explode", "hack"]))
        self.assertTrue(result.ok)
        self.assertEqual(set(result.spec["actions"]) - set(schema.ACTIONS), set())
        self.assertIn("delete", result.spec["actions"])

    def test_processor_defaults_by_view_kind(self):
        draft = _chart_draft()
        draft.pop("processor")
        result = validate_and_normalize(draft)
        self.assertEqual(result.spec["processor"]["kind"], "normalize_timeseries")

        metric_draft = _chart_draft(type="metric", view={"kind": "metric"})
        metric_draft.pop("processor")
        metric_result = validate_and_normalize(metric_draft)
        self.assertEqual(metric_result.spec["processor"]["kind"], "aggregate")

    def test_name_defaults_from_type_label(self):
        result = validate_and_normalize(_chart_draft(name="  "))
        self.assertEqual(result.spec["name"], schema.TYPE_LABELS["chart"])

    def test_system_stats_widget_needs_no_config(self):
        result = validate_and_normalize({
            "type": "system_stats",
            "data_source": {"kind": "system_stats"},
            "trigger": {"kind": "manual"},
        })
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.spec["view"]["kind"], "system_stats")


if __name__ == "__main__":
    unittest.main()
