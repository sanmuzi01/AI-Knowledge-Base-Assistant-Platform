"""工作台组件模板：选模板 + 填字段 → 直接产出合法 spec，不走大模型。"""

import unittest

from service.widgets.templates import (
    TEMPLATES, TemplateError, build_spec, list_templates,
)
from service.widgets.validator import validate_and_normalize
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()

# key -> 一组最小合法参数
_MIN_PARAMS = {
    "kb_health": {"space_id": 3},
    "kb_probe": {"agent_id": 5, "query": "报销上限是多少"},
    "my_usage": {},
    "my_overview": {},
    "api_table": {"url": "https://intra.example.com/api/list", "fields": "name,count"},
    "api_metric_alert": {"url": "https://intra.example.com/api/m", "json_path": "data", "warn_value": 100},
    "web_monitor": {"url": "https://example.com/notice"},
    "web_snapshot": {"url": "https://example.com/page"},
    "daily_briefing": {"source": "internal_api", "url": "https://intra.example.com/api/x"},
    "web_query_daily": {"query": "上证指数 今日收盘"},
}


class CatalogTest(unittest.TestCase):
    def test_every_template_covered_by_min_params(self):
        keys = {t["key"] for t in TEMPLATES}
        self.assertEqual(keys, set(_MIN_PARAMS), "有模板没写测试参数")

    def test_list_templates_shape_and_no_build_fn(self):
        for t in list_templates():
            self.assertIn("key", t)
            self.assertIn("name", t)
            self.assertIsInstance(t["fields"], list)
            self.assertNotIn("build", t)
            for f in t["fields"]:
                self.assertIn(f["type"], ("text", "textarea", "number", "url", "time", "select", "agent", "space"))


class BuildSpecTest(unittest.TestCase):
    def test_all_templates_build_valid_specs(self):
        for key, params in _MIN_PARAMS.items():
            spec = build_spec(key, params)
            # build_spec 内部已过 validator；再确认一次结构
            self.assertEqual(spec["spec_version"], 1)
            self.assertIn(spec["type"], (
                "table", "chart", "metric", "markdown", "web_monitor", "system_stats", "task_list", "api_data",
            ))
            self.assertIn("data_source", spec)
            self.assertIn("kind", spec["data_source"])
            self.assertTrue(validate_and_normalize(spec).ok)

    def test_missing_required_raises_template_error(self):
        with self.assertRaises(TemplateError):
            build_spec("kb_health", {})                       # 缺 space_id
        with self.assertRaises(TemplateError):
            build_spec("api_table", {})                       # 缺 url
        with self.assertRaises(TemplateError):
            build_spec("api_table", {"url": "ftp://x"})       # url 协议不对
        with self.assertRaises(TemplateError):
            build_spec("api_metric_alert", {"url": "https://x.com"})  # 没给任何阈值

    def test_unknown_template(self):
        with self.assertRaises(TemplateError):
            build_spec("nope", {})

    def test_kb_probe_top_k_clamped(self):
        spec = build_spec("kb_probe", {"agent_id": 1, "query": "x", "top_k": 999})
        self.assertLessEqual(spec["data_source"]["config"]["top_k"], 10)

    def test_daily_briefing_url_only_when_source_needs_it(self):
        spec = build_spec("daily_briefing", {"source": "my_usage"})
        self.assertEqual(spec["data_source"]["kind"], "system_stats")
        self.assertEqual(spec["processor"]["kind"], "llm_summarize")
        with self.assertRaises(TemplateError):
            build_spec("daily_briefing", {"source": "web_page"})   # 选了网页却没给 url

    def test_api_metric_alert_builds_threshold_rules(self):
        spec = build_spec("api_metric_alert", {
            "url": "https://x.com/m", "json_path": "d", "field": "qps",
            "alert_when": "gt", "warn_value": 50, "alert_value": 100, "unit": "次/秒",
        })
        self.assertEqual(spec["processor"]["kind"], "threshold_alert")
        rules = spec["processor"]["config"]["rules"]
        self.assertEqual([r["level"] for r in rules], ["warn", "alert"])
        self.assertEqual(spec["view"]["config"]["unit"], "次/秒")


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class TemplateRouteE2ETest(unittest.TestCase):
    """GET /templates → POST /from-template → POST '' 建组件 → 出现在列表里。"""

    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.user = rc.create_user("wtpl")
        r = cls.client.post("/agent", json={"name": f"wtpl-{cls.user['id']}"}, headers=cls.user["headers"])
        assert r.status_code == 200, r.text
        cls.agent_id = r.json()["agent_id"]

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            uid = cls.user["id"]
            db.execute(text("DELETE dp FROM widget_data_points dp JOIN user_widgets w ON dp.widget_id=w.id WHERE w.user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_widgets WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": cls.agent_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def test_catalog_lists_templates_and_my_agents(self):
        r = self.client.get("/user/widgets/templates", headers=self.user["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertGreaterEqual(len(body["templates"]), 8)
        agent_ids = [a["value"] for a in body["options"]["agents"]]
        self.assertIn(self.agent_id, agent_ids)

    def test_build_from_template_then_create(self):
        r = self.client.post("/user/widgets/from-template", headers=self.user["headers"], json={
            "template_key": "kb_probe",
            "params": {"agent_id": self.agent_id, "query": "报销上限", "top_k": 5},
        })
        self.assertEqual(r.status_code, 200, r.text)
        draft = r.json()["draft"]
        self.assertEqual(draft["data_source"]["kind"], "knowledge_base")
        self.assertEqual(draft["data_source"]["config"]["agent_id"], self.agent_id)

        c = self.client.post("/user/widgets", headers=self.user["headers"], json={"draft": draft})
        self.assertEqual(c.status_code, 200, c.text)
        wid = c.json()["id"]

        lst = self.client.get("/user/widgets", headers=self.user["headers"])
        self.assertEqual(lst.status_code, 200, lst.text)
        self.assertIn(wid, [w["id"] for w in lst.json()["items"]])

    def test_bad_params_return_400(self):
        r = self.client.post("/user/widgets/from-template", headers=self.user["headers"], json={
            "template_key": "api_table", "params": {},
        })
        self.assertEqual(r.status_code, 400, r.text)


if __name__ == "__main__":
    unittest.main()
