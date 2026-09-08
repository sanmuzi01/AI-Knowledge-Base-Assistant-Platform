import unittest

from service.user_dashboard_service import _build_recommendations


class UserDashboardServiceTest(unittest.TestCase):
    def test_recommendations_prioritize_missing_core_setup(self):
        items = _build_recommendations(
            agent_count=0,
            ready_agent_count=0,
            chat_model_count=0,
            embedding_model_count=0,
            knowledge_done_count=0,
            skill_count=0,
            profile_ready=False,
            failed_tasks=0,
            failed_runs_7d=0,
        )

        self.assertEqual(items[0]["key"], "connect-chat-model")
        self.assertEqual(items[0]["level"], "danger")
        self.assertIn("create-agent", {item["key"] for item in items})

    def test_recommendations_surface_operational_failures(self):
        items = _build_recommendations(
            agent_count=1,
            ready_agent_count=1,
            chat_model_count=1,
            embedding_model_count=1,
            knowledge_done_count=1,
            skill_count=1,
            profile_ready=True,
            failed_tasks=2,
            failed_runs_7d=3,
        )

        keys = [item["key"] for item in items]
        self.assertEqual(keys, ["failed-tasks", "failed-runs"])


if __name__ == "__main__":
    unittest.main()
