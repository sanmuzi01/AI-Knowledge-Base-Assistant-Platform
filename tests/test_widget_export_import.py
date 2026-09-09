"""组件导出 / 导入：导出只含 spec，导入照常过校验并复用 create。"""

import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from service.exceptions import AppError

from FasdtApi import user_widget
from service import widget_async_service as svc


def _widget_row():
    return SimpleNamespace(
        id=3, user_id=1, name="金价走势", type="chart", description="", spec_version=1,
        capabilities_json=json.dumps(["fetch"]),
        data_source_json=json.dumps({"kind": "catalog", "config": {"provider": "gold_price"}}),
        processor_json=json.dumps({"kind": "normalize_timeseries", "config": {}}),
        view_json=json.dumps({"kind": "chart", "config": {"chart_type": "line"}}),
        trigger_json=json.dumps({"kind": "daily", "config": {"run_at": "09:00", "timezone": "Asia/Shanghai"}}),
        actions_json=json.dumps(["refresh", "delete"]),
    )


class ExportTest(unittest.IsolatedAsyncioTestCase):
    async def test_export_returns_clean_spec(self):
        async def fake_get(db, user_id, widget_id):
            return _widget_row() if widget_id == 3 and user_id == 1 else None

        with patch.object(svc.dao, "get_owned_widget_async", fake_get):
            out = await svc.export_widget(object(), SimpleNamespace(id=1), 3)

        self.assertEqual(out["export_version"], 1)
        self.assertEqual(out["kind"], "user_widget")
        self.assertEqual(out["spec"]["type"], "chart")
        self.assertEqual(out["spec"]["data_source"]["config"]["provider"], "gold_price")
        # 不泄露运行状态 / 用户字段
        self.assertNotIn("user_id", out["spec"])
        self.assertNotIn("last_status", out["spec"])

    async def test_export_missing_widget_404(self):
        async def none_get(db, user_id, widget_id):
            return None

        with patch.object(svc.dao, "get_owned_widget_async", none_get):
            with self.assertRaises(AppError) as ctx:
                await svc.export_widget(object(), SimpleNamespace(id=1), 999)
        self.assertEqual(ctx.exception.http_status, 404)


class ImportTest(unittest.IsolatedAsyncioTestCase):
    async def test_import_unwraps_spec_and_delegates_to_create(self):
        seen = {}

        async def fake_create(db, user, draft):
            seen["draft"] = draft
            return {"id": 10, "name": draft.get("name")}

        payload = {"export_version": 1, "spec": {"type": "metric", "data_source": {"kind": "system_stats"}}}
        with patch.object(svc, "create_widget", fake_create):
            out = await svc.import_widget(object(), SimpleNamespace(id=1), payload)

        self.assertEqual(seen["draft"]["type"], "metric")
        self.assertEqual(out["id"], 10)

    async def test_import_accepts_bare_spec(self):
        async def fake_create(db, user, draft):
            return {"id": 11}

        with patch.object(svc, "create_widget", fake_create):
            out = await svc.import_widget(object(), SimpleNamespace(id=1), {"type": "table", "data_source": {"kind": "sample"}})
        self.assertEqual(out["id"], 11)

    async def test_import_rejects_garbage(self):
        with self.assertRaises(AppError):
            await svc.import_widget(object(), SimpleNamespace(id=1), {"hello": "world"})


class RouteWiringTest(unittest.TestCase):
    def test_routes_present_and_async(self):
        self.assertTrue(inspect.iscoroutinefunction(user_widget.export_widget_route))
        self.assertTrue(inspect.iscoroutinefunction(user_widget.import_widget_route))
        paths = {r.path for r in user_widget.router.routes}
        self.assertIn("/user/widgets/import", paths)
        self.assertIn("/user/widgets/{widget_id:int}/export", paths)


if __name__ == "__main__":
    unittest.main()
