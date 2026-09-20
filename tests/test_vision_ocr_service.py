"""service/llm/vision_ocr.py 的单测：挑视觉模型的逻辑、OCR 请求的多模态 content 组装。"""
import unittest
from unittest.mock import MagicMock, patch

from service.llm.vision_ocr import ocr_image, resolve_vision_model, supports_vision


class SupportsVisionTest(unittest.TestCase):
    def test_known_vision_models(self):
        self.assertTrue(supports_vision("glm-4v"))
        self.assertTrue(supports_vision("gpt-4o"))
        self.assertTrue(supports_vision("gpt-4o-mini"))

    def test_non_vision_chat_model(self):
        self.assertFalse(supports_vision("glm-4"))
        self.assertFalse(supports_vision("deepseek-chat"))


class ResolveVisionModelTest(unittest.TestCase):
    def test_picks_first_active_vision_capable_config(self):
        cfg_chat = MagicMock(model_name="glm-4", is_active=1)
        cfg_vision = MagicMock(model_name="glm-4v", is_active=1)
        with patch("models.llm_config_dao.list_configs_by_user", return_value=[cfg_chat, cfg_vision]), \
             patch("service.llm.llm_config_service.get_api_config",
                   return_value={"model_name": "glm-4v", "api_key": "k", "api_url": None}):
            result = resolve_vision_model(db=MagicMock(), user_id=1)
        self.assertEqual(result, ("glm-4v", "k", None))

    def test_no_vision_model_configured_returns_none(self):
        cfg_chat = MagicMock(model_name="glm-4", is_active=1)
        with patch("models.llm_config_dao.list_configs_by_user", return_value=[cfg_chat]):
            result = resolve_vision_model(db=MagicMock(), user_id=1)
        self.assertIsNone(result)

    def test_inactive_vision_config_is_skipped(self):
        cfg_vision = MagicMock(model_name="glm-4v", is_active=0)
        with patch("models.llm_config_dao.list_configs_by_user", return_value=[cfg_vision]):
            result = resolve_vision_model(db=MagicMock(), user_id=1)
        self.assertIsNone(result)


class OcrImageTest(unittest.TestCase):
    def test_builds_multimodal_message_and_returns_stripped_text(self):
        fake_client = MagicMock()
        fake_client.chat.return_value = "  识别出的文字  "
        with patch("service.llm.factory.LLMFactory.create", return_value=fake_client):
            result = ocr_image("glm-4v", "key", None, "base64data")

        self.assertEqual(result, "识别出的文字")
        call_args = fake_client.chat.call_args
        messages = call_args.args[0] if call_args.args else call_args.kwargs["messages"]
        content = messages[0]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertIn("base64data", content[1]["image_url"]["url"])

    def test_no_text_sentinel_returns_empty_string(self):
        fake_client = MagicMock()
        fake_client.chat.return_value = "无文字内容"
        with patch("service.llm.factory.LLMFactory.create", return_value=fake_client):
            result = ocr_image("glm-4v", "key", None, "base64data")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
