"""数据源连接器：输出结构、config 校验、按用户过滤。"""

import unittest
from datetime import datetime

from service.widgets.connectors import CONNECTORS
from service.widgets.connectors.catalog import CATALOG_PROVIDERS
from service.widgets.context import WidgetRunContext


def _ctx(db=None):
    return WidgetRunContext(user_id=42, now=datetime(2026, 3, 1), db=db)


class SampleConnectorTest(unittest.IsolatedAsyncioTestCase):
    async def test_sample_output_shape_and_determinism(self):
        conn = CONNECTORS.get("sample")
        a = await conn.fetch(_ctx(), {"series": "gold_price", "points": 10})
        b = await conn.fetch(_ctx(), {"series": "gold_price", "points": 10})
        self.assertEqual(len(a["rows"]), 10)
        self.assertEqual(set(a["rows"][0]), {"date", "value"})
        self.assertEqual([r["value"] for r in a["rows"]], [r["value"] for r in b["rows"]])

    def test_sample_config_validation(self):
        conn = CONNECTORS.get("sample")
        self.assertEqual(conn.validate_config({"points": 30}), [])
        self.assertTrue(conn.validate_config({"points": 9999}))


class CatalogConnectorTest(unittest.IsolatedAsyncioTestCase):
    async def test_providers_registered(self):
        self.assertEqual(CATALOG_PROVIDERS.keys(), ["gold_price", "usd_cny", "weather"])

    async def test_catalog_dispatches_to_provider(self):
        conn = CONNECTORS.get("catalog")
        data = await conn.fetch(_ctx(), {"provider": "usd_cny", "points": 5})
        self.assertEqual(data["provider"], "usd_cny")
        self.assertEqual(len(data["rows"]), 5)

    def test_catalog_rejects_unknown_provider(self):
        conn = CONNECTORS.get("catalog")
        self.assertTrue(conn.validate_config({"provider": "silver"}))
        self.assertEqual(conn.validate_config({"provider": "weather"}), [])


class UserScopedConnectorTest(unittest.IsolatedAsyncioTestCase):
    async def test_system_stats_is_user_scoped(self):
        captured = {}

        async def fake_dashboard(db, user_id):
            captured["user_id"] = user_id
            return {"counts": {"agents": 2}, "status": {"health_score": 88}, "recent_runs": [], "recent_tasks": []}

        import service.user_dashboard_async_service as mod
        original = mod.get_user_dashboard
        mod.get_user_dashboard = fake_dashboard
        try:
            conn = CONNECTORS.get("system_stats")
            out = await conn.fetch(_ctx(db=object()), {})
        finally:
            mod.get_user_dashboard = original
        self.assertEqual(captured["user_id"], 42)          # 用的是 ctx.user_id
        self.assertEqual(out["health_score"], 88)

    async def test_agent_runs_requires_db(self):
        conn = CONNECTORS.get("agent_runs")
        with self.assertRaises(RuntimeError):
            await conn.fetch(_ctx(db=None), {})
        self.assertTrue(conn.validate_config({"days": 999}))


if __name__ == "__main__":
    unittest.main()
