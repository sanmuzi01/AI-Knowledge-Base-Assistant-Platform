"""处理器 llm_summarize：注入假模型出摘要 / 无模型优雅降级 / 空回复报错触发退避。"""

import unittest
from datetime import datetime
from unittest.mock import patch

from service.widgets.context import WidgetRunContext
from service.widgets.processors import PROCESSORS


def _ctx():
    return WidgetRunContext(user_id=1, now=datetime(2026, 5, 1, 9, 0, 0), db=object())


class LlmSummarizeTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.proc = PROCESSORS.get("llm_summarize")

    async def test_uses_injected_llm_call(self):
        seen = {}

        async def fake_llm(messages):
            seen["messages"] = messages
            return "本周运行 12 次，成功率 92%，较上周提升。"

        raw = {"summary": {"runs": 12, "finished": 11}}
        out = await self.proc(_ctx(), raw, {"instruction": "总结运行情况", "_llm_call": fake_llm})

        self.assertEqual(out["summary"], "本周运行 12 次，成功率 92%，较上周提升。")
        self.assertEqual(out["text"], out["summary"])
        self.assertIn("总结运行情况", seen["messages"][1]["content"])
        self.assertIn("runs", seen["messages"][1]["content"])  # 原始数据被带上

    async def test_no_model_degrades_without_raising(self):
        async def no_factory(db, user_id):
            return None

        with patch("service.widgets.designer._default_llm_call_factory", no_factory):
            out = await self.proc(_ctx(), {"a": 1}, {})

        self.assertTrue(out["skipped"])
        self.assertIsNone(out["summary"])
        self.assertIn("未连接 AI 模型", out["text"])

    async def test_empty_answer_raises_for_backoff(self):
        from service.exceptions import UpstreamError

        async def empty_llm(messages):
            return "   "

        with self.assertRaises(UpstreamError):
            await self.proc(_ctx(), {"a": 1}, {"_llm_call": empty_llm})

    async def test_returns_headline_and_strips_preamble(self):
        async def chatty_llm(messages):
            return "好的，以下是总结如下：\n**本周成功率 92%**\n\n- 运行 12 次\n- 失败 1 次"

        out = await self.proc(_ctx(), {"x": 1}, {"_llm_call": chatty_llm})
        self.assertTrue(out["text"].startswith("**本周成功率 92%**"))   # 前面的寒暄被剥掉
        self.assertEqual(out["headline"], "本周成功率 92%")             # 去掉 markdown 记号的纯文本

    async def test_style_changes_format_instruction(self):
        seen = {}

        async def spy_llm(messages):
            seen["system"] = messages[0]["content"]
            return "一句话结论"

        await self.proc(_ctx(), {"x": 1}, {"_llm_call": spy_llm, "style": "one_line"})
        self.assertIn("一句话", seen["system"])
        self.assertIn("不超过", seen["system"])

    async def test_code_fence_is_unwrapped(self):
        async def fenced_llm(messages):
            return "```markdown\n**结论**\n- 要点\n```"

        out = await self.proc(_ctx(), {"x": 1}, {"_llm_call": fenced_llm})
        self.assertNotIn("```", out["text"])
        self.assertTrue(out["text"].startswith("**结论**"))


if __name__ == "__main__":
    unittest.main()
