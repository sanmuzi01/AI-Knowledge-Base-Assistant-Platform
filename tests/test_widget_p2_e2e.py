"""P2 全链路集成测试。

用内存 fake 顶替「数据库 + 外部 HTTP + 大模型」，其余全部走真实代码：
designer(注入假模型) -> validator -> _spec_to_fields -> scheduler.run_due_widgets
-> runner.run_widget -> http 连接器(真实 SSRF/大小校验分支) -> llm_summarize 处理器
-> 落数据点 + 保留策略 + 计算下次运行时间；再覆盖失败退避、连续失败暂停、手动恢复。
"""

import json
import os
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from service.widgets import runner, scheduler
from service.widgets.designer import design_widget
from service.widget_async_service import _spec_to_fields


NOW = datetime(2026, 7, 1, 8, 0, 0)


class _FakeDB:
    async def flush(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class _Store:
    """内存版 user_widget_async_dao。"""

    def __init__(self):
        self.widgets = {}
        self.points = []
        self._pid = 0

    # --- widgets ---
    def add_widget(self, fields):
        wid = len(self.widgets) + 1
        base = dict(
            id=wid, user_id=1, enabled=1, sort_order=0,
            last_run_at=None, last_status=None, fail_count=0, next_run_at=None,
        )
        base.update(fields)
        row = SimpleNamespace(**base)
        self.widgets[wid] = row
        return row

    async def get_owned_widget_async(self, db, user_id, widget_id):
        w = self.widgets.get(widget_id)
        return w if w and w.user_id == user_id else None

    async def due_widgets_async(self, db, now, limit=50):
        due = [
            w for w in self.widgets.values()
            if w.enabled == 1 and w.next_run_at is not None and w.next_run_at <= now
        ]
        return sorted(due, key=lambda w: w.next_run_at)[:limit]

    async def claim_widget_async(self, db, widget_id, expected, lease_until):
        w = self.widgets.get(widget_id)
        if not w or w.next_run_at != expected:
            return False
        w.next_run_at = lease_until
        return True

    # --- data points ---
    async def add_data_point_async(self, db, widget_id, **kw):
        self._pid += 1
        self.points.append(SimpleNamespace(id=self._pid, widget_id=widget_id, recorded_at=NOW, **kw))

    async def latest_data_point_async(self, db, widget_id):
        pts = [p for p in self.points if p.widget_id == widget_id]
        return pts[-1] if pts else None

    async def apply_retention_async(self, db, widget_id, **kw):
        return 0

    def install(self, stack):
        import models.user_widget_async_dao as dao
        for name in (
            "get_owned_widget_async", "due_widgets_async", "claim_widget_async",
            "add_data_point_async", "latest_data_point_async", "apply_retention_async",
        ):
            stack.enter_context(patch.object(dao, name, getattr(self, name)))


async def _fake_llm(messages):
    return "外部接口返回 3 条记录，最新值 42，较昨日上升。"


def _http_response(payload: bytes):
    return SimpleNamespace(
        content=payload, status_code=200, encoding="utf-8",
        raise_for_status=lambda: None,
    )


class WidgetP2EndToEndTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import contextlib
        self.stack = contextlib.ExitStack()
        self.store = _Store()
        self.store.install(self.stack)
        self.stack.enter_context(patch("utils.timeutil.utcnow", lambda: NOW))
        self.stack.enter_context(patch("service.widgets.runner.utcnow", lambda: NOW))
        self.stack.enter_context(patch("service.widgets.scheduler.utcnow", lambda: NOW))
        self.stack.enter_context(patch("service.web_crawler_service.validate_crawl_url", lambda u: u))
        self.stack.enter_context(
            patch("service.widgets.designer._default_llm_call_factory",
                  lambda db, uid: _async(_fake_llm))
        )
        self.db = _FakeDB()

    async def asyncTearDown(self):
        self.stack.close()

    async def _make_widget(self):
        async def design_llm(messages):
            return json.dumps({
                "name": "接口数据每小时摘要",
                "type": "markdown",
                "data_source": {"kind": "http", "config": {"url": "https://api.example.com/stats"}},
                "processor": {"kind": "llm_summarize", "config": {"instruction": "总结接口数据"}},
                "view": {"kind": "markdown", "config": {}},
                "trigger": {"kind": "hourly", "config": {"minute": 0}},
            })

        out = await design_widget(db=self.db, user_id=1, prompt="每小时用AI总结我那个接口的数据", llm_call=design_llm)
        self.assertFalse(out["needs_clarification"], out)
        spec = out["draft"]
        self.assertEqual(spec["data_source"]["kind"], "http")
        self.assertEqual(spec["processor"]["kind"], "llm_summarize")

        fields = _spec_to_fields(spec)
        fields["next_run_at"] = runner.compute_next_run_at(spec["trigger"], NOW)
        return self.store.add_widget(fields)

    async def test_full_lifecycle(self):
        widget = await self._make_widget()
        self.assertIsNotNone(widget.next_run_at)
        # 强制到点
        widget.next_run_at = NOW - timedelta(minutes=1)

        ok_payload = json.dumps({"rows": [{"d": "2026-06-30", "v": 41}, {"d": "2026-07-01", "v": 42}]}).encode()

        # --- 1) 调度成功跑一次 ---
        with patch("service.http_resilience.async_request_with_retry",
                   new=lambda **kw: _async_value(_http_response(ok_payload))):
            summary = await scheduler.run_due_widgets(self.db, now=NOW)

        self.assertEqual(summary, {"due": 1, "ran": 1, "skipped": 0, "failed": 0})
        self.assertEqual(widget.last_status, "ok")
        self.assertEqual(widget.fail_count, 0)
        # hourly -> 下次在下一个整点
        self.assertEqual(widget.next_run_at, datetime(2026, 7, 1, 9, 0, 0))
        last = await self.store.latest_data_point_async(self.db, widget.id)
        self.assertEqual(last.ok, 1)
        payload = json.loads(last.payload_json)
        self.assertEqual(payload["view"]["kind"], "markdown")
        self.assertIn("最新值 42", payload["result"]["text"])   # llm_summarize 的产出进了 payload

        # --- 2) 外部接口挂了 -> 记失败 + 指数退避 ---
        widget.next_run_at = NOW - timedelta(minutes=1)

        def boom(**kw):
            raise RuntimeError("上游 502")

        with patch.dict(os.environ, {"WIDGET_RETRY_BACKOFF_BASE_MINUTES": "5", "WIDGET_MAX_CONSECUTIVE_FAILS": "3"}), \
             patch("service.http_resilience.async_request_with_retry", new=boom):
            await scheduler.run_due_widgets(self.db, now=NOW)

        self.assertEqual(widget.last_status, "error")
        self.assertEqual(widget.fail_count, 1)
        self.assertEqual(widget.next_run_at, NOW + timedelta(minutes=5))

        # --- 3) 继续失败到达上限 -> 暂停自动调度 ---
        for _ in range(2):
            widget.next_run_at = NOW - timedelta(minutes=1)
            with patch.dict(os.environ, {"WIDGET_MAX_CONSECUTIVE_FAILS": "3"}), \
                 patch("service.http_resilience.async_request_with_retry", new=boom):
                await scheduler.run_due_widgets(self.db, now=NOW)

        self.assertEqual(widget.fail_count, 3)
        self.assertEqual(widget.last_status, "paused")
        self.assertIsNone(widget.next_run_at)
        # 暂停后不再出现在到点列表里
        self.assertEqual(await self.store.due_widgets_async(self.db, NOW), [])

        # --- 4) 用户手动运行成功 -> 恢复 ---
        with patch("service.http_resilience.async_request_with_retry",
                   new=lambda **kw: _async_value(_http_response(ok_payload))):
            result = await runner.run_widget(self.db, 1, widget.id, trigger="manual")

        self.assertTrue(result.ok)
        self.assertEqual(widget.last_status, "ok")
        self.assertEqual(widget.fail_count, 0)


def _async(fn):
    async def _c(*a, **k):
        return fn
    return _c(*[], **{})


def _async_value(value):
    async def _c(*a, **k):
        return value
    return _c()


if __name__ == "__main__":
    unittest.main()
