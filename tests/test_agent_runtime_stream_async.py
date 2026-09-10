"""阶段 3 —— `run_stream_with_history_async` / async `chat_with_agent_stream_async` /
`POST /chat/{id}/stream` 行为验证。

LangGraph 同步 `invoke_stream` 生成器经 worker 线程 + `asyncio.Queue` 桥回，事件应逐条透传；
事务边界同非流式 async 路径（run 尽早 commit、记忆总结独立事务）。无法连库时整体 skip。
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from tests import _route_client as rc
from tests._runtime_fakes import _FakeLLM, _StubExecutor, echo_tool

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class RunStreamAsyncTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("rts")

    @classmethod
    def tearDownClass(cls):
        cls._wipe()
        rc.cleanup()

    @classmethod
    def _wipe(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            uid = cls.user["id"]
            db.execute(text("DELETE s FROM agent_step s JOIN agent_run r ON s.run_id=r.id WHERE r.user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM agent_run WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE m FROM message m JOIN conversation c ON m.conversation_id=c.id WHERE c.user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM conversation WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM memory WHERE user_id=:u"), {"u": uid})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _mk_agent(self, tag, **overrides):
        from models.init_db import SessionLocal
        from models.agent_dao import create_agent
        db = SessionLocal()
        try:
            fields = dict(name=f"rts-{tag}", user_id=self.user["id"], model_name="glm-4",
                          rag_enabled=0, memory_enabled=0, temperature=70)
            fields.update(overrides)
            a = create_agent(db, **fields)
            db.commit()
            return a.id
        finally:
            db.close()

    def _mk_conv(self, agent_id):
        from models.init_db import SessionLocal
        import models.conversation_dao as cdao
        db = SessionLocal()
        try:
            c = cdao.create_conversation(db, user_id=self.user["id"], agent_id=agent_id)
            db.commit()
            return c.id
        finally:
            db.close()

    def _run_stream(self, agent_id, conv_id, fake, tools, message="你好"):
        from models.async_db import AsyncSessionLocal, async_engine
        from service.runtime import agent_runtime

        async def _go():
            events = []
            try:
                async with AsyncSessionLocal() as db:
                    with patch.object(agent_runtime, "ToolExecutor",
                                      lambda **kw: _StubExecutor(fake, tools)):
                        async for ev in agent_runtime.run_stream_with_history_async(
                            db=db, user_id=self.user["id"], agent_id=agent_id,
                            user_message=message, history=[], conversation_id=conv_id,
                        ):
                            events.append(ev)
            finally:
                await async_engine.dispose()
            return events
        return asyncio.run(_go())

    def _latest_run(self, conv_id):
        from models.init_db import SessionLocal, AgentRun, AgentStep
        db = SessionLocal()
        try:
            run = (db.query(AgentRun).filter(AgentRun.conversation_id == conv_id)
                   .order_by(AgentRun.id.desc()).first())
            steps = (db.query(AgentStep).filter(AgentStep.run_id == run.id)
                     .order_by(AgentStep.step_no).all()) if run else []
            return {
                "status": run.status if run else None,
                "final_answer": run.final_answer if run else None,
                "error_msg": run.error_msg if run else None,
                "step_types": [s.step_type for s in steps],
            }
        finally:
            db.close()

    # -------------------------------------------------- 与同步基线一致

    def test_plain_stream(self):
        agent_id = self._mk_agent("plain")
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="流式异步回答")])

        events = self._run_stream(agent_id, conv_id, fake, tools=[])
        joined = "".join(events)

        self.assertIn("event: ready", joined)
        self.assertIn('event: answer\ndata: {"content": "流式异步回答"}', joined)
        self.assertIn("event: done", joined)
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")
        self.assertEqual(run["final_answer"], "流式异步回答")

    def test_stream_tool_call(self):
        agent_id = self._mk_agent("tool")
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[
            AIMessage(content="", tool_calls=[{"name": "echo_tool", "args": {"text": "hi"}, "id": "c1"}]),
            AIMessage(content="工具跑完了"),
        ])

        events = self._run_stream(agent_id, conv_id, fake, tools=[echo_tool])
        joined = "".join(events)

        self.assertIn("event: tool_call", joined)
        self.assertIn("event: tool_result", joined)
        self.assertIn("event: done", joined)
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")
        self.assertIn("tool_call", run["step_types"])
        self.assertIn("tool_result", run["step_types"])
        self.assertIn("responder", run["step_types"])

    def test_stream_rag(self):
        agent_id = self._mk_agent("rag", rag_enabled=1)
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="带来源【来源1】")])
        fake_search = {
            "context": "【来源1】报销上限 2000。",
            "citations": [{"index": 1, "knowledge_id": 3, "file_name": "报销.pdf", "space_id": 1}],
            "hits": [{"knowledge_id": 3, "content": "报销上限 2000。", "score": 0.85}],
            "mode": "space", "refused": False,
        }
        with patch("service.rag.search_entry.search_for_agent_async",
                   new=AsyncMock(return_value=fake_search)):
            events = self._run_stream(agent_id, conv_id, fake, tools=[])
        joined = "".join(events)

        self.assertIn("event: retrieval", joined)
        self.assertIn("event: citations", joined)
        self.assertIn("event: done", joined)
        self.assertIn("报销上限 2000", fake.calls[0][0].content)
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")
        self.assertEqual(run["step_types"][0], "retrieval")

    def test_stream_memory_loaded_and_summarized(self):
        agent_id = self._mk_agent("mem", memory_enabled=1)
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="记住了")])

        from service.runtime import agent_runtime
        with patch.object(agent_runtime, "load_memory_async", new=AsyncMock(return_value="用户偏好简洁")), \
             patch.object(agent_runtime, "should_summarize_async", new=AsyncMock(return_value=True)), \
             patch.object(agent_runtime, "summarize_and_save_async", new=AsyncMock(return_value="新摘要")):
            events = self._run_stream(agent_id, conv_id, fake, tools=[])
        joined = "".join(events)

        self.assertIn("event: memory", joined)
        self.assertIn("长期记忆总结完成", joined)
        self.assertIn("用户偏好简洁", fake.calls[0][0].content)
        self.assertEqual(self._latest_run(conv_id)["status"], "finished")

    # -------------------------------------------------- 行为改进（vs 同步）

    def test_stream_llm_failure_persists_failed_run(self):
        agent_id = self._mk_agent("fail")
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(raise_on_call=RuntimeError("流式模型炸了"))

        events = self._run_stream(agent_id, conv_id, fake, tools=[])
        joined = "".join(events)

        self.assertIn("event: ready", joined)
        self.assertIn("event: error", joined)
        self.assertIn("服务暂时异常", joined)
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "failed")            # 同步版这里是 None（被回滚）
        self.assertIn("流式模型炸了", run["error_msg"] or "")

    def test_stream_memory_summarize_failure_keeps_finished_run(self):
        agent_id = self._mk_agent("memerr", memory_enabled=1)
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="回答正常")])

        from service.runtime import agent_runtime
        with patch.object(agent_runtime, "load_memory_async", new=AsyncMock(return_value="")), \
             patch.object(agent_runtime, "should_summarize_async", new=AsyncMock(return_value=True)), \
             patch.object(agent_runtime, "summarize_and_save_async",
                          new=AsyncMock(side_effect=RuntimeError("总结超时"))):
            events = self._run_stream(agent_id, conv_id, fake, tools=[])
        joined = "".join(events)

        self.assertIn("event: done", joined)
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")          # 同步版这里被 rollback 掉
        self.assertEqual(run["final_answer"], "回答正常")


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class ChatStreamRouteAsyncTest(unittest.TestCase):
    """POST /chat/{agent_id}/stream 走 get_async_db → chat_with_agent_stream_async。"""

    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.alice = rc.create_user("rts_alice")

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            uid = cls.alice["id"]
            db.execute(text("DELETE s FROM agent_step s JOIN agent_run r ON s.run_id=r.id WHERE r.user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM agent_run WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE m FROM message m JOIN conversation c ON m.conversation_id=c.id WHERE c.user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM conversation WHERE user_id=:u"), {"u": uid})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def test_stream_route_happy_path(self):
        from service.runtime import agent_runtime

        r = self.client.post("/agent", json={"name": f"rts-route-{self.alice['id']}"},
                             headers=self.alice["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        agent_id = r.json()["agent_id"]

        fake = _FakeLLM(responses=[AIMessage(content="路由流式回答")])
        with patch.object(agent_runtime, "ToolExecutor", lambda **kw: _StubExecutor(fake, [])):
            resp = self.client.post(f"/chat/{agent_id}/stream", json={"message": "你好"},
                                    headers=self.alice["headers"])

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.text
        self.assertIn("event: ready", body)
        self.assertIn("event: answer", body)
        self.assertIn("路由流式回答", body)
        self.assertIn("event: done", body)
        # done 里带 conversation_id
        import re
        m = re.search(r'"conversation_id":\s*(\d+)', body)
        self.assertIsNotNone(m, body)
        conv_id = int(m.group(1))

        msgs = self.client.get(f"/conversation/{conv_id}/messages", headers=self.alice["headers"])
        self.assertEqual(msgs.status_code, 200, msgs.text)
        contents = [mm["content"] for mm in msgs.json()]
        self.assertIn("你好", contents)
        self.assertIn("路由流式回答", contents)


if __name__ == "__main__":
    unittest.main()
