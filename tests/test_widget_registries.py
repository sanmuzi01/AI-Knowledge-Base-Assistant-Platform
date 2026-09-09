"""扩展点测试：新增 connector / processor / view 不需要改 runner 主流程。

runner 只通过 CONNECTORS.get / PROCESSORS.get 解析实现；这里注册一对全新的
connector + processor，直接驱动 run_widget，验证主流程一行不用改就能跑通。
"""

import json
import unittest
from types import SimpleNamespace

from service.widgets.connectors import CONNECTORS
from service.widgets.connectors.base import BaseConnector
from service.widgets.processors import PROCESSORS
from service.widgets.registry import Registry
from service.widgets import runner


class RegistryBehaviourTest(unittest.TestCase):
    def test_duplicate_registration_rejected(self):
        reg: Registry[int] = Registry("测试")
        reg.add("a", 1)
        with self.assertRaises(ValueError):
            reg.add("a", 2)

    def test_unknown_key_error_lists_available(self):
        reg: Registry[int] = Registry("测试")
        reg.add("a", 1)
        with self.assertRaises(KeyError) as ctx:
            reg.get("b")
        self.assertIn("a", str(ctx.exception))


class _EchoConnector(BaseConnector):
    kind = "unittest_echo"
    label = "测试回声"

    async def fetch(self, ctx, config):
        return {"rows": [{"date": "2026-01-01", "value": config.get("seed", 7)}], "unit": "u"}


def _double_processor(ctx, raw, config):
    rows = raw["rows"]
    return {"value": rows[-1]["value"] * 2, "unit": raw.get("unit")}


class ExtensionPointTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        CONNECTORS.add("unittest_echo", _EchoConnector())
        PROCESSORS.add("unittest_double", _double_processor)

    async def test_new_connector_and_processor_run_without_touching_runner(self):
        widget = SimpleNamespace(
            id=99, user_id=1, name="扩展点组件", type="metric", description="",
            spec_version=1,
            capabilities_json=json.dumps(["fetch"]),
            data_source_json=json.dumps({"kind": "unittest_echo", "config": {"seed": 21}}),
            processor_json=json.dumps({"kind": "unittest_double", "config": {}}),
            view_json=json.dumps({"kind": "metric", "config": {}}),
            trigger_json=json.dumps({"kind": "manual", "config": {}}),
            actions_json=json.dumps(["refresh", "delete"]),
            last_run_at=None, last_status=None, fail_count=0, next_run_at=None,
        )

        saved_points = []

        class _FakeDao:
            async def get_owned_widget_async(self, db, user_id, widget_id):
                return widget

            async def add_data_point_async(self, db, wid, **kw):
                saved_points.append(kw)

            async def apply_retention_async(self, db, wid, **kw):
                return 0

        import models.user_widget_async_dao as real_dao
        fake = _FakeDao()
        originals = {
            name: getattr(real_dao, name)
            for name in ("get_owned_widget_async", "add_data_point_async", "apply_retention_async")
        }
        for name in originals:
            setattr(real_dao, name, getattr(fake, name))
        try:
            class _DB:
                async def flush(self):
                    return None

            result = await runner.run_widget(_DB(), user_id=1, widget_id=99)
        finally:
            for name, fn in originals.items():
                setattr(real_dao, name, fn)

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, 42.0)          # 21 * 2，走的是新注册的 processor
        self.assertEqual(len(saved_points), 1)
        self.assertEqual(saved_points[0]["ok"], 1)


if __name__ == "__main__":
    unittest.main()
