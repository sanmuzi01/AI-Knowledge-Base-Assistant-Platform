import unittest
from types import SimpleNamespace

from service.user_profile_service import format_user_profile_for_prompt, normalize_profile_payload, profile_to_dict


class UserProfileServiceTest(unittest.TestCase):
    def test_normalize_profile_payload_limits_and_fallbacks(self):
        payload = normalize_profile_payload({
            "occupation": "  后端工程师  ",
            "skills": "Python\n FastAPI   Vue",
            "preferences": "先给结论，再给步骤",
            "communication_style": "unknown",
            "persona": "bad",
            "extra_info": "x" * 1200,
        })

        self.assertEqual(payload["occupation"], "后端工程师")
        self.assertEqual(payload["skills"], "Python FastAPI Vue")
        self.assertEqual(payload["communication_style"], "balanced")
        self.assertEqual(payload["persona"], "professional")
        self.assertEqual(len(payload["extra_info"]), 1000)

    def test_profile_to_dict_defaults_when_missing(self):
        data = profile_to_dict(None)

        self.assertEqual(data["communication_style"], "balanced")
        self.assertEqual(data["persona"], "professional")
        self.assertEqual(data["occupation"], "")

    def test_format_user_profile_for_prompt(self):
        db = SimpleNamespace()
        profile = SimpleNamespace(
            occupation="学生",
            skills="Python 入门",
            preferences="多举例",
            communication_style="teacher",
            persona="teacher",
            extra_info="正在做 AI 助手项目",
            updated_at=None,
        )

        class Query:
            def filter(self, *_args):
                return self

            def first(self):
                return profile

        db.query = lambda *_args: Query()
        prompt = format_user_profile_for_prompt(db, 1)

        self.assertIn("用户画像与个性化要求", prompt)
        self.assertIn("学生", prompt)
        self.assertIn("耐心老师", prompt)
        self.assertIn("不要主动暴露", prompt)


if __name__ == "__main__":
    unittest.main()

