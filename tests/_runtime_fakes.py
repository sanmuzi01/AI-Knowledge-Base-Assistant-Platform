"""agent_runtime 测试共享替身（不是测试文件）。

- `_FakeLLM`：最小 LangChain ChatModel 替身，只实现 ReActEngine 用到的 bind_tools / invoke。
- `echo_tool`：一个真实 LangChain @tool，用于测一次工具调用往返。
- `_StubExecutor`：替换 `service.runtime.agent_runtime.ToolExecutor`，跳过真实 LLM / 技能装配，
  直接把 FakeLLM + 指定工具塞进真实 `ReActEngine`。
"""

from langchain_core.messages import AIMessage
from langchain_core.tools import tool


class _FakeLLM:
    """responses: 按 invoke 次序弹出的 AIMessage；耗尽后返回一句兜底回答。
    raise_on_call: 传入异常实例则每次 invoke 直接抛（测失败路径）。"""

    def __init__(self, responses=None, raise_on_call=None):
        self._responses = list(responses or [])
        self._raise = raise_on_call
        self.calls = []  # 每次 invoke 收到的 messages

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        if self._raise is not None:
            raise self._raise
        if self._responses:
            return self._responses.pop(0)
        return AIMessage(content="（兜底回答）")


@tool
def echo_tool(text: str) -> str:
    """回显传入文本（测试用工具）。"""
    return f"echo:{text}"


class _StubExecutor:
    def __init__(self, llm, tools):
        self._llm = llm
        self._tools = tools

    def create_engine(self, max_iterations=5, step_callback=None):
        from service.runtime.react_engine import ReActEngine
        return ReActEngine(
            llm=self._llm, tools=self._tools,
            max_iterations=max_iterations, step_callback=step_callback,
        )
