"""告警外部推送（service/notification_service.py + widgets/runner.py 的推送触发逻辑）回归测试。"""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from service.exceptions import InvalidInput, NotFound
from tests import _route_client as rc

_AVAILABLE, _WHY = rc.route_tests_available()


def _run(coro):
    return asyncio.run(coro)


@unittest.skipUnless(_AVAILABLE, f"需要本地 MySQL：{_WHY}")
class NotificationChannelCrudTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 出站 URL 会走防 SSRF 校验，校验要解析域名。测试不该依赖真实 DNS / 外网：
        # 断网或 DNS 抖动时这两个用例会莫名失败。这里把 example.com 固定解析成一个公网地址。
        cls._dns = patch("service.web_crawler_service._resolve_host", return_value=["93.184.216.34"])
        cls._dns.start()
        cls.user = rc.create_user("rt-notify-user")

    @classmethod
    def tearDownClass(cls):
        cls._dns.stop()
        from sqlalchemy import text
        from models.init_db import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("DELETE FROM notification_channel WHERE user_id=:u"), {"u": cls.user["id"]})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        rc.cleanup()

    def test_create_list_update_delete(self):
        from models.async_db import AsyncSessionLocal
        from service.notification_service import create_channel, delete_channel, list_channels, update_channel

        async def _create():
            async with AsyncSessionLocal() as db:
                return await create_channel(db, self.user["id"], "我的机器人", "https://example.com/webhook")

        created = _run(_create())
        self.assertEqual(created["name"], "我的机器人")
        self.assertTrue(created["is_enabled"])
        channel_id = created["id"]

        async def _list():
            async with AsyncSessionLocal() as db:
                return await list_channels(db, self.user["id"])

        items = _run(_list())
        self.assertTrue(any(c["id"] == channel_id for c in items))

        async def _update():
            async with AsyncSessionLocal() as db:
                return await update_channel(db, self.user["id"], channel_id, {"is_enabled": False})

        updated = _run(_update())
        self.assertFalse(updated["is_enabled"])

        async def _delete():
            async with AsyncSessionLocal() as db:
                return await delete_channel(db, self.user["id"], channel_id)

        result = _run(_delete())
        self.assertEqual(result["message"], "通道已删除")

    def test_ssrf_blocked_url_rejected(self):
        from models.async_db import AsyncSessionLocal
        from service.notification_service import create_channel

        async def _do():
            async with AsyncSessionLocal() as db:
                return await create_channel(db, self.user["id"], "内网测试", "http://127.0.0.1:8011/webhook")

        with self.assertRaises(InvalidInput):
            _run(_do())

    def test_update_nonexistent_channel_raises_not_found(self):
        from models.async_db import AsyncSessionLocal
        from service.notification_service import update_channel

        async def _do():
            async with AsyncSessionLocal() as db:
                return await update_channel(db, self.user["id"], 999999999, {"is_enabled": True})

        with self.assertRaises(NotFound):
            _run(_do())

    def test_dispatch_skips_disabled_channels_and_calls_enabled_ones(self):
        from models.async_db import AsyncSessionLocal
        from service.notification_service import create_channel, dispatch_alert_async, update_channel

        async def _setup():
            async with AsyncSessionLocal() as db:
                enabled = await create_channel(db, self.user["id"], "启用中", "https://example.com/a")
                disabled = await create_channel(db, self.user["id"], "已停用", "https://example.com/b")
                await update_channel(db, self.user["id"], disabled["id"], {"is_enabled": False})
                return enabled["id"], disabled["id"]

        enabled_id, disabled_id = _run(_setup())

        sent_to = []

        async def _fake_send(channel, title, message):
            sent_to.append(channel.id)
            return None

        async def _dispatch():
            async with AsyncSessionLocal() as db:
                with patch("service.notification_service._send_to_channel", side_effect=_fake_send):
                    await dispatch_alert_async(db, self.user["id"], title="t", message="m")

        _run(_dispatch())
        self.assertIn(enabled_id, sent_to)
        self.assertNotIn(disabled_id, sent_to)


class MaybeDispatchAlertTest(unittest.TestCase):
    """runner._maybe_dispatch_alert 的等级去重逻辑——纯逻辑测试，不需要数据库。"""

    def _widget(self, last_alert_level=None):
        return SimpleNamespace(id=1, name="测试组件", last_alert_level=last_alert_level)

    def test_first_alert_triggers_dispatch(self):
        from service.widgets.runner import _maybe_dispatch_alert

        widget = self._widget(last_alert_level=None)
        payload = {"result": {"level": "alert", "text": "超过阈值"}}
        mock_dispatch = AsyncMock()
        with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
            _run(_maybe_dispatch_alert(None, 1, widget, payload))
        mock_dispatch.assert_awaited_once()
        self.assertEqual(widget.last_alert_level, "alert")

    def test_same_level_does_not_redispatch(self):
        from service.widgets.runner import _maybe_dispatch_alert

        widget = self._widget(last_alert_level="alert")
        payload = {"result": {"level": "alert", "text": "还是超过阈值"}}
        mock_dispatch = AsyncMock()
        with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
            _run(_maybe_dispatch_alert(None, 1, widget, payload))
        mock_dispatch.assert_not_awaited()

    def test_recovery_to_ok_triggers_dispatch(self):
        from service.widgets.runner import _maybe_dispatch_alert

        widget = self._widget(last_alert_level="warn")
        payload = {"result": {"level": "ok", "text": "已恢复"}}
        mock_dispatch = AsyncMock()
        with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
            _run(_maybe_dispatch_alert(None, 1, widget, payload))
        mock_dispatch.assert_awaited_once()
        self.assertEqual(widget.last_alert_level, "ok")

    def test_first_ever_run_ok_does_not_dispatch(self):
        from service.widgets.runner import _maybe_dispatch_alert

        widget = self._widget(last_alert_level=None)
        payload = {"result": {"level": "ok", "text": "一切正常"}}
        mock_dispatch = AsyncMock()
        with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
            _run(_maybe_dispatch_alert(None, 1, widget, payload))
        mock_dispatch.assert_not_awaited()

    def test_non_threshold_payload_is_noop(self):
        from service.widgets.runner import _maybe_dispatch_alert

        widget = self._widget(last_alert_level=None)
        payload = {"result": {"rows": []}}
        mock_dispatch = AsyncMock()
        with patch("service.notification_service.dispatch_alert_async", mock_dispatch):
            _run(_maybe_dispatch_alert(None, 1, widget, payload))
        mock_dispatch.assert_not_awaited()
        self.assertIsNone(widget.last_alert_level)


if __name__ == "__main__":
    unittest.main()
