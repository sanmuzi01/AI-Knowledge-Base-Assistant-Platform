"""
会话系统后端闭环测试
验证流程：
  1. 登录
  2. 创建会话（默认标题"新会话"）
  3. 同步发送第1条消息 → 验证 conversation_id 返回、标题自动生成
  4. 查询会话列表 → 验证新会话出现、标题正确
  5. 查询消息历史 → 验证2条消息（1 user + 1 assistant）
  6. 流式发送第2条消息（复用 conversation_id）→ 验证SSE事件
  7. 再查历史 → 验证4条消息（2轮对话）
  8. 越权测试（不存在的 conversation_id）→ 应返回403/404
  9. 删除会话 → 验证成功
  10. 再查列表 → 会话已消失
"""
import json
import time
import requests

BASE = "http://localhost:8000"
NAME = "sanmuzi"         # ← 改成你的用户名
PASSWORD = "123456"       # ← 改成你的密码
AGENT_ID = 1              # ← 改成你绑了chart_generator的Agent ID

def login():
    resp = requests.post(f"{BASE}/user/login", json={"name": NAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"[FAIL] 登录失败 HTTP {resp.status_code}: {resp.text}")
        return None
    token = resp.json().get("access_token")
    print(f"[OK] 登录成功, token={token[:20]}...")
    return token

def step(title, fn):
    print(f"\n=== {title} ===")
    try:
        result = fn()
        print(f"[OK] {title}")
        return result
    except AssertionError as e:
        print(f"[FAIL] {title}: {e}")
        return None

def main():
    token = login()
    if not token:
        return
    H = {"Authorization": f"Bearer {token}"}

    # --- 1. 创建会话 ---
    def s1():
        resp = requests.post(f"{BASE}/conversation", headers=H, json={"agent_id": AGENT_ID})
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["agent_id"] == AGENT_ID
        assert data["title"] == "新会话"
        print(f"  创建会话: id={data['id']}, title={data['title']}")
        return data["id"]
    conv_id = step("1.创建会话", s1)
    if not conv_id:
        return

    # --- 2. 同步发第1条消息（画图）---
    def s2():
        resp = requests.post(
            f"{BASE}/chat/{AGENT_ID}", headers=H,
            json={"message": "帮我画个柱状图，数据是：语文80，数学90，英语85", "conversation_id": conv_id}
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        # conversation_id 必须返回
        assert "conversation_id" in data, "缺少 conversation_id 字段"
        assert data["conversation_id"] == conv_id, f"conv_id 不匹配: {data.get('conversation_id')}!={conv_id}"
        answer = data.get("answer", "")
        assert len(answer) > 0, "回答为空"
        assert "/static/charts/" in answer, "回答没提到图表URL"
        print(f"  回答长度: {len(answer)}")
        print(f"  回答预览: {answer[:80]}...")
        return True
    if not step("2.同步发第1条消息（画图）", s2):
        return

    # --- 3. 会话标题自动生成 ---
    def s3():
        resp = requests.get(f"{BASE}/conversation/{conv_id}", headers=H)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        # 首条消息后标题不应再是"新会话"
        assert data["title"] != "新会话", f"标题还是默认值: {data['title']}"
        assert len(data["title"]) > 0
        print(f"  自动生成标题: {data['title']}")
        return True
    if not step("3.会话标题自动生成", s3):
        return

    # --- 4. Agent会话列表包含本会话 ---
    def s4():
        resp = requests.get(f"{BASE}/conversation/agent/{AGENT_ID}", headers=H)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        ids = [c["id"] for c in data]
        assert conv_id in ids, f"会话列表里没找到 {conv_id}: {ids}"
        print(f"  会话列表共 {len(data)} 个会话, 本会话在其中")
        return True
    if not step("4.Agent会话列表包含本会话", s4):
        return

    # --- 5. 消息历史：2条（user + assistant）---
    def s5():
        resp = requests.get(f"{BASE}/conversation/{conv_id}/messages", headers=H)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        msgs = resp.json()
        assert len(msgs) == 2, f"消息数应为2，实际: {len(msgs)}"
        assert msgs[0]["role"] == "user", f"第1条应为user: {msgs[0]['role']}"
        assert msgs[1]["role"] == "assistant", f"第2条应为assistant: {msgs[1]['role']}"
        assert len(msgs[1]["content"]) > 50, "assistant回答太短"
        print(f"  消息数: {len(msgs)}")
        print(f"  user: {msgs[0]['content'][:30]}...")
        print(f"  assistant: {msgs[1]['content'][:50]}...")
        return True
    if not step("5.消息历史验证（2条）", s5):
        return

    # --- 6. 流式发第2条消息（复用会话，历史生效）---
    def s6():
        # 故意让它引用上一轮的"语文/数学/英语"上下文，如果LLM知道这些=历史生效
        payload = {
            "message": "再画个折线图，用刚才那三个科目的分数就行",
            "conversation_id": conv_id,
        }
        resp = requests.post(
            f"{BASE}/chat/{AGENT_ID}/stream", headers=H,
            json=payload, stream=True,
        )
        resp.encoding = "utf-8"
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        events = []
        event_type = None
        data_lines = []
        got_answer = False
        got_done = False
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                if event_type and data_lines:
                    data_str = "\n".join(data_lines)
                    try:
                        data_obj = json.loads(data_str.split(":", 1)[1].strip())
                    except Exception:
                        data_obj = {"raw": data_str}
                    events.append((event_type, data_obj))
                    if event_type == "answer":
                        got_answer = True
                        ans = data_obj.get("content", "")
                        assert len(ans) > 30, f"流式回答太短: {ans[:50]}"
                        print(f"  answer预览: {ans[:80]}...")
                    if event_type == "done":
                        got_done = True
                event_type = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line)
        # 关键事件类型检查
        event_types = [e[0] for e in events]
        assert "tool_call" in event_types or "thinking" in event_types, "没看到thinking/tool_call事件"
        assert got_answer, "没收到 answer 事件"
        assert got_done, "没收到 done 事件"
        print(f"  事件总数: {len(events)}")
        print(f"  事件类型: {event_types}")
        return True
    if not step("6.流式发第2条消息（复用会话）", s6):
        return

    # --- 7. 消息历史：4条（2轮对话）---
    def s7():
        resp = requests.get(f"{BASE}/conversation/{conv_id}/messages", headers=H)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        msgs = resp.json()
        assert len(msgs) == 4, f"消息数应为4，实际: {len(msgs)}"
        roles = [m["role"] for m in msgs]
        assert roles == ["user", "assistant", "user", "assistant"], f"角色顺序错: {roles}"
        print(f"  消息数: {len(msgs)}, 角色顺序: {roles}")
        return True
    if not step("7.消息历史验证（4条）", s7):
        return

    # --- 8. 越权测试：用不存在的会话ID ---
    def s8():
        fake_conv = 999999
        # 8a. 查不存在的会话
        resp = requests.get(f"{BASE}/conversation/{fake_conv}", headers=H)
        assert resp.status_code in (403, 404), f"应返回403/404，实际HTTP {resp.status_code}"
        # 8b. 用不存在的会话发消息
        resp = requests.post(
            f"{BASE}/chat/{AGENT_ID}", headers=H,
            json={"message": "测试", "conversation_id": fake_conv},
        )
        assert resp.status_code in (403, 400), f"应返回403/400，实际HTTP {resp.status_code}"
        print("  权限校验正确")
        return True
    if not step("8.越权测试（不存在会话）", s8):
        return

    # --- 9. 删除会话 ---
    def s9():
        resp = requests.delete(f"{BASE}/conversation/{conv_id}", headers=H)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("message") == "删除成功", f"返回内容异常: {data}"
        print(f"  删除会话 {conv_id} 成功")
        return True
    if not step("9.删除会话", s9):
        return

    # --- 10. 再查列表：会话已消失 ---
    def s10():
        resp = requests.get(f"{BASE}/conversation/agent/{AGENT_ID}", headers=H)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        ids = [c["id"] for c in data]
        assert conv_id not in ids, f"已删除的会话 {conv_id} 仍在列表中: {ids}"
        # 同时验证级联删除：查消息历史应返回404
        resp = requests.get(f"{BASE}/conversation/{conv_id}/messages", headers=H)
        assert resp.status_code == 404, f"删除会话后查消息应404，实际HTTP {resp.status_code}"
        print("  会话列表已无该会话，级联删除验证通过")
        return True
    if not step("10.级联删除验证", s10):
        return

    print("\n" + "=" * 60)
    print("🎉 全部10项测试通过！会话系统后端闭环完成 ✅")
    print("=" * 60)

if __name__ == "__main__":
    main()
