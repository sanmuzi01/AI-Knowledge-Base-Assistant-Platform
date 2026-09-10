"""「一次连接，多项能力」：POST /llm_config/quick_connect。

选平台 + 粘一次 Key → 原子保存聊天 + 资料读取两条配置并逐条测试。
连通性测试（async_test_config）打桩，不打真实模型。需要本地 MySQL，连不上则 skip。
"""

import unittest
from unittest.mock import AsyncMock, patch

from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


def _ok(model_name, kind):
    return {"ok": True, "model_name": model_name, "kind": kind, "message": "连接正常", "elapsed_ms": 5}


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class QuickConnectRouteTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.user = rc.create_user("qc")

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM llm_config WHERE user_id=:u"), {"u": cls.user["id"]})
            db.commit()
        finally:
            db.close()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    def _configs(self):
        r = self.client.get("/llm_config/list", headers=self.user["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        return {c["model_name"]: c for c in r.json()}

    def test_zhipu_connects_chat_and_embedding_in_one_call(self):
        async def fake_test(db, user, model_name):
            return _ok(model_name, "embedding" if "embedding" in model_name else "chat")

        with patch("service.llm.llm_config_service.async_test_config", new=AsyncMock(side_effect=fake_test)):
            r = self.client.post("/llm_config/quick_connect", headers=self.user["headers"],
                                 json={"provider": "zhipu", "api_key": "sk-zhipu-demo"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(sorted(body["saved"]), ["embedding-3", "glm-4"])
        self.assertEqual(body["skipped"], [])
        self.assertTrue(body["results"]["glm-4"]["ok"])
        self.assertTrue(body["results"]["embedding-3"]["ok"])

        cfgs = self._configs()
        self.assertIn("glm-4", cfgs)
        self.assertIn("embedding-3", cfgs)
        self.assertEqual(cfgs["glm-4"]["kind"], "chat")
        self.assertEqual(cfgs["embedding-3"]["kind"], "embedding")

    def test_deepseek_saves_chat_only_and_reports_skip(self):
        with patch("service.llm.llm_config_service.async_test_config",
                   new=AsyncMock(side_effect=lambda db, u, m: _ok(m, "chat"))):
            r = self.client.post("/llm_config/quick_connect", headers=self.user["headers"],
                                 json={"provider": "deepseek", "api_key": "sk-ds-demo"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["saved"], ["deepseek-chat"])
        self.assertEqual(body["skipped"], [{"capability": "embedding", "reason": "该平台暂不支持"}])
        self.assertIn("deepseek-chat", self._configs())

    def test_capabilities_filter_chat_only(self):
        with patch("service.llm.llm_config_service.async_test_config",
                   new=AsyncMock(side_effect=lambda db, u, m: _ok(m, "chat"))):
            r = self.client.post("/llm_config/quick_connect", headers=self.user["headers"],
                                 json={"provider": "openai", "api_key": "sk-oa", "capabilities": ["chat"]})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["saved"], ["gpt-4o-mini"])
        self.assertNotIn("text-embedding-3-small", self._configs())

    def test_re_connect_updates_existing_key(self):
        calls = []

        async def fake_test(db, user, model_name):
            calls.append(model_name)
            return _ok(model_name, "chat")

        with patch("service.llm.llm_config_service.async_test_config", new=AsyncMock(side_effect=fake_test)):
            self.client.post("/llm_config/quick_connect", headers=self.user["headers"],
                             json={"provider": "qwen", "api_key": "sk-qwen-1"})
            r2 = self.client.post("/llm_config/quick_connect", headers=self.user["headers"],
                                  json={"provider": "qwen", "api_key": "sk-qwen-2"})
        self.assertEqual(r2.status_code, 200, r2.text)
        # 第二次是更新，不应报重复/冲突，配置里 qwen-plus 只有一条
        cfgs = [c for c in self._configs() if c == "qwen-plus"]
        self.assertEqual(len(cfgs), 1)


if __name__ == "__main__":
    unittest.main()
