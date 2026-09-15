"""阶段 1 —— agent_runtime 下游服务/DAO 的 async 双胞胎与同步版行为一致性。

对照点（`docs/agent-runtime-async-migration.md` 阶段 1 表）：
  - models/agent_run_async_dao: create_run / create_step / update_run_status / *finished_runs*
  - service/memory_async_service: load_memory / should_summarize / summarize_and_save
  - service/user_profile_async_service: format_user_profile_for_prompt / infer_user_profile_from_summary
  - service/conversation_async_service: save_message / load_history_for_llm / maybe_update_title...

每个 async 版跑真实 DB，断言与同步版在同一批数据上输出一致。LLM 调用按需 patch。
无法连库时整体 skip。
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


def _run(coro):
    return asyncio.run(coro)


async def _with_async_session(fn):
    """每次用独立事件循环（asyncio.run），跑完把 async 引擎连接池在**同一循环内**释放，
    避免 asyncmy 连接被跨循环 GC 时刷 'NoneType has no attribute send' 噪音。"""
    from models.async_db import AsyncSessionLocal, async_engine
    try:
        async with AsyncSessionLocal() as s:
            return await fn(s)
    finally:
        await async_engine.dispose()


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class AsyncDepsParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("adep")

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
            db.execute(text("DELETE FROM user_profile WHERE user_id=:u"), {"u": uid})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    # -------------------------------------------------- fixtures

    def _mk_agent(self, tag):
        from models.init_db import SessionLocal
        from models.agent_dao import create_agent
        db = SessionLocal()
        try:
            a = create_agent(db, name=f"adep-{tag}", user_id=self.user["id"],
                             model_name="glm-4", rag_enabled=0, memory_enabled=1, temperature=70)
            db.commit()
            return a.id
        finally:
            db.close()

    def _seed_finished_runs(self, agent_id, n):
        from models.init_db import SessionLocal, AgentRun
        from utils.timeutil import utcnow
        db = SessionLocal()
        try:
            for i in range(n):
                db.add(AgentRun(
                    user_id=self.user["id"], agent_id=agent_id,
                    user_message=f"q{i}", final_answer=f"a{i}",
                    status="finished", started_at=utcnow(), finished_at=utcnow(),
                ))
            db.commit()
        finally:
            db.close()

    def _seed_summary(self, agent_id, content, chat_count):
        from models.init_db import SessionLocal, Memory
        db = SessionLocal()
        try:
            db.add(Memory(user_id=self.user["id"], agent_id=agent_id,
                          memory_type="summary", content=content, chat_count=chat_count))
            db.commit()
        finally:
            db.close()

    # -------------------------------------------------- load_memory

    def test_load_memory_parity(self):
        from service.memory.memory_service import load_memory
        from service.memory_async_service import load_memory_async
        from models.init_db import SessionLocal, Memory

        agent_id = self._mk_agent("mem")
        db = SessionLocal()
        try:
            for mt, c in [("summary", "用户是产品经理"), ("fact", "在做 A 项目"),
                          ("preference", "喜欢简洁"), ("note", "   ")]:
                db.add(Memory(user_id=self.user["id"], agent_id=agent_id, memory_type=mt, content=c))
            db.commit()
        finally:
            db.close()

        with SessionLocal() as s:
            sync_text = load_memory(s, self.user["id"], agent_id)
        async_text = _run(_with_async_session(
            lambda a: load_memory_async(a, self.user["id"], agent_id)))

        self.assertEqual(sync_text, async_text)
        self.assertIn("对话摘要", sync_text)
        self.assertNotIn("[备注]", sync_text)  # 空内容被过滤

    def test_load_memory_empty_parity(self):
        from service.memory.memory_service import load_memory
        from service.memory_async_service import load_memory_async
        from models.init_db import SessionLocal

        agent_id = self._mk_agent("memempty")
        with SessionLocal() as s:
            sync_text = load_memory(s, self.user["id"], agent_id)
        async_text = _run(_with_async_session(
            lambda a: load_memory_async(a, self.user["id"], agent_id)))
        self.assertEqual(sync_text, "")
        self.assertEqual(async_text, "")

    # -------------------------------------------------- should_summarize

    def test_should_summarize_parity_below_and_at_threshold(self):
        from service.memory.memory_service import should_summarize
        from service.memory_async_service import should_summarize_async
        from models.init_db import SessionLocal

        agent_id = self._mk_agent("sum")
        # 4 轮已完成 + 无历史摘要 → diff=4 < 5 → False
        self._seed_finished_runs(agent_id, 4)
        with SessionLocal() as s:
            sync_lo = should_summarize(s, self.user["id"], agent_id)
        async_lo = _run(_with_async_session(
            lambda a: should_summarize_async(a, self.user["id"], agent_id)))
        self.assertEqual(sync_lo, async_lo)
        self.assertFalse(sync_lo)

        # 补到 5 轮 → diff=5 >= 5 → True
        self._seed_finished_runs(agent_id, 1)
        with SessionLocal() as s:
            sync_hi = should_summarize(s, self.user["id"], agent_id)
        async_hi = _run(_with_async_session(
            lambda a: should_summarize_async(a, self.user["id"], agent_id)))
        self.assertEqual(sync_hi, async_hi)
        self.assertTrue(sync_hi)

    def test_should_summarize_parity_with_prior_summary(self):
        from service.memory.memory_service import should_summarize
        from service.memory_async_service import should_summarize_async
        from models.init_db import SessionLocal

        agent_id = self._mk_agent("sum2")
        self._seed_finished_runs(agent_id, 8)
        self._seed_summary(agent_id, "旧摘要", chat_count=5)  # diff = 8-5 = 3 < 5 → False

        with SessionLocal() as s:
            sync_v = should_summarize(s, self.user["id"], agent_id)
        async_v = _run(_with_async_session(
            lambda a: should_summarize_async(a, self.user["id"], agent_id)))
        self.assertEqual(sync_v, async_v)
        self.assertFalse(sync_v)

    # -------------------------------------------------- user profile prompt

    def test_format_user_profile_parity(self):
        from service.user_profile_service import save_user_profile, format_user_profile_for_prompt
        from service.user_profile_async_service import format_user_profile_for_prompt_async
        from models.init_db import SessionLocal

        with SessionLocal() as s:
            save_user_profile(s, self.user["id"], {
                "occupation": "产品经理", "skills": "SQL, 增长",
                "preferences": "先给结论", "communication_style": "concise",
                "persona": "analyst", "extra_info": "带一个 5 人小队",
            })
            sync_text = format_user_profile_for_prompt(s, self.user["id"])
        async_text = _run(_with_async_session(
            lambda a: format_user_profile_for_prompt_async(a, self.user["id"])))
        self.assertEqual(sync_text, async_text)
        self.assertIn("产品经理", sync_text)

    def test_format_user_profile_empty_parity(self):
        from service.user_profile_service import format_user_profile_for_prompt
        from service.user_profile_async_service import format_user_profile_for_prompt_async
        from models.init_db import SessionLocal

        # 新建一个没有 profile 的用户
        u2 = rc.create_user("adep2")
        with SessionLocal() as s:
            sync_text = format_user_profile_for_prompt(s, u2["id"])
        async_text = _run(_with_async_session(
            lambda a: format_user_profile_for_prompt_async(a, u2["id"])))
        # 无 profile 时同步版会带默认「风格/人格」两行，两版仍需一致
        self.assertEqual(sync_text, async_text)

    # -------------------------------------------------- conversation helpers

    def _mk_conv(self, agent_id, title="新会话"):
        from models.init_db import SessionLocal
        import models.conversation_dao as cdao
        db = SessionLocal()
        try:
            c = cdao.create_conversation(db, user_id=self.user["id"], agent_id=agent_id, title=title)
            db.commit()
            return c.id
        finally:
            db.close()

    def test_load_history_for_llm_parity(self):
        from service.conversation_service import load_history_for_llm, save_message
        from service.conversation_async_service import load_history_for_llm_async
        from models.init_db import SessionLocal

        agent_id = self._mk_agent("hist")
        conv_id = self._mk_conv(agent_id)
        with SessionLocal() as s:
            save_message(s, conv_id, "user", "第一句")
            save_message(s, conv_id, "assistant", "第一答")
            save_message(s, conv_id, "system", "系统提示应被过滤")
            save_message(s, conv_id, "user", "第二句")
            s.commit()
            sync_hist = load_history_for_llm(s, conv_id, limit=20)
        async_hist = _run(_with_async_session(
            lambda a: load_history_for_llm_async(a, conv_id, limit=20)))
        self.assertEqual(sync_hist, async_hist)
        self.assertEqual([m["role"] for m in sync_hist], ["user", "assistant", "user"])

    def test_save_message_async_creates_row_and_touches_conv(self):
        from service.conversation_async_service import save_message_async
        from models.init_db import SessionLocal, Message, Conversation

        agent_id = self._mk_agent("save")
        conv_id = self._mk_conv(agent_id)
        with SessionLocal() as s:
            before = s.query(Conversation).filter(Conversation.id == conv_id).first().update_time

        async def _do(a):
            msg = await save_message_async(a, conv_id, "user", "异步存的消息")
            await a.commit()
            return msg.id
        mid = _run(_with_async_session(_do))

        with SessionLocal() as s:
            row = s.query(Message).filter(Message.id == mid).first()
            self.assertIsNotNone(row)
            self.assertEqual(row.content, "异步存的消息")
            after = s.query(Conversation).filter(Conversation.id == conv_id).first().update_time
            self.assertGreaterEqual(after, before)

    def test_maybe_update_title_parity(self):
        from service.conversation_service import maybe_update_title_by_first_message
        from service.conversation_async_service import maybe_update_title_by_first_message_async
        from models.init_db import SessionLocal, Conversation

        agent_id = self._mk_agent("title")
        # 默认标题 → 两版都应改成消息摘要
        c_sync = self._mk_conv(agent_id)
        c_async = self._mk_conv(agent_id)
        msg = "帮我梳理一下这个季度的增长复盘框架和关键指标口径"
        with SessionLocal() as s:
            maybe_update_title_by_first_message(s, c_sync, msg)
            s.commit()

        async def _do(a):
            await maybe_update_title_by_first_message_async(a, c_async, msg)
            await a.commit()
        _run(_with_async_session(_do))

        with SessionLocal() as s:
            t_sync = s.query(Conversation).filter(Conversation.id == c_sync).first().title
            t_async = s.query(Conversation).filter(Conversation.id == c_async).first().title
        self.assertEqual(t_sync, t_async)
        self.assertNotEqual(t_sync, "新会话")

        # 非默认标题 → 两版都不动
        c2_sync = self._mk_conv(agent_id, title="已有标题")
        c2_async = self._mk_conv(agent_id, title="已有标题")
        with SessionLocal() as s:
            maybe_update_title_by_first_message(s, c2_sync, msg)
            s.commit()
        _run(_with_async_session(
            lambda a: maybe_update_title_by_first_message_async(a, c2_async, msg)))
        with SessionLocal() as s:
            self.assertEqual(s.query(Conversation).filter(Conversation.id == c2_sync).first().title, "已有标题")
            self.assertEqual(s.query(Conversation).filter(Conversation.id == c2_async).first().title, "已有标题")

    # -------------------------------------------------- agent_run write DAOs

    def test_agent_run_write_daos_parity(self):
        from models.agent_run_dao import (
            count_finished_runs_by_agent, list_finished_runs_by_agent,
        )
        from models.agent_run_async_dao import (
            create_run_async, create_step_async, update_run_status_async,
            count_finished_runs_by_agent_async, list_finished_runs_by_agent_async,
        )
        from models.init_db import SessionLocal, AgentRun, AgentStep

        agent_id = self._mk_agent("run")

        async def _do(a):
            run = await create_run_async(
                a, user_id=self.user["id"], agent_id=agent_id,
                user_message="异步问题", conversation_id=None)
            await create_step_async(
                a, run_id=run.id, step_no=1, step_type="retrieval",
                thought="检索", tool_name="rag_search", tool_result="命中2条")
            await update_run_status_async(
                a, run=run, status="finished", final_answer="异步答", total_steps=1)
            await a.commit()
            return run.id
        run_id = _run(_with_async_session(_do))

        with SessionLocal() as s:
            run = s.query(AgentRun).filter(AgentRun.id == run_id).first()
            self.assertEqual(run.status, "finished")
            self.assertEqual(run.final_answer, "异步答")
            self.assertEqual(run.total_steps, 1)
            self.assertIsNotNone(run.finished_at)
            steps = s.query(AgentStep).filter(AgentStep.run_id == run_id).all()
            self.assertEqual(len(steps), 1)
            self.assertEqual(steps[0].step_type, "retrieval")

            sync_count = count_finished_runs_by_agent(s, self.user["id"], agent_id)
            sync_list = list_finished_runs_by_agent(s, self.user["id"], agent_id)

        async_count = _run(_with_async_session(
            lambda a: count_finished_runs_by_agent_async(a, self.user["id"], agent_id)))
        async_list = _run(_with_async_session(
            lambda a: list_finished_runs_by_agent_async(a, self.user["id"], agent_id)))
        self.assertEqual(sync_count, async_count)
        self.assertEqual(sync_count, 1)
        self.assertEqual([r.id for r in sync_list], [r.id for r in async_list])

    # -------------------------------------------------- summarize_and_save

    def test_summarize_and_save_parity(self):
        from models.init_db import SessionLocal, Memory
        from service.memory.memory_service import summarize_and_save
        from service.memory_async_service import summarize_and_save_async

        canned = "用户是产品经理，负责 A 项目，偏好简洁回答。"

        agent_sync = self._mk_agent("ssync")
        agent_async = self._mk_agent("sasync")
        self._seed_finished_runs(agent_sync, 9)
        self._seed_finished_runs(agent_async, 9)

        async def _fake_async_chat_with_usage(**kw):
            return canned, {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

        with patch("service.llm.llm_service.chat", return_value=canned), \
             patch("service.llm.llm_service.async_chat_with_usage", side_effect=_fake_async_chat_with_usage), \
             patch("service.user_profile_service.infer_user_profile_from_summary", return_value=None), \
             patch("service.user_profile_async_service.infer_user_profile_from_summary_async",
                   new=AsyncMock(return_value=None)):
            with SessionLocal() as s:
                sync_ret = summarize_and_save(s, self.user["id"], agent_sync, "glm-4")
                s.commit()

            usage_sink: list = []

            async def _do(a):
                r = await summarize_and_save_async(
                    a, self.user["id"], agent_async, "glm-4", usage_sink=usage_sink,
                )
                await a.commit()
                return r
            async_ret = _run(_with_async_session(_do))

        self.assertEqual(sync_ret, async_ret)
        self.assertEqual(sync_ret, canned)
        # usage_sink 收到了这次总结调用的用量，供 agent_runtime 把它并进 run 的 total_tokens
        self.assertEqual(usage_sink, [{"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}])
        with SessionLocal() as s:
            for aid in (agent_sync, agent_async):
                mems = (s.query(Memory)
                        .filter(Memory.agent_id == aid, Memory.memory_type == "summary").all())
                self.assertEqual(len(mems), 1)
                self.assertEqual(mems[0].content, canned)
                self.assertEqual(mems[0].chat_count, 9)


if __name__ == "__main__":
    unittest.main()
