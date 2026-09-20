"""create_langchain_llm 的 base_url 拼接回归测试。

真实踩过的坑：model_catalog.CHAT_MODELS[...]["api_url"] 存的是完整的
chat/completions 端点 URL（GLMClient/OpenAICompatibleClient 直接拿去用没问题），
但这里传给 LangChain ChatOpenAI(base_url=...) 时，LangChain 自己会再拼一次
/chat/completions——不去掉这个后缀就会拼成 .../chat/completions/chat/completions，
导致所有绑了工具/技能、走 ReAct 引擎的智谱模型 Agent 每次对话都 404。
"""
import unittest
from unittest.mock import MagicMock, patch

from service.llm.langchain_adapter import create_langchain_llm


class CreateLangchainLlmBaseUrlTest(unittest.TestCase):
    def _fake_chat_openai(self):
        """拦住真实的 ChatOpenAI 构造（会校验网络相关参数），只看传进去的 kwargs。"""
        captured = {}

        def _fake(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        return captured, _fake

    def test_strips_chat_completions_suffix_from_api_config_url(self):
        captured, fake_ctor = self._fake_chat_openai()
        with patch("service.llm.langchain_adapter.get_api_config", return_value={
            "api_key": "k", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        }), patch("service.llm.langchain_adapter.ChatOpenAI", side_effect=fake_ctor):
            create_langchain_llm(db=None, user_id=1, model_name="glm-4")

        self.assertEqual(captured["base_url"], "https://open.bigmodel.cn/api/paas/v4")

    def test_leaves_root_only_url_untouched(self):
        captured, fake_ctor = self._fake_chat_openai()
        with patch("service.llm.langchain_adapter.get_api_config", return_value={
            "api_key": "k", "api_url": "https://api.deepseek.com/v1",
        }), patch("service.llm.langchain_adapter.ChatOpenAI", side_effect=fake_ctor):
            create_langchain_llm(db=None, user_id=1, model_name="deepseek-chat")

        self.assertEqual(captured["base_url"], "https://api.deepseek.com/v1")

    def test_explicit_api_url_param_also_gets_suffix_stripped(self):
        captured, fake_ctor = self._fake_chat_openai()
        with patch("service.llm.langchain_adapter.get_api_config", return_value={"api_key": "k", "api_url": None}), \
             patch("service.llm.langchain_adapter.ChatOpenAI", side_effect=fake_ctor):
            create_langchain_llm(
                db=None, user_id=1, model_name="glm-4",
                api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions/",
            )

        self.assertEqual(captured["base_url"], "https://open.bigmodel.cn/api/paas/v4")

    def test_missing_config_raises_actionable_error(self):
        with patch("service.llm.langchain_adapter.get_api_config", return_value=None):
            with self.assertRaises(ValueError):
                create_langchain_llm(db=None, user_id=1, model_name="glm-4")


if __name__ == "__main__":
    unittest.main()
