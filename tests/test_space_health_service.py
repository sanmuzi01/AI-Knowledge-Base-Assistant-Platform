"""知识库空间健康分：纯逻辑单测（评分 / 比率 / 过期阈值 / Widget connector 校验）。

不依赖 DB。`_collect_*` 与 `health_snapshot` 走 ORM，端到端由路由级测试覆盖。
"""

import os
import unittest
from unittest.mock import patch

from service.knowledge_space import health_service as hs


class RateAndStaleTest(unittest.TestCase):
    def test_rate(self):
        self.assertEqual(hs._rate(1, 4), 0.25)
        self.assertEqual(hs._rate(0, 0), 0.0)
        self.assertEqual(hs._rate(3, 3), 1.0)

    def test_stale_days_env(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KB_STALE_DAYS", None)
            self.assertEqual(hs._stale_days(), 90)
        with patch.dict(os.environ, {"KB_STALE_DAYS": "30"}):
            self.assertEqual(hs._stale_days(), 30)
        with patch.dict(os.environ, {"KB_STALE_DAYS": "oops"}):
            self.assertEqual(hs._stale_days(), 90)


def _docs(**over):
    base = dict(total=10, enabled=10, done=10, failed=0, pending=0, empty_done=0, stale=0,
                failed_rate=0.0, pending_rate=0.0, stale_rate=0.0, disabled_rate=0.0, chunk_count=100)
    base.update(over)
    return base


def _samples(**over):
    base = dict(sample_count=0, hit_rate=None, refuse_rate=None, citation_rate=None, useful_rate=None)
    base.update(over)
    return base


class ScoreTest(unittest.TestCase):
    def test_empty_space_is_neutral(self):
        self.assertEqual(hs._score(_docs(total=0), _samples()), 60)

    def test_all_healthy_is_100(self):
        self.assertEqual(hs._score(_docs(), _samples()), 100)

    def test_failed_docs_drag_score_down(self):
        s = hs._score(_docs(failed=5, failed_rate=0.5), _samples())
        self.assertLess(s, 80)  # 0.5 * 45 = 22.5 扣分

    def test_stale_and_pending_penalised(self):
        s = hs._score(_docs(stale=10, stale_rate=1.0, pending=10, pending_rate=1.0), _samples())
        self.assertLessEqual(s, 65)

    def test_samples_below_3_do_not_count(self):
        low_hit = _samples(sample_count=2, hit_rate=0.0, refuse_rate=1.0)
        self.assertEqual(hs._score(_docs(), low_hit), 100)

    def test_samples_at_3_bring_hit_rate_in(self):
        low_hit = _samples(sample_count=3, hit_rate=0.0, refuse_rate=0.0, useful_rate=None)
        self.assertEqual(hs._score(_docs(), low_hit), 85)  # 100 - (1-0)*15

    def test_score_clamped_0_100(self):
        wreck = _docs(failed=10, failed_rate=1.0, pending=10, pending_rate=1.0,
                      stale=10, stale_rate=1.0, empty_done=10)
        s = hs._score(wreck, _samples(sample_count=5, hit_rate=0.0, refuse_rate=1.0, useful_rate=0.0))
        self.assertGreaterEqual(s, 0)
        self.assertLessEqual(s, 100)


class ComputeHealthLevelTest(unittest.TestCase):
    def test_level_thresholds(self):
        with patch.object(hs, "_collect_doc_metrics", return_value=_docs()), \
             patch.object(hs, "_collect_sample_metrics", return_value=_samples()):
            self.assertEqual(hs.compute_health(object(), 1)["level"], "good")
        with patch.object(hs, "_collect_doc_metrics", return_value=_docs(failed=6, failed_rate=0.6)), \
             patch.object(hs, "_collect_sample_metrics", return_value=_samples()):
            out = hs.compute_health(object(), 1)
            self.assertEqual(out["health_score"], 73)
            self.assertEqual(out["level"], "fair")
        with patch.object(hs, "_collect_doc_metrics",
                          return_value=_docs(failed=9, failed_rate=0.9, stale=5, stale_rate=0.5)), \
             patch.object(hs, "_collect_sample_metrics", return_value=_samples()):
            self.assertEqual(hs.compute_health(object(), 1)["level"], "poor")


class WidgetConnectorTest(unittest.TestCase):
    def test_validate_config(self):
        from service.widgets.connectors.knowledge_space import CONNECTOR

        self.assertEqual(CONNECTOR.kind, "knowledge_space")
        self.assertTrue(CONNECTOR.validate_config({}))
        self.assertTrue(CONNECTOR.validate_config({"space_id": 0}))
        self.assertEqual(CONNECTOR.validate_config({"space_id": 5}), [])

    def test_registered_in_schema_and_registry(self):
        from service.widgets import schema
        from service.widgets.connectors import CONNECTORS

        self.assertIn("knowledge_space", schema.CONNECTOR_KINDS)
        self.assertIn("knowledge_space", schema.CONNECTOR_LABELS)
        self.assertTrue(CONNECTORS.has("knowledge_space"))


if __name__ == "__main__":
    unittest.main()
