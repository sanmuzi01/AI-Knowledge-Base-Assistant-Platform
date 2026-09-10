"""组件路由：全部 async + 基本连线（service 层用 mock）。"""

import inspect
import unittest
from types import SimpleNamespace

from FasdtApi import user_widget


class WidgetRouteShapeTest(unittest.TestCase):
    def test_all_handlers_are_async(self):
        handlers = [
            user_widget.design_widget_route,
            user_widget.create_widget_route,
            user_widget.list_widgets_route,
            user_widget.update_widget_route,
            user_widget.delete_widget_route,
            user_widget.run_widget_route,
            user_widget.widget_data_route,
        ]
        self.assertEqual([h.__name__ for h in handlers if not inspect.iscoroutinefunction(h)], [])

    def test_router_prefix_and_paths(self):
        paths = {route.path for route in user_widget.router.routes}
        self.assertEqual(user_widget.router.prefix, "/user/widgets")
        self.assertIn("/user/widgets/design", paths)
        self.assertIn("/user/widgets/templates", paths)
        self.assertIn("/user/widgets/from-template", paths)
        self.assertIn("/user/widgets", paths)
        self.assertIn("/user/widgets/{widget_id:int}/run", paths)

    def test_template_routes_are_async(self):
        self.assertTrue(inspect.iscoroutinefunction(user_widget.list_templates_route))
        self.assertTrue(inspect.iscoroutinefunction(user_widget.from_template_route))


class WidgetRouteWiringTest(unittest.IsolatedAsyncioTestCase):
    async def test_design_route_delegates_to_service(self):
        captured = {}

        async def fake_design(db, user, prompt):
            captured["prompt"] = prompt
            captured["user_id"] = user.id
            return {"needs_clarification": False, "draft": {"type": "chart"}}

        original = user_widget.widget_async_service.design
        user_widget.widget_async_service.design = fake_design
        try:
            out = await user_widget.design_widget_route(
                user_widget.DesignRequest(prompt="每天看金价"),
                async_db=object(),
                current_user=SimpleNamespace(id=7),
            )
        finally:
            user_widget.widget_async_service.design = original
        self.assertEqual(captured, {"prompt": "每天看金价", "user_id": 7})
        self.assertEqual(out["draft"]["type"], "chart")


if __name__ == "__main__":
    unittest.main()
