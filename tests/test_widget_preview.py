"""创建前试运行：run_spec_preview 不落库、复用同一套连接器/处理器，并带 auto_view。"""

import inspect
import unittest
from types import SimpleNamespace

from service.widgets.runner import run_spec_preview
from FasdtApi import user_widget


def _spec(**over):
    base = {
        "spec_version": 1,
        "name": "预览测试",
        "type": "chart",
        "data_source": {"kind": "sample", "config": {"series": "gold_price", "points": 12}},
        "processor": {"kind": "normalize_timeseries", "config": {"x_field": "date", "y_field": "value"}},
        "view": {"kind": "markdown", "config": {}},
        "trigger": {"kind": "manual", "config": {}},
        "actions": ["refresh", "delete"],
    }
    base.update(over)
    return base


class RunSpecPreviewTest(unittest.IsolatedAsyncioTestCase):
    async def test_preview_runs_pipeline_without_db(self):
        result = await run_spec_preview(db=None, user_id=1, spec=_spec())
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.widget_id, 0)                      # 预览没有真实 widget id
        self.assertEqual(result.payload["view"]["kind"], "markdown")
        self.assertEqual(len(result.payload["result"]["points"]), 12)
        # markdown 视图 + 时间序列 -> 附带折线图 auto_view
        self.assertIn("auto_view", result.payload)
        self.assertEqual(result.payload["auto_view"]["kind"], "chart")

    async def test_preview_failure_returns_error_not_raise(self):
        bad = _spec(data_source={"kind": "catalog", "config": {"provider": "not-real"}})
        result = await run_spec_preview(db=None, user_id=1, spec=bad)
        self.assertFalse(result.ok)
        self.assertTrue(result.error)
        self.assertFalse(result.payload["ok"])


class PreviewRouteTest(unittest.IsolatedAsyncioTestCase):
    def test_route_is_async_and_registered(self):
        self.assertTrue(inspect.iscoroutinefunction(user_widget.preview_widget_route))
        paths = {r.path for r in user_widget.router.routes}
        self.assertIn("/user/widgets/preview", paths)

    async def test_route_delegates_to_service(self):
        captured = {}

        async def fake_preview(db, user, draft):
            captured["draft"] = draft
            captured["uid"] = user.id
            return {"ok": True, "data": {"result": 1}}

        original = user_widget.widget_async_service.preview_widget
        user_widget.widget_async_service.preview_widget = fake_preview
        try:
            out = await user_widget.preview_widget_route(
                user_widget.CreateWidgetRequest(draft={"type": "chart"}),
                async_db=object(),
                current_user=SimpleNamespace(id=9),
            )
        finally:
            user_widget.widget_async_service.preview_widget = original
        self.assertEqual(captured, {"draft": {"type": "chart"}, "uid": 9})
        self.assertTrue(out["ok"])


if __name__ == "__main__":
    unittest.main()
