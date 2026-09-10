"""`run_with_history_async` / async `chat_with_agent` 行为验证（真实 DB + mock LLM）。

除了聊天执行的基本可观察行为（AgentRun / AgentStep 落库、RAG / memory 编排），还断言两处
**相对旧同步实现的行为改进**（修同步版事务怪癖）：
  1. run 记录尽早 commit → LLM 失败也留下 status='failed' 的 AgentRun；
  2. 记忆总结跑在独立 AsyncSession → 总结失败不回滚已 finished 的 run。

LLM 经 stub `ToolExecutor` 注入 FakeLLM（`tests/_runtime_fakes.py`）。无法连库时整体 skip。
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from tests import _route_client as rc
from tests._runtime_fakes import _FakeLLM, _StubExecutor, echo_tool

_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class RunWithHistoryAsyncTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("rta")

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

    # -------------------------------------------------- fixtures

    def _mk_agent(self, tag, **overrides):
        from models.init_db import SessionLocal
        from models.agent_dao import create_agent
        db = SessionLocal()
        try:
            fields = dict(name=f"rta-{tag}", user_id=self.user["id"], model_name="glm-4",
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

    def _run_async(self, agent_id, conv_id, fake, tools, message="你好", history=None):
        from models.async_db import AsyncSessionLocal, async_engine
        from service.runtime import agent_runtime

        async def _go():
            try:
                async with AsyncSessionLocal() as db:
                    with patch.object(agent_runtime, "ToolExecutor",
                                      lambda **kw: _StubExecutor(fake, tools)):
                        return await agent_runtime.run_with_history_async(
                            db=db, user_id=self.user["id"], agent_id=agent_id,
                            user_message=message, history=history or [], conversation_id=conv_id,
                        )
            finally:
                await async_engine.dispose()
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
                "id": run.id if run else None,
                "status": run.status if run else None,
                "final_answer": run.final_answer if run else None,
                "error_msg": run.error_msg if run else None,
                "total_steps": run.total_steps if run else None,
                "step_types": [s.step_type for s in steps],
            }
        finally:
            db.close()

    # -------------------------------------------------- 与同步基线一致的部分

    def test_plain_conversation(self):
        agent_id = self._mk_agent("plain")
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="异步回答")])

        result = self._run_async(agent_id, conv_id, fake, tools=[])

        self.assertEqual(result["answer"], "异步回答")
        self.assertEqual(result["rag_mode"], "off")
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")
        self.assertEqual(run["final_answer"], "异步回答")
        self.assertEqual(run["step_types"], ["responder"])
        self.assertEqual(fake.calls[0][0].type, "system")

    def test_single_tool_call_round_trip(self):
        agent_id = self._mk_agent("tool")
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[
            AIMessage(content="", tool_calls=[{"name": "echo_tool", "args": {"text": "hi"}, "id": "c1"}]),
            AIMessage(content="工具跑完了"),
        ])

        result = self._run_async(agent_id, conv_id, fake, tools=[echo_tool])

        self.assertEqual(result["answer"], "工具跑完了")
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")
        self.assertIn("tool_call", run["step_types"])
        self.assertIn("tool_result", run["step_types"])
        self.assertIn("responder", run["step_types"])

    def test_rag_enabled_composes_context_and_citations(self):
        agent_id = self._mk_agent("rag", rag_enabled=1)
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="带来源【来源1】")])
        fake_search = {
            "context": "【来源1】年假 5 天。",
            "citations": [{"index": 1, "knowledge_id": 9, "file_name": "假期.pdf", "space_id": 2}],
            "hits": [{"knowledge_id": 9, "content": "年假 5 天。", "score": 0.9}],
            "mode": "space", "refused": False,
        }
        with patch("service.rag.search_entry.search_for_agent_async",
                   new=AsyncMock(return_value=fake_search)):
            result = self._run_async(agent_id, conv_id, fake, tools=[])

        self.assertEqual(result["citations"], fake_search["citations"])
        self.assertEqual(result["rag_mode"], "space")
        self.assertIn("年假 5 天", fake.calls[0][0].content)
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")
        self.assertEqual(run["step_types"][0], "retrieval")

    def test_memory_injected_and_summarize_triggered(self):
        agent_id = self._mk_agent("mem", memory_enabled=1)
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="记住了")])

        from service.runtime import agent_runtime
        with patch.object(agent_runtime, "load_memory_async", new=AsyncMock(return_value="用户偏好简洁")), \
             patch.object(agent_runtime, "should_summarize_async", new=AsyncMock(return_value=True)), \
             patch.object(agent_runtime, "summarize_and_save_async", new=AsyncMock(return_value="新摘要")) as save:
            result = self._run_async(agent_id, conv_id, fake, tools=[])

        self.assertEqual(result["answer"], "记住了")
        self.assertIn("用户偏好简洁", fake.calls[0][0].content)
        save.assert_awaited_once()
        self.assertEqual(self._latest_run(conv_id)["status"], "finished")

    # -------------------------------------------------- 行为改进 1：失败也留 run

    def test_llm_failure_persists_failed_run_and_reraises(self):
        agent_id = self._mk_agent("fail")
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(raise_on_call=RuntimeError("模型 500"))

        with self.assertRaises(RuntimeError) as ctx:
            self._run_async(agent_id, conv_id, fake, tools=[])
        self.assertIn("模型 500", str(ctx.exception))

        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "failed")          # 同步版这里是 None（被回滚）
        self.assertIn("模型 500", run["error_msg"] or "")

    # -------------------------------------------------- 行为改进 2：总结失败不连累 run

    def test_memory_summarize_failure_keeps_finished_run(self):
        agent_id = self._mk_agent("memerr", memory_enabled=1)
        conv_id = self._mk_conv(agent_id)
        fake = _FakeLLM(responses=[AIMessage(content="回答正常")])

        from service.runtime import agent_runtime
        with patch.object(agent_runtime, "load_memory_async", new=AsyncMock(return_value="")), \
             patch.object(agent_runtime, "should_summarize_async", new=AsyncMock(return_value=True)), \
             patch.object(agent_runtime, "summarize_and_save_async",
                          new=AsyncMock(side_effect=RuntimeError("总结 LLM 超时"))):
            result = self._run_async(agent_id, conv_id, fake, tools=[])

        self.assertEqual(result["answer"], "回答正常")
        run = self._latest_run(conv_id)
        self.assertEqual(run["status"], "finished")        # 同步版这里是 None（被回滚）
        self.assertEqual(run["final_answer"], "回答正常")


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class ChatRouteAsyncTest(unittest.TestCase):
    """POST /chat/{agent_id} 走 get_async_db → chat_with_agent → run_with_history_async。"""

    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.alice = rc.create_user("rtc_alice")
        cls.bob = rc.create_user("rtc_bob")

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            ids = tuple(u["id"] for u in (cls.alice, cls.bob))
            inc = "(" + ",".join(str(i) for i in ids) + ")"
            db.execute(text(f"DELETE s FROM agent_step s JOIN agent_run r ON s.run_id=r.id WHERE r.user_id IN {inc}"))
            db.execute(text(f"DELETE FROM agent_run WHERE user_id IN {inc}"))
            db.execute(text(f"DELETE m FROM message m JOIN conversation c ON m.conversation_id=c.id WHERE c.user_id IN {inc}"))
            db.execute(text(f"DELETE FROM conversation WHERE user_id IN {inc}"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def _mk_agent(self, user):
        r = self.client.post("/agent", json={"name": f"rtc-agent-{user['id']}"}, headers=user["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["agent_id"]

    def test_chat_happy_path_and_persists_message(self):
        from service.runtime import agent_runtime

        agent_id = self._mk_agent(self.alice)
        fake = _FakeLLM(responses=[AIMessage(content="路由层异步回答")])

        with patch.object(agent_runtime, "ToolExecutor", lambda **kw: _StubExecutor(fake, [])):
            r = self.client.post(f"/chat/{agent_id}", json={"message": "你好"}, headers=self.alice["headers"])

        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["answer"], "路由层异步回答")
        conv_id = body["conversation_id"]
        self.assertIsNotNone(conv_id)

        # 用户消息 + AI 消息都落库
        msgs = self.client.get(f"/conversation/{conv_id}/messages", headers=self.alice["headers"])
        self.assertEqual(msgs.status_code, 200, msgs.text)
        contents = [m["content"] for m in msgs.json()]
        self.assertIn("你好", contents)
        self.assertIn("路由层异步回答", contents)

    def test_chat_cross_user_conversation_rejected(self):
        from service.runtime import agent_runtime

        agent_id = self._mk_agent(self.alice)
        fake = _FakeLLM(responses=[AIMessage(content="x")])
        with patch.object(agent_runtime, "ToolExecutor", lambda **kw: _StubExecutor(fake, [])):
            first = self.client.post(f"/chat/{agent_id}", json={"message": "hi"}, headers=self.alice["headers"])
            conv_id = first.json()["conversation_id"]
            # bob 拿 alice 的 conversation_id 发消息 → 归属校验失败
            bad = self.client.post(
                f"/chat/{agent_id}",
                json={"message": "偷看", "conversation_id": conv_id},
                headers=self.bob["headers"],
            )
        self.assertIn(bad.status_code, (400, 403, 404), bad.text)


if __name__ == "__main__":
    unittest.main()
