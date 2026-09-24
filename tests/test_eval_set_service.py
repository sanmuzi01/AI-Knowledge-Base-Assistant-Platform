"""固定评估集（EvalSet/EvalRun）的回归测试。

- `_diff_against_previous`：纯逻辑，测回归/变好问题的识别和指标差值计算。
- create/list/get/delete/run 全流程：真实 MySQL，`evaluate_rag_dataset` 打桩掉
  （不用真的连向量库/embedding），只验证持久化和跟上一轮自动比较这部分编排逻辑。

Phase 3 收尾（docs/sync-async-boundary.md）：`eval_set_service` 整层已经改成
AsyncSession（配合 evaluate_rag_dataset 切到 rag_service.search_async），
这里的生命周期测试跟着改用 AsyncSessionLocal + tests/_async_helpers.run_async。
"""
import unittest
from unittest.mock import patch

from service.evaluation import eval_set_service
from tests import _route_client as rc
from tests._async_helpers import run_async

_AVAILABLE, _WHY = rc.route_tests_available()


class DiffAgainstPreviousTest(unittest.TestCase):
    def test_no_previous_report_returns_none(self):
        report = {"cases": [], "metrics": {}}
        self.assertIsNone(eval_set_service._diff_against_previous(report, None))

    def test_detects_regression_and_improvement(self):
        previous = {
            "cases": [
                {"question": "Q1", "hit": True},
                {"question": "Q2", "hit": False},
                {"question": "Q3", "hit": True},
            ],
            "metrics": {"hit_rate": 0.8, "recall": 0.7},
        }
        current = {
            "cases": [
                {"question": "Q1", "hit": False},  # 回归：命中变没命中
                {"question": "Q2", "hit": True},   # 变好：没命中变命中
                {"question": "Q3", "hit": True},   # 不变
            ],
            "metrics": {"hit_rate": 0.6, "recall": 0.75},
        }
        diff = eval_set_service._diff_against_previous(current, previous)
        self.assertEqual(diff["regressed_questions"], ["Q1"])
        self.assertEqual(diff["improved_questions"], ["Q2"])
        self.assertEqual(diff["metric_deltas"]["hit_rate"], -0.2)
        self.assertEqual(diff["metric_deltas"]["recall"], 0.05)

    def test_ignores_questions_missing_from_previous(self):
        previous = {"cases": [{"question": "Q1", "hit": True}], "metrics": {}}
        current = {"cases": [{"question": "Q1", "hit": True}, {"question": "Q2", "hit": False}], "metrics": {}}
        diff = eval_set_service._diff_against_previous(current, previous)
        self.assertEqual(diff["regressed_questions"], [])
        self.assertEqual(diff["improved_questions"], [])


class CreateEvalSetValidationTest(unittest.TestCase):
    """create_eval_set 现在是 async def——校验逻辑在协程体最前面，不 await/run 就不会
    真的执行到 raise 那一行（协程是惰性的），所以这几个测试都要走 run_async。"""

    def test_requires_at_least_one_case(self):
        with self.assertRaises(ValueError):
            run_async(eval_set_service.create_eval_set(None, 1, "set", [], agent_id=1))

    def test_requires_agent_or_space(self):
        with self.assertRaises(ValueError):
            run_async(eval_set_service.create_eval_set(None, 1, "set", [{"question": "q"}]))

    def test_rejects_both_agent_and_space(self):
        with self.assertRaises(ValueError):
            run_async(eval_set_service.create_eval_set(
                None, 1, "set", [{"question": "q"}], agent_id=1, space_id=2,
            ))


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class EvalSetLifecycleDbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from models.init_db import SessionLocal, Agent

        cls.user = rc.create_user("evalset")
        db = SessionLocal()
        try:
            agent = Agent(user_id=cls.user["id"], name="eval-agent")
            db.add(agent)
            db.commit()
            cls.agent_id = agent.id
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM eval_run WHERE eval_set_id IN (SELECT id FROM eval_set WHERE agent_id=:a)"), {"a": cls.agent_id})
            db.execute(text("DELETE FROM eval_set WHERE agent_id=:a"), {"a": cls.agent_id})
            db.execute(text("DELETE FROM agent WHERE id=:a"), {"a": cls.agent_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def _fake_report(self, hit_q1: bool):
        return {
            "case_count": 1,
            "evaluated_retrieval_count": 1,
            "evaluated_faithfulness_count": 0,
            "metrics": {"hit_rate": 1.0 if hit_q1 else 0.0, "recall": None,
                        "precision_at_k": None, "mrr": None, "faithfulness": None},
            "cases": [{"question": "回收站文件能保留多久", "hit": hit_q1}],
            "settings": {},
        }

    def test_create_list_get_run_twice_and_diff(self):
        from models.async_db import AsyncSessionLocal

        async def _do():
            async with AsyncSessionLocal() as db:
                created = await eval_set_service.create_eval_set(
                    db, self.user["id"], "kb-basic",
                    [{"question": "回收站文件能保留多久"}],
                    agent_id=self.agent_id,
                )
                self.assertEqual(created["name"], "kb-basic")
                set_id = created["id"]

                listed = await eval_set_service.list_eval_sets(db, self.user["id"], agent_id=self.agent_id)
                self.assertEqual([s["id"] for s in listed], [set_id])

                fetched = await eval_set_service.get_eval_set(db, self.user["id"], set_id)
                self.assertEqual(fetched["id"], set_id)

                with patch("service.evaluation.eval_set_service.evaluate_rag_dataset",
                           side_effect=lambda *a, **k: self._fake_report(hit_q1=False)):
                    first_run = await eval_set_service.run_eval_set(db, self.user["id"], set_id)
                self.assertIsNone(first_run["diff"], "第一次运行没有上一轮，diff 应该是 None")
                self.assertEqual(first_run["report"]["metrics"]["hit_rate"], 0.0)

                with patch("service.evaluation.eval_set_service.evaluate_rag_dataset",
                           side_effect=lambda *a, **k: self._fake_report(hit_q1=True)):
                    second_run = await eval_set_service.run_eval_set(db, self.user["id"], set_id)
                self.assertIsNotNone(second_run["diff"])
                self.assertEqual(second_run["diff"]["improved_questions"], ["回收站文件能保留多久"])
                self.assertEqual(second_run["diff"]["metric_deltas"]["hit_rate"], 1.0)

                runs = await eval_set_service.list_eval_runs(db, self.user["id"], set_id)
                self.assertEqual(len(runs), 2)
                self.assertEqual(runs[0]["id"], second_run["run_id"], "按时间倒序，最新的排最前")

                await eval_set_service.delete_eval_set(db, self.user["id"], set_id)
                with self.assertRaises(ValueError):
                    await eval_set_service.get_eval_set(db, self.user["id"], set_id)

        run_async(_do())

    def test_get_or_run_unowned_set_raises(self):
        from models.async_db import AsyncSessionLocal

        async def _do():
            async with AsyncSessionLocal() as db:
                with self.assertRaises(ValueError):
                    await eval_set_service.get_eval_set(db, self.user["id"], 999999)
                with self.assertRaises(ValueError):
                    await eval_set_service.run_eval_set(db, self.user["id"], 999999)

        run_async(_do())


if __name__ == "__main__":
    unittest.main()
