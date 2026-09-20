"""Agent 流水线（service/agent_pipeline_service.py）回归测试。

`run_pipeline_async` 内部调用的 chat_service.chat_with_agent 全部 mock 掉——
真实跑需要网络和真实 API Key；这里只验证编排逻辑本身：上一步答案传给下一步、
某步失败就停在那一步、配额用尽同样会停下来且不抛出未处理异常。
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from service.exceptions import InvalidInput, NotFound, QuotaExceeded
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


def _run(coro):
    return asyncio.run(coro)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AgentPipelineCrudTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("rt-pipeline-user")
        cls.other = rc.create_user("rt-pipeline-other")
        from models.init_db import SessionLocal, Agent

        db = SessionLocal()
        try:
            a1 = Agent(user_id=cls.user["id"], name="rt-pipeline-agent-1")
            a2 = Agent(user_id=cls.user["id"], name="rt-pipeline-agent-2")
            other_agent = Agent(user_id=cls.other["id"], name="rt-pipeline-other-agent")
            db.add_all([a1, a2, other_agent])
            db.commit()
            cls.agent1_id, cls.agent2_id = a1.id, a2.id
            cls.other_agent_id = other_agent.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM agent_pipeline WHERE user_id IN (:u1,:u2)"),
                       {"u1": cls.user["id"], "u2": cls.other["id"]})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def test_create_requires_min_two_steps(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import create_pipeline_async

        async def _do():
            async with AsyncSessionLocal() as db:
                return await create_pipeline_async(
                    db, self.user["id"], "太短", None, [{"agent_id": self.agent1_id}],
                )

        with self.assertRaises(InvalidInput):
            _run(_do())

    def test_create_rejects_unowned_agent(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import create_pipeline_async

        async def _do():
            async with AsyncSessionLocal() as db:
                return await create_pipeline_async(
                    db, self.user["id"], "偷用别人的助手", None,
                    [{"agent_id": self.agent1_id}, {"agent_id": self.other_agent_id}],
                )

        with self.assertRaises(InvalidInput):
            _run(_do())

    def test_create_list_update_delete_lifecycle(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import (
            create_pipeline_async, delete_pipeline_async, list_pipelines_async, update_pipeline_async,
        )

        async def _create():
            async with AsyncSessionLocal() as db:
                return await create_pipeline_async(
                    db, self.user["id"], "先总结再润色", "测试流水线",
                    [{"agent_id": self.agent1_id, "label": "总结"}, {"agent_id": self.agent2_id, "label": "润色"}],
                )

        created = _run(_create())
        self.assertEqual(len(created["steps"]), 2)
        pipeline_id = created["id"]

        async def _list():
            async with AsyncSessionLocal() as db:
                return await list_pipelines_async(db, self.user["id"])

        items = _run(_list())
        self.assertTrue(any(p["id"] == pipeline_id for p in items))

        async def _update():
            async with AsyncSessionLocal() as db:
                return await update_pipeline_async(db, self.user["id"], pipeline_id, {"is_enabled": False})

        updated = _run(_update())
        self.assertFalse(updated["is_enabled"])

        async def _delete():
            async with AsyncSessionLocal() as db:
                return await delete_pipeline_async(db, self.user["id"], pipeline_id)

        result = _run(_delete())
        self.assertEqual(result["message"], "流水线已删除")

    def test_update_nonexistent_raises_not_found(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import update_pipeline_async

        async def _do():
            async with AsyncSessionLocal() as db:
                return await update_pipeline_async(db, self.user["id"], 999999999, {"is_enabled": True})

        with self.assertRaises(NotFound):
            _run(_do())


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class AgentPipelineRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.user = rc.create_user("rt-pipeline-run")
        from models.init_db import SessionLocal, Agent

        db = SessionLocal()
        try:
            a1 = Agent(user_id=cls.user["id"], name="rt-run-agent-1")
            a2 = Agent(user_id=cls.user["id"], name="rt-run-agent-2")
            db.add_all([a1, a2])
            db.commit()
            cls.agent1_id, cls.agent2_id = a1.id, a2.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM agent_pipeline WHERE user_id=:u"), {"u": cls.user["id"]})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def _fake_user(self):
        from types import SimpleNamespace
        return SimpleNamespace(id=self.user["id"])

    def _make_pipeline(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import create_pipeline_async

        async def _do():
            async with AsyncSessionLocal() as db:
                return await create_pipeline_async(
                    db, self.user["id"], "两步流水线", None,
                    [{"agent_id": self.agent1_id}, {"agent_id": self.agent2_id}],
                )

        return _run(_do())["id"]

    def test_second_step_receives_first_steps_answer(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import run_pipeline_async

        pipeline_id = self._make_pipeline()
        calls = []

        async def fake_chat(db, user, agent_id, user_message, conversation_id=None):
            calls.append(user_message)
            return {"answer": f"回答自 agent {agent_id}", "conversation_id": 1}

        async def _do():
            async with AsyncSessionLocal() as db:
                with patch("service.agent_pipeline_service.chat_service.chat_with_agent", fake_chat), \
                     patch("service.agent_pipeline_service.quota_service.enforce_quota_async",
                           AsyncMock(return_value={"used_tokens": 0})), \
                     patch("service.agent_pipeline_service.quota_service.check_and_notify_threshold_async",
                           AsyncMock()):
                    return await run_pipeline_async(db, self._fake_user(), pipeline_id, "初始问题")

        result = _run(_do())
        self.assertTrue(result["completed"])
        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(calls[0], "初始问题")
        self.assertEqual(calls[1], f"回答自 agent {self.agent1_id}")
        self.assertEqual(result["final_answer"], f"回答自 agent {self.agent2_id}")

    def test_stops_at_failed_step_without_running_later_steps(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import run_pipeline_async

        pipeline_id = self._make_pipeline()
        calls = []

        async def fake_chat(db, user, agent_id, user_message, conversation_id=None):
            calls.append(agent_id)
            if agent_id == self.agent1_id:
                return {"message": "智能体不存在或无权限"}  # 没有 answer key，代表失败
            return {"answer": "不应该跑到这里", "conversation_id": 1}

        async def _do():
            async with AsyncSessionLocal() as db:
                with patch("service.agent_pipeline_service.chat_service.chat_with_agent", fake_chat), \
                     patch("service.agent_pipeline_service.quota_service.enforce_quota_async",
                           AsyncMock(return_value={"used_tokens": 0})), \
                     patch("service.agent_pipeline_service.quota_service.check_and_notify_threshold_async",
                           AsyncMock()):
                    return await run_pipeline_async(db, self._fake_user(), pipeline_id, "初始问题")

        result = _run(_do())
        self.assertFalse(result["completed"])
        self.assertEqual(len(result["steps"]), 1)
        self.assertFalse(result["steps"][0]["ok"])
        self.assertEqual(calls, [self.agent1_id])  # 第二步压根没被调用

    def test_stops_when_quota_exceeded_mid_pipeline(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import run_pipeline_async

        pipeline_id = self._make_pipeline()

        async def fake_enforce(db, user_id):
            raise QuotaExceeded("本月配额已用完")

        async def _do():
            async with AsyncSessionLocal() as db:
                with patch("service.agent_pipeline_service.chat_service.chat_with_agent",
                           AsyncMock(return_value={"answer": "不应该被调用", "conversation_id": 1})), \
                     patch("service.agent_pipeline_service.quota_service.enforce_quota_async", fake_enforce):
                    return await run_pipeline_async(db, self._fake_user(), pipeline_id, "初始问题")

        result = _run(_do())
        self.assertFalse(result["completed"])
        self.assertFalse(result["steps"][0]["ok"])
        self.assertIn("配额", result["steps"][0]["error"])

    def test_run_nonexistent_pipeline_raises_not_found(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import run_pipeline_async

        async def _do():
            async with AsyncSessionLocal() as db:
                return await run_pipeline_async(db, self._fake_user(), 999999999, "问题")

        with self.assertRaises(NotFound):
            _run(_do())

    def test_run_disabled_pipeline_raises_invalid_input(self):
        from models.async_db import AsyncSessionLocal
        from service.agent_pipeline_service import run_pipeline_async, update_pipeline_async

        pipeline_id = self._make_pipeline()

        async def _disable():
            async with AsyncSessionLocal() as db:
                await update_pipeline_async(db, self.user["id"], pipeline_id, {"is_enabled": False})

        _run(_disable())

        async def _do():
            async with AsyncSessionLocal() as db:
                return await run_pipeline_async(db, self._fake_user(), pipeline_id, "问题")

        with self.assertRaises(InvalidInput):
            _run(_do())


if __name__ == "__main__":
    unittest.main()
