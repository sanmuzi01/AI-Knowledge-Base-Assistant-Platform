import threading
import unittest

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from service.runtime.react_engine import ReActEngine
from service.tools.base import ToolContext
from tests._runtime_fakes import _FakeLLM, echo_tool


def drain(stream):
    events = []
    while True:
        try:
            events.append(next(stream))
        except StopIteration as result:
            return events, result.value


class StreamingLLM(_FakeLLM):
    def __init__(self):
        super().__init__()
        self.closed = False
        self.completed = False
        self.resume = threading.Event()

    def stream(self, messages):
        try:
            yield AIMessageChunk(content="hello ")
            if not self.resume.wait(5):
                raise TimeoutError("Consumer did not receive the first delta")
            yield AIMessageChunk(content="world")
            yield AIMessageChunk(content="", usage_metadata={
                "input_tokens": 10, "output_tokens": 2, "total_tokens": 12,
            })
            self.completed = True
        finally:
            self.closed = True


class ReActStreamingTest(unittest.TestCase):
    def test_deltas_arrive_before_model_finishes(self):
        llm = StreamingLLM()
        stream = ReActEngine(llm, []).invoke_stream("", "hi")
        first = next(stream)
        self.assertIn("event: answer_delta", first)
        self.assertFalse(llm.completed)
        llm.resume.set()
        events, result = drain(stream)
        self.assertEqual(result["answer"], "hello world")
        self.assertEqual(result["usage"]["total_tokens"], 12)
        self.assertTrue(llm.closed)
        self.assertIn('event: answer\ndata: {"content": "hello world"}', "".join(events))

    def test_iteration_budget_and_usage_match_both_paths(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                responses = [AIMessage(content="", tool_calls=[{
                    "name": "echo_tool", "args": {"text": str(i)}, "id": f"call{i}",
                }], usage_metadata={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4})
                    for i in range(3)]
                responses.append(AIMessage(content="finished", usage_metadata={
                    "input_tokens": 3, "output_tokens": 1, "total_tokens": 4,
                }))
                llm = _FakeLLM(responses)
                steps = []
                engine = ReActEngine(llm, [echo_tool], max_iterations=2, step_callback=steps.append)
                result = drain(engine.invoke_stream("", "hi"))[1] if streaming else engine.invoke("", "hi")
                self.assertEqual(result["total_iterations"], 2)
                self.assertEqual(result["answer"], "finished")
                self.assertEqual(result["usage"]["total_tokens"], 16)
                self.assertEqual(sum(s["step_type"] == "thought" for s in steps), 3)
                self.assertEqual(sum(isinstance(m, ToolMessage) for m in llm.calls[-1]), 2)
                # The unexecuted third call must not reach the finalization request.
                self.assertFalse(any(getattr(m, "tool_calls", None) and
                                     m.tool_calls[0]["id"] == "call2" for m in llm.calls[-1]))

    def test_unknown_usage_is_not_reported_as_zero(self):
        result = ReActEngine(_FakeLLM([AIMessage(content="ok")]), []).invoke("", "hi")
        self.assertIsNone(result["usage"])

    def test_cancel_stops_stream_and_closes_model(self):
        llm = StreamingLLM()
        engine = ReActEngine(llm, [])
        stream = engine.invoke_stream("", "hi")
        next(stream)
        engine.cancel_event.set()
        llm.resume.set()
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            drain(stream)
        self.assertTrue(llm.closed)
        self.assertFalse(llm.completed)

    def test_legacy_usage_metadata(self):
        response = AIMessage(content="ok", response_metadata={
            "token_usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
        })
        result = ReActEngine(_FakeLLM([response]), []).invoke("", "hi")
        self.assertEqual(result["usage"], {"input_tokens": 7, "output_tokens": 2, "total_tokens": 9})

    def test_tool_internal_llm_usage_is_merged_into_run_total(self):
        """requires_context=True 的工具（比如 outline_generator）执行时自己也调了一次 LLM，
        这部分用量必须被算进这次运行的总 usage，不能只统计主循环两次调用。"""
        from langchain_core.tools import tool as lc_tool

        ctx = ToolContext(llm_client=None)

        @lc_tool
        def tool_with_own_llm_call(text: str) -> str:
            """模拟一个 requires_context=True 的工具，自己也调了一次 LLM。"""
            ctx.record_usage({"input_tokens": 5, "output_tokens": 3, "total_tokens": 8})
            return f"done:{text}"

        responses = [
            AIMessage(
                content="", tool_calls=[{"name": "tool_with_own_llm_call", "args": {"text": "x"}, "id": "call0"}],
                usage_metadata={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4},
            ),
            AIMessage(content="finished", usage_metadata={"input_tokens": 3, "output_tokens": 1, "total_tokens": 4}),
        ]
        llm = _FakeLLM(responses)
        engine = ReActEngine(llm, [tool_with_own_llm_call], max_iterations=2, ctx=ctx)

        result = engine.invoke("", "hi")

        # 主循环两次调用共 4+4=8 token，加上工具内部那一次 8 token = 16
        self.assertEqual(result["usage"]["total_tokens"], 16)
        # 用完就清空，不会在下一次运行里重复计入
        self.assertEqual(ctx.usage_log, [])
