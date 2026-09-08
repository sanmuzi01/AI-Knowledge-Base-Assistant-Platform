import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from service import background_task_service


class _FakeDb:
    def flush(self):
        return None


class BackgroundTaskRetryTest(unittest.TestCase):
    def test_failed_task_is_requeued_until_retry_limit(self):
        task = SimpleNamespace(
            id=1,
            status="running",
            progress=10,
            error_msg=None,
            retry_count=0,
            started_at=None,
            finished_at=None,
            next_run_at=None,
        )

        with patch.dict(os.environ, {
            "TASK_MAX_AUTO_RETRIES": "2",
            "TASK_RETRY_BASE_SECONDS": "10",
            "TASK_RETRY_MAX_SECONDS": "60",
        }):
            background_task_service._mark_task_failed_or_retry(_FakeDb(), task, "boom")

        self.assertEqual(task.status, "queued")
        self.assertEqual(task.retry_count, 1)
        self.assertEqual(task.progress, 0)
        self.assertIsNotNone(task.next_run_at)
        self.assertIn("自动重试", task.error_msg)

    def test_failed_task_stops_after_retry_limit(self):
        task = SimpleNamespace(
            id=2,
            status="running",
            progress=10,
            error_msg=None,
            retry_count=2,
            started_at=None,
            finished_at=None,
            next_run_at=None,
        )

        with patch.dict(os.environ, {"TASK_MAX_AUTO_RETRIES": "2"}):
            background_task_service._mark_task_failed_or_retry(_FakeDb(), task, "boom")

        self.assertEqual(task.status, "failed")
        self.assertEqual(task.retry_count, 2)
        self.assertEqual(task.progress, 100)
        self.assertIsNone(task.next_run_at)


if __name__ == "__main__":
    unittest.main()
