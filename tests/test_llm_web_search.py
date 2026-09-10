"""service/llm/web_search.py：按 provider 开联网检索的适配层。"""

import unittest
from unittest.mock import AsyncMock, patch

from service.llm.web_search import (
    resolve_search_model_async,
    search_payload_extras,
    supports_web_search,
    web_search_model,
)


class CapabilityTest(unittest.TestCase):
    def test_supports_by_provider(self):
        for m in ("glm-4", "qwen-plus", "kimi-latest", "gpt-4o-mini", "sonar", "sonar-pro"):
            self.assertTrue(supports_web_search(m), m)
        for m in ("deepseek-chat", "deepseek-reasoner", "BAAI/bge-small-zh-v1.5"):
            self.assertFalse(supports_web_search(m), m)

    def test_web_search_model_swaps_only_openai(self):
        self.assertEqual(web_search_model("glm-4"), "glm-4")
        self.assertEqual(web_search_model("qwen-plus"), "qwen-plus")
        self.assertEqual(web_search_model("sonar"), "sonar")
        self.assertEqual(web_search_model("gpt-4o"), "gpt-4o-search-preview")
        self.assertEqual(web_search_model("gpt-4o-mini"), "gpt-4o-mini-search-preview")
        self.assertEqual(web_search_model("gpt-4o-search-preview"), "gpt-4o-search-preview")

    def test_payload_extras_per_provider(self):
        self.assertIn("tools", search_payload_extras("glm-4"))
        self.assertEqual(search_payload_extras("qwen-plus"), {"enable_search": True})
        self.assertEqual(search_payload_extras("kimi-latest")["tools"][0]["function"]["name"], "$web_search")
        self.assertEqual(search_payload_extras("sonar"), {})
        self.assertEqual(search_payload_extras("gpt-4o-mini"), {})
        self.assertEqual(search_payload_extras("deepseek-chat"), {})


class _Cfg:
    def __init__(self, name, active=True):
        self.model_name = name
        self.is_active = active


_DEFAULT_CFG = object()


class ResolveModelTest(unittest.IsolatedAsyncioTestCase):
    async def _resolve(self, configs, api_cfg=_DEFAULT_CFG, preferred=None):
        if api_cfg is _DEFAULT_CFG:
            api_cfg = {"api_key": "k", "api_url": "u", "model_name": "x"}
        with patch("models.llm_config_async_dao.list_configs_by_user_async",
                   new=AsyncMock(return_value=configs)), \
             patch("service.llm.llm_config_service.async_get_api_config",
                   new=AsyncMock(return_value=api_cfg)):
            return await resolve_search_model_async(db=object(), user_id=1, preferred=preferred)

    async def test_picks_first_search_capable(self):
        out = await self._resolve([_Cfg("deepseek-chat"), _Cfg("glm-4")])
        self.assertEqual(out, ("glm-4", "k", "https://open.bigmodel.cn/api/paas/v4/chat/completions"))

    async def test_openai_swaps_to_search_preview_same_key(self):
        out = await self._resolve([_Cfg("gpt-4o-mini")])
        self.assertEqual(out[0], "gpt-4o-mini-search-preview")
        self.assertEqual(out[1], "k")

    async def test_preferred_wins_when_capable(self):
        out = await self._resolve([_Cfg("glm-4"), _Cfg("qwen-plus")], preferred="qwen-plus")
        self.assertEqual(out[0], "qwen-plus")

    async def test_none_when_only_deepseek(self):
        out = await self._resolve([_Cfg("deepseek-chat")])
        self.assertIsNone(out)

    async def test_none_when_no_key(self):
        out = await self._resolve([_Cfg("glm-4")], api_cfg=None)
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
