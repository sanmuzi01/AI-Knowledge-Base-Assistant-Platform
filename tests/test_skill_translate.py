"""Skill 名称/说明翻译：只测解析、权限、失败兜底；模型调用全部用假客户端。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from service.skills_core import translate
from service.skills_core.translate import TranslateError, needs_translation, translate_skill


class FakeClient:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.seen = reply, error, None

    def chat(self, messages, temperature=0.2):
        self.seen = messages[0]["content"]
        if self.error:
            raise self.error
        return self.reply


class NeedsTranslationTest(unittest.TestCase):
    def test_only_text_without_any_chinese_needs_it(self):
        self.assertTrue(needs_translation("Use this skill whenever the user wants PDF files"))
        self.assertFalse(needs_translation("PDF 处理"))
        self.assertFalse(needs_translation(""))


class ParseTest(unittest.TestCase):
    def test_accepts_plain_and_fenced_json(self):
        good = '{"name": "PDF 处理", "description": "读取、合并、拆分 PDF。"}'
        self.assertEqual(translate._parse(good)["name"], "PDF 处理")
        self.assertEqual(translate._parse("```json\n" + good + "\n```")["description"], "读取、合并、拆分 PDF。")
        self.assertEqual(translate._parse("好的：" + good)["name"], "PDF 处理")

    def test_rejects_garbage_missing_fields_and_untranslated(self):
        for bad in ("not json", "{}", '{"name": "x"}', '{"name": "pdf", "description": "still english"}'):
            with self.assertRaises(TranslateError, msg=bad):
                translate._parse(bad)


class TranslateSkillTest(unittest.TestCase):
    def setUp(self):
        self.skill = SimpleNamespace(id=1, user_id=7, name="pdf", description="Use this skill for PDF files")
        self.saved = {}

        def fake_update(db, skill_id, user_id, **kw):
            self.saved = kw
            return {"id": skill_id, **kw}

        self._p = [
            patch.object(translate, "dao_get", return_value=self.skill),
            patch.object(translate, "update_skill", side_effect=fake_update),
            patch.object(translate, "_pick_chat_model", return_value=("glm-4", "key", None)),
        ]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in self._p:
            p.stop()

    def _with_client(self, client):
        return patch("service.llm.factory.LLMFactory.create", return_value=client)

    def test_translates_and_saves_name_and_description(self):
        client = FakeClient('{"name": "PDF 处理", "description": "读取、合并、拆分 PDF。"}')
        with self._with_client(client):
            result = translate_skill(SimpleNamespace(), 1, user_id=7)
        self.assertEqual(self.saved, {"name": "PDF 处理", "description": "读取、合并、拆分 PDF。"})
        self.assertEqual(result["name"], "PDF 处理")
        self.assertIn("Use this skill for PDF files", client.seen)

    def test_not_your_skill_returns_none_without_calling_the_model(self):
        with self._with_client(FakeClient("x")) as create:
            self.assertIsNone(translate_skill(SimpleNamespace(), 1, user_id=999))
        create.assert_not_called()

    def test_no_chat_model_gives_actionable_message(self):
        with patch.object(translate, "_pick_chat_model", return_value=None):
            with self.assertRaises(TranslateError) as ctx:
                translate_skill(SimpleNamespace(), 1, user_id=7)
        self.assertIn("模型配置", str(ctx.exception))

    def test_provider_error_is_not_leaked_to_the_user(self):
        with self._with_client(FakeClient(error=RuntimeError("401 key sk-secret-123 invalid"))):
            with self.assertRaises(TranslateError) as ctx:
                translate_skill(SimpleNamespace(), 1, user_id=7)
        self.assertNotIn("sk-secret", str(ctx.exception))
        self.assertEqual(self.saved, {})


if __name__ == "__main__":
    unittest.main()
