"""真实路由级测试：登录鉴权 + 跨用户 / 管理员权限隔离。

走真实 FastAPI 应用（TestClient）、真实 JWT、真实 DB。无法连库或缺 JWT_SECRET_KEY 时整体 skip。
"""

import unittest

from tests import _route_client as rc


_AVAILABLE, _WHY = rc.route_tests_available()


@unittest.skipUnless(_AVAILABLE, f"路由级测试环境不可用：{_WHY}")
class RouteIsolationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = rc.make_client()
        cls.client.__enter__()
        cls.alice = rc.create_user("alice")
        cls.bob = rc.create_user("bob")
        cls.admin = rc.create_user("admin")
        cls._admin_env = rc.admin_env(cls.admin["name"])
        cls._admin_env.start()

    @classmethod
    def tearDownClass(cls):
        cls._admin_env.stop()
        try:
            cls.client.__exit__(None, None, None)
        finally:
            rc.cleanup()

    # ---- 登录 / 鉴权门槛 ----

    def test_login_success_and_wrong_password(self):
        ok = self.client.post("/user/login", json={"name": self.alice["name"], "password": self.alice["password"]})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertIn("access_token", ok.json())

        bad = self.client.post("/user/login", json={"name": self.alice["name"], "password": "wrong-password"})
        self.assertEqual(bad.status_code, 401)

    def test_protected_route_requires_token(self):
        self.assertIn(self.client.get("/user/widgets").status_code, (401, 403))
        self.assertEqual(self.client.get("/user/widgets", headers=self.alice["headers"]).status_code, 200)

    # ---- 组件跨用户隔离 ----

    def _create_widget(self, user) -> int:
        draft = {"type": "metric", "data_source": {"kind": "system_stats"}, "trigger": {"kind": "manual"}}
        r = self.client.post("/user/widgets", json={"draft": draft}, headers=user["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def test_widget_is_private_to_owner(self):
        wid = self._create_widget(self.alice)

        # 本人可见
        mine = self.client.get("/user/widgets", headers=self.alice["headers"]).json()["items"]
        self.assertIn(wid, [w["id"] for w in mine])

        # 别人拿不到 —— 读 / 运行 / 导出 / 改 / 删 全部 404
        h = self.bob["headers"]
        self.assertEqual(self.client.get(f"/user/widgets/{wid}/data", headers=h).status_code, 404)
        self.assertEqual(self.client.post(f"/user/widgets/{wid}/run", headers=h).status_code, 404)
        self.assertEqual(self.client.get(f"/user/widgets/{wid}/export", headers=h).status_code, 404)
        self.assertEqual(self.client.patch(f"/user/widgets/{wid}", json={"name": "x"}, headers=h).status_code, 404)
        self.assertEqual(self.client.delete(f"/user/widgets/{wid}", headers=h).status_code, 404)

        # bob 的列表里也不该出现
        theirs = self.client.get("/user/widgets", headers=h).json()["items"]
        self.assertNotIn(wid, [w["id"] for w in theirs])

    # ---- 知识库跨用户隔离 ----

    def test_knowledge_agent_is_private_to_owner(self):
        r = self.client.post("/agent", json={"name": f"rt-agent-{self.alice['id']}"}, headers=self.alice["headers"])
        self.assertEqual(r.status_code, 200, r.text)
        agent_id = r.json().get("agent_id")
        self.assertIsNotNone(agent_id, r.text)

        # 同步 def 端点 + 领域异常：别人删 / 删不存在 都要 404（且带 code 字段）
        gone = self.client.delete(f"/agent/{agent_id}", headers=self.bob["headers"])
        self.assertEqual(gone.status_code, 404)
        self.assertEqual(gone.json().get("code"), "not_found")
        self.assertEqual(self.client.delete("/agent/999999", headers=self.alice["headers"]).status_code, 404)

        # bob 查 alice 的知识库诊断 —— 不放行
        got = self.client.get(f"/knowledge/{agent_id}/diagnostics", headers=self.bob["headers"])
        self.assertIn(got.status_code, (403, 404))

        # alice 自己可以
        self.assertEqual(
            self.client.get(f"/knowledge/{agent_id}/diagnostics", headers=self.alice["headers"]).status_code, 200
        )

        # 纯读接口（已全量 async）：本人 200、别人 404
        self.assertEqual(self.client.get(f"/knowledge/{agent_id}/list", headers=self.alice["headers"]).status_code, 200)
        self.assertEqual(self.client.get(f"/knowledge/{agent_id}/list", headers=self.bob["headers"]).status_code, 404)
        self.assertEqual(self.client.get("/knowledge/my/list", headers=self.alice["headers"]).status_code, 200)
        self.assertEqual(
            self.client.get(f"/knowledge/{agent_id}/999999", headers=self.alice["headers"]).status_code, 404
        )

        # 检索：本人过了归属校验（测试用户没配 embedding Key，会在向量化那步 400），别人在归属校验就 404
        mine = self.client.post(f"/knowledge/{agent_id}/search", json={"query": "x", "top_k": 3},
                                headers=self.alice["headers"])
        self.assertIn(mine.status_code, (200, 400), mine.text)
        if mine.status_code == 400:
            self.assertIn("API Key", mine.text)          # 说明已越过归属校验，卡在向量化
        self.assertEqual(
            self.client.post(f"/knowledge/{agent_id}/search", json={"query": "x"},
                             headers=self.bob["headers"]).status_code, 404
        )

    # ---- 知识库空间：CRUD + 跨用户隔离 ----

    def test_knowledge_space_is_private_to_owner(self):
        c = self.client.post(
            "/knowledge-spaces",
            json={"name": f"rt-space-{self.alice['id']}", "purpose": "policy", "tags": ["制度"]},
            headers=self.alice["headers"],
        )
        self.assertEqual(c.status_code, 200, c.text)
        sid = c.json()["id"]

        mine = self.client.get("/knowledge-spaces", headers=self.alice["headers"]).json()
        self.assertIn(sid, [s["id"] for s in mine["items"]])
        self.assertTrue(any(p["key"] == "policy" for p in mine["purposes"]))

        h = self.bob["headers"]
        self.assertEqual(self.client.get(f"/knowledge-spaces/{sid}", headers=h).status_code, 404)
        self.assertEqual(self.client.patch(f"/knowledge-spaces/{sid}", json={"name": "x"}, headers=h).status_code, 404)
        d = self.client.delete(f"/knowledge-spaces/{sid}", headers=h)
        self.assertEqual(d.status_code, 404)
        self.assertEqual(d.json().get("code"), "not_found")
        self.assertNotIn(sid, [s["id"] for s in self.client.get("/knowledge-spaces", headers=h).json()["items"]])

        # owner 改名
        self.assertEqual(
            self.client.patch(f"/knowledge-spaces/{sid}", json={"name": "改过的名字"},
                              headers=self.alice["headers"]).status_code, 200
        )

        # 空间内文档：上传 -> 列表 -> 跨用户隔离 -> 删除
        up = self.client.post(
            f"/knowledge-spaces/{sid}/documents",
            files={"file": ("rt-note.txt", b"hello knowledge space", "text/plain")},
            headers=self.alice["headers"],
        )
        self.assertEqual(up.status_code, 200, up.text)
        kid = up.json()["knowledge_id"]

        lst = self.client.get(f"/knowledge-spaces/{sid}/documents", headers=self.alice["headers"])
        self.assertEqual(lst.status_code, 200)
        self.assertIn(kid, [d["id"] for d in lst.json()["items"]])

        self.assertEqual(self.client.get(f"/knowledge-spaces/{sid}/documents", headers=h).status_code, 404)
        self.assertEqual(
            self.client.delete(f"/knowledge-spaces/{sid}/documents/{kid}", headers=h).status_code, 404
        )
        self.assertEqual(
            self.client.delete(f"/knowledge-spaces/{sid}/documents/{kid}", headers=self.alice["headers"]).status_code, 200
        )

        # 清空文档后 owner 可删空间
        self.assertEqual(
            self.client.delete(f"/knowledge-spaces/{sid}", headers=self.alice["headers"]).status_code, 200
        )

    # ---- Agent 绑定知识库空间：绑定校验 + 越权 ----

    def _make_space(self, user, name: str) -> int:
        r = self.client.post(
            "/knowledge-spaces",
            json={"name": name, "purpose": "policy"},
            headers=user["headers"],
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def test_agent_space_binding_and_cross_user_reject(self):
        s1 = self._make_space(self.alice, f"rt-bind-a-{self.alice['id']}")
        s2 = self._make_space(self.alice, f"rt-bind-b-{self.alice['id']}")
        bob_space = self._make_space(self.bob, f"rt-bind-bob-{self.bob['id']}")

        # 创建时绑定自己的两个空间 + kb_* 配置
        c = self.client.post(
            "/agent",
            json={"name": f"rt-kb-agent-{self.alice['id']}", "rag_enabled": 1,
                  "space_ids": [s1, s2], "kb_top_k": 8, "kb_force_citation": 1},
            headers=self.alice["headers"],
        )
        self.assertEqual(c.status_code, 200, c.text)
        agent_id = c.json()["agent_id"]

        got = self.client.get(f"/agent/{agent_id}", headers=self.alice["headers"]).json()
        self.assertCountEqual(got.get("space_ids", []), [s1, s2])
        self.assertEqual(got.get("kb_top_k"), 8)

        # 改绑：只留 s1
        u = self.client.put(f"/agent/{agent_id}", json={"space_ids": [s1]}, headers=self.alice["headers"])
        self.assertEqual(u.status_code, 200, u.text)
        got = self.client.get(f"/agent/{agent_id}", headers=self.alice["headers"]).json()
        self.assertEqual(got.get("space_ids"), [s1])

        # 绑定别人的空间 -> 400（校验挡在 access_control.user_space_ids）
        bad = self.client.put(
            f"/agent/{agent_id}", json={"space_ids": [s1, bob_space]}, headers=self.alice["headers"]
        )
        self.assertEqual(bad.status_code, 400, bad.text)

        # 创建时就绑别人的空间 -> 400
        bad2 = self.client.post(
            "/agent",
            json={"name": f"rt-kb-bad-{self.alice['id']}", "space_ids": [bob_space]},
            headers=self.alice["headers"],
        )
        self.assertEqual(bad2.status_code, 400, bad2.text)

        # 清理绑定后删 Agent + 空间
        self.client.put(f"/agent/{agent_id}", json={"space_ids": []}, headers=self.alice["headers"])
        self.client.delete(f"/agent/{agent_id}", headers=self.alice["headers"])
        for sid in (s1, s2):
            self.client.delete(f"/knowledge-spaces/{sid}", headers=self.alice["headers"])
        self.client.delete(f"/knowledge-spaces/{bob_space}", headers=self.bob["headers"])

    # ---- 知识库调试台：越权检索 / 样例隔离 ----

    def test_rag_debug_console_isolation(self):
        sid = self._make_space(self.alice, f"rt-dbg-{self.alice['id']}")
        h_a, h_b = self.alice["headers"], self.bob["headers"]

        # alice 对自己的空间跑检索：过了归属校验，卡在向量化（测试用户没配 embedding Key）
        mine = self.client.post(
            "/rag-debug/run", json={"query": "年假几天", "space_ids": [sid], "top_k": 3}, headers=h_a
        )
        self.assertIn(mine.status_code, (200, 400), mine.text)

        # bob 用 alice 的 space_id 跑检索 -> 403（PermissionError 在向量化之前）
        theirs = self.client.post(
            "/rag-debug/run", json={"query": "年假几天", "space_ids": [sid], "top_k": 3}, headers=h_b
        )
        self.assertEqual(theirs.status_code, 403, theirs.text)

        # 存一条样例（不依赖检索是否成功，result 可为空快照）
        saved = self.client.post(
            "/rag-debug/samples",
            json={"query": "年假几天", "space_ids": [sid],
                  "result": {"hits": [], "context": "", "citations": []},
                  "verdict": "useless", "in_eval_set": True},
            headers=h_a,
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        sample_id = saved.json()["id"]

        # 列表 / 导出：本人可见，别人 404 / 空
        mine_list = self.client.get(f"/rag-debug/samples?space_id={sid}", headers=h_a).json()
        self.assertIn(sample_id, [s["id"] for s in mine_list["items"]])
        self.assertEqual(self.client.get(f"/rag-debug/samples?space_id={sid}", headers=h_b).status_code, 404)

        exported = self.client.get(f"/rag-debug/samples/export?space_id={sid}", headers=h_a).json()
        self.assertEqual(exported["total"], 1)
        self.assertEqual(exported["cases"][0]["expected_knowledge_ids"], [])  # useless -> 期望查不到

        # 别人改 / 删这条样例 -> 404
        self.assertEqual(
            self.client.patch(f"/rag-debug/samples/{sample_id}", json={"verdict": "useful"}, headers=h_b).status_code, 404
        )
        self.assertEqual(self.client.delete(f"/rag-debug/samples/{sample_id}", headers=h_b).status_code, 404)

        # 本人删除后清理空间
        self.assertEqual(self.client.delete(f"/rag-debug/samples/{sample_id}", headers=h_a).status_code, 200)
        self.client.delete(f"/knowledge-spaces/{sid}", headers=h_a)

    # ---- 知识库健康分 + 按空间评估：越权隔离 ----

    def test_space_health_and_eval_isolation(self):
        sid = self._make_space(self.alice, f"rt-health-{self.alice['id']}")
        h_a, h_b = self.alice["headers"], self.bob["headers"]

        # 本人：健康分实时算，返回明细 + 分数
        ok = self.client.get(f"/knowledge-spaces/{sid}/health", headers=h_a)
        self.assertEqual(ok.status_code, 200, ok.text)
        body = ok.json()
        self.assertIsInstance(body["health_score"], int)
        self.assertIn("documents", body)
        self.assertIn("retrieval", body)

        # 别人：404（不泄露存在性）
        self.assertEqual(self.client.get(f"/knowledge-spaces/{sid}/health", headers=h_b).status_code, 404)

        # 按空间评估：本人过了归属校验（无 embedding Key 时卡在向量化 -> 400）；别人 404
        mine = self.client.post(
            f"/evaluation/space/{sid}/rag", json={"cases": [{"question": "年假几天"}], "top_k": 3}, headers=h_a
        )
        self.assertIn(mine.status_code, (200, 400), mine.text)
        self.assertEqual(
            self.client.post(
                f"/evaluation/space/{sid}/rag", json={"cases": [{"question": "x"}]}, headers=h_b
            ).status_code, 404
        )

        self.client.delete(f"/knowledge-spaces/{sid}", headers=h_a)

    # ---- 会话 / 后台任务：领域异常 + 隔离 ----

    def test_conversation_cross_user_404_with_code(self):
        r = self.client.post("/agent", json={"name": f"rt-conv-{self.alice['id']}"}, headers=self.alice["headers"])
        agent_id = r.json()["agent_id"]
        c = self.client.post("/conversation", json={"agent_id": agent_id}, headers=self.alice["headers"])
        self.assertEqual(c.status_code, 200, c.text)
        conv_id = c.json().get("id") or c.json().get("conversation_id")

        got = self.client.get(f"/conversation/{conv_id}", headers=self.bob["headers"])
        self.assertEqual(got.status_code, 404)
        self.assertEqual(got.json().get("code"), "not_found")
        self.assertEqual(self.client.get("/conversation/999999", headers=self.alice["headers"]).status_code, 404)

    def test_background_task_admin_only_endpoint_403(self):
        r = self.client.get("/task/all", headers=self.alice["headers"])
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json().get("code"), "permission_denied")
        self.assertEqual(self.client.get("/task/all", headers=self.admin["headers"]).status_code, 200)

    # ---- Skill 读接口（已全量 async）----

    def test_skill_read_routes_work_and_404(self):
        h = self.alice["headers"]
        self.assertEqual(self.client.get("/skill/", headers=h).status_code, 200)
        self.assertEqual(self.client.get("/skill/public", headers=h).status_code, 200)
        self.assertEqual(self.client.get("/skill/999999", headers=h).status_code, 404)
        self.assertEqual(self.client.get("/skill/999999/validate", headers=h).status_code, 404)

    # ---- 管理员接口隔离 ----

    def test_admin_routes_reject_regular_user(self):
        self.assertEqual(self.client.get("/admin/users", headers=self.alice["headers"]).status_code, 403)
        self.assertEqual(self.client.get("/admin/overview", headers=self.bob["headers"]).status_code, 403)

    def test_admin_routes_allow_admin(self):
        r = self.client.get("/admin/users", headers=self.admin["headers"])
        self.assertEqual(r.status_code, 200, r.text)


if __name__ == "__main__":
    unittest.main()
