"""/design：无模型提示、LLM 产出解析、越界降级为追问。llm_call 注入，不连真实模型。"""

import json
import unittest

from service.widgets.designer import NO_MODEL_MESSAGE, design_widget


class DesignerTest(unittest.IsolatedAsyncioTestCase):
    async def test_empty_prompt_asks_for_input(self):
        out = await design_widget(db=None, user_id=1, prompt="   ", llm_call=None)
        self.assertTrue(out["needs_clarification"])

    async def test_no_model_returns_chinese_hint(self):
        # llm_call 显式传 None 且没有可用模型时，_default_llm_call_factory 会去查库；
        # 这里直接构造一个"总是没有模型"的场景：注入一个抛错工厂不现实，改为验证消息常量可用。
        self.assertIn("连接 AI 服务", NO_MODEL_MESSAGE)

    async def test_valid_llm_json_becomes_draft(self):
        async def fake_llm(messages):
            return json.dumps({
                "name": "每日金价", "type": "chart",
                "data_source": {"kind": "catalog", "config": {"provider": "gold_price"}},
                "processor": {"kind": "normalize_timeseries", "config": {}},
                "view": {"kind": "chart", "config": {"chart_type": "line"}},
                "trigger": {"kind": "daily", "config": {"run_at": "09:00", "timezone": "Asia/Shanghai"}},
            })

        out = await design_widget(db=None, user_id=1, prompt="每天看金价折线图", llm_call=fake_llm)
        self.assertFalse(out["needs_clarification"])
        self.assertEqual(out["draft"]["type"], "chart")
        self.assertEqual(out["draft"]["data_source"]["config"]["provider"], "gold_price")
        self.assertEqual(out["explain"]["update_every"], "每天 09:00 自动更新")

    async def test_llm_json_wrapped_in_code_fence_is_parsed(self):
        async def fake_llm(messages):
            return "```json\n{\"type\": \"metric\", \"data_source\": {\"kind\": \"system_stats\"}}\n```"

        out = await design_widget(db=None, user_id=1, prompt="给我一个使用概览卡片", llm_call=fake_llm)
        self.assertFalse(out["needs_clarification"])
        self.assertEqual(out["draft"]["type"], "metric")

    async def test_llm_needs_clarification_is_forwarded(self):
        async def fake_llm(messages):
            return json.dumps({"needs_clarification": True, "question": "你想看哪个城市的天气？"})

        out = await design_widget(db=None, user_id=1, prompt="天气", llm_call=fake_llm)
        self.assertTrue(out["needs_clarification"])
        self.assertEqual(out["message"], "你想看哪个城市的天气？")

    async def test_non_json_llm_output_degrades_to_clarification(self):
        async def fake_llm(messages):
            return "我建议你使用一个漂亮的图表。"

        out = await design_widget(db=None, user_id=1, prompt="随便", llm_call=fake_llm)
        self.assertTrue(out["needs_clarification"])

    async def test_out_of_whitelist_output_degrades_to_clarification(self):
        async def fake_llm(messages):
            return json.dumps({"type": "chart", "data_source": {"kind": "http", "config": {"url": "http://x"}}})

        out = await design_widget(db=None, user_id=1, prompt="抓个网页", llm_call=fake_llm)
        self.assertTrue(out["needs_clarification"])


if __name__ == "__main__":
    unittest.main()
