"""web_query 连接器：让用户已配置的联网模型去查，抠成结构化数据。

模型客户端整体打桩，不联网、不调真实模型。
"""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from service.widgets.connectors.web_query import CONNECTOR
from service.widgets.context import WidgetRunContext


def _ctx():
    return WidgetRunContext(user_id=1, now=datetime(2026, 9, 19, 9, 19), widget_id=7, db=object())


class _FakeClient:
    def __init__(self, answer):
        self._answer = answer
        self.web_search_flag = None

    async def achat(self, messages, temperature=0.5, web_search=False):
        self.web_search_flag = web_search
        return self._answer


class ValidateTest(unittest.TestCase):
    def test_query_required(self):
        self.assertTrue(CONNECTOR.validate_config({}))
        self.assertTrue(CONNECTOR.validate_config({"query": "  "}))
        self.assertEqual(CONNECTOR.validate_config({"query": "三角洲子弹价格"}), [])

    def test_blank_model_rejected(self):
        self.assertTrue(CONNECTOR.validate_config({"query": "x", "model": "  "}))


class FetchTest(unittest.IsolatedAsyncioTestCase):
    async def _fetch(self, answer, resolved=("glm-4", "k", "u"), config=None):
        client = _FakeClient(answer)
        with patch("service.llm.web_search.resolve_search_model_async",
                   new=AsyncMock(return_value=resolved)), \
             patch("service.llm.factory.LLMFactory.create", return_value=client):
            out = await CONNECTOR.fetch(_ctx(), config or {"query": "三角洲行动 子弹 交易行价格"})
        return out, client

    async def test_found_numeric_becomes_single_point_series(self):
        answer = ('{"found": true, "value": "1942.36 币", "unit": "游戏币", '
                  '"as_of": "2026-09-18", "note": "交易行均价", "sources": ["https://x.com/a"]}')
        out, client = await self._fetch(answer)
        self.assertTrue(out["found"])
        self.assertEqual(out["number"], 1942.36)
        self.assertEqual(out["rows"], [{"t": "2026-09-18", "y": 1942.36}])
        self.assertEqual(out["sources"], ["https://x.com/a"])
        self.assertFalse(out["low_confidence"])
        self.assertTrue(client.web_search_flag)          # 确实开了联网
        self.assertEqual(out["model"], "glm-4")
        # markdown 视图直接渲染 summary
        self.assertIn("1942.36", out["summary"])
        self.assertIn("2026-09-18", out["summary"])
        self.assertIn("https://x.com/a", out["summary"])

    async def test_found_non_numeric_still_has_summary_no_rows(self):
        out, _ = await self._fetch('{"found": true, "value": "价格在 1800~2000 币之间波动", "sources": []}')
        self.assertTrue(out["found"])
        self.assertIsNone(out["number"])
        self.assertTrue(out["low_confidence"])
        self.assertEqual(out["rows"], [])
        self.assertIn("1800~2000", out["summary"])
        self.assertIn("仅供参考", out["summary"])

    async def test_not_found_reports_reason_and_alternative_in_summary(self):
        out, _ = await self._fetch('{"found": false, "reason": "没有公开的每日价格数据"}')
        self.assertFalse(out["found"])
        self.assertIn("公开", out["reason"])
        self.assertEqual(out["rows"], [])
        self.assertIn("没有公开的每日价格数据", out["summary"])
        self.assertIn("sonar", out["summary"])          # 给替代方案
        self.assertIn("glm-4", out["summary"])          # 说清用的哪个模型

    async def test_garbage_answer_treated_as_not_found(self):
        out, _ = await self._fetch("我建议你去游戏交易平台看看。")
        self.assertFalse(out["found"])
        self.assertEqual(out["rows"], [])

    async def test_no_search_capable_model_raises_upstream(self):
        from service.exceptions import UpstreamError
        with self.assertRaises(UpstreamError):
            await self._fetch('{"found": true}', resolved=None)

    async def test_code_fence_answer_is_parsed(self):
        answer = '```json\n{"found": true, "value": 100, "as_of": "2026-09-19"}\n```'
        out, _ = await self._fetch(answer)
        self.assertTrue(out["found"])
        self.assertEqual(out["number"], 100.0)


if __name__ == "__main__":
    unittest.main()
