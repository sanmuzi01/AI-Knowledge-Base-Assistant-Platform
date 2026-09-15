"""OutlineGeneratorTool 单测。

之前这里调用 `ctx.llm_client.chat(messages, ...)`，但 ctx.llm_client 实际上是
`create_langchain_llm()` 建的 LangChain ChatOpenAI 实例——它只有 `.invoke()`，没有
`.chat()`，所以每次调用都直接进 except，从未真正生成过大纲。这组测试锁定修复后的
正确调用方式（.invoke() + 从 AIMessage 取 content/usage）。
"""
import json
import unittest
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from service.tools.base import ToolContext
from service.tools.outline_generator import OutlineGeneratorTool


class OutlineGeneratorToolTest(unittest.TestCase):
    def _make_tool(self, llm_client):
        tool = OutlineGeneratorTool()
        tool.set_context(ToolContext(llm_client=llm_client))
        return tool

    def test_execute_calls_invoke_not_chat(self):
        """回归测试：这个工具从来不应该调用 .chat()（LangChain 对象没有这个方法）。"""
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content="第1章 引言\n第2章 正文")
        # 显式确保没有 .chat，模拟真实的 ChatOpenAI 接口形状
        del llm.chat

        tool = self._make_tool(llm)
        result = json.loads(tool.execute(topic="人工智能", sections=2))

        llm.invoke.assert_called_once()
        self.assertNotIn("error", result)
        self.assertEqual(result["outline"], "第1章 引言\n第2章 正文")

    def test_execute_records_usage_on_context(self):
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(
            content="大纲内容",
            usage_metadata={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28},
        )
        ctx = ToolContext(llm_client=llm)
        tool = OutlineGeneratorTool()
        tool.set_context(ctx)

        tool.execute(topic="主题", sections=3)

        self.assertEqual(ctx.usage_log, [{"input_tokens": 20, "output_tokens": 8, "total_tokens": 28}])

    def test_execute_missing_context_returns_error_not_crash(self):
        tool = OutlineGeneratorTool()
        result = json.loads(tool.execute(topic="主题"))
        self.assertIn("error", result)

    def test_execute_missing_topic_returns_error(self):
        tool = self._make_tool(MagicMock())
        result = json.loads(tool.execute())
        self.assertIn("error", result)

    def test_llm_failure_returns_error_json_not_raise(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("模型超时")
        tool = self._make_tool(llm)

        result = json.loads(tool.execute(topic="主题"))
        self.assertIn("LLM调用失败", result["error"])


if __name__ == "__main__":
    unittest.main()
