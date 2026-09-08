"""组件运行引擎 —— 唯一运行入口。

手动运行、未来 Worker 定时运行、事件触发，都调 run_widget(...)。
流程固定：取连接器 -> fetch -> 取处理器 -> process -> 存数据点 -> 更新调度状态。
runner 只认注册表，不认识任何具体数据源 / 处理器 / 视图。
"""

import inspect
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from utils.logger_handler import get_logger
from utils.timeutil import utcnow
from service.widgets import schema
from service.widgets.connectors import CONNECTORS
from service.widgets.context import WidgetRunContext
from service.widgets.processors import PROCESSORS

logger = get_logger("widget_runner")

DEFAULT_KEEP_POINTS = 200


@dataclass
class WidgetRunResult:
    ok: bool
    widget_id: int
    payload: Dict[str, Any]
    label: Optional[str] = None
    value: Optional[float] = None
    error: Optional[str] = None
    duration_ms: int = 0


def _loads(raw: Optional[str], fallback):
    try:
        value = json.loads(raw) if raw else None
        return value if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def spec_from_widget(widget) -> Dict[str, Any]:
    """把 UserWidget 行还原成一份完整 spec dict。"""
    return {
        "spec_version": getattr(widget, "spec_version", schema.SPEC_VERSION),
        "name": widget.name,
        "type": widget.type,
        "description": widget.description or "",
        "capabilities": _loads(widget.capabilities_json, []),
        "data_source": _loads(widget.data_source_json, {"kind": "sample", "config": {}}),
        "processor": _loads(widget.processor_json, {"kind": "passthrough", "config": {}}),
        "view": _loads(widget.view_json, {"kind": schema.TYPE_DEFAULT_VIEW.get(widget.type, "table"), "config": {}}),
        "trigger": _loads(widget.trigger_json, {"kind": "manual", "config": {}}),
        "actions": _loads(widget.actions_json, list(schema.DEFAULT_ACTIONS)),
    }


def compute_next_run_at(trigger: Dict[str, Any], now: datetime) -> Optional[datetime]:
    """按触发规则算下一次运行时间（naive UTC，与库中 DateTime 列一致）。manual -> None。"""
    kind = (trigger or {}).get("kind", "manual")
    config = (trigger or {}).get("config") or {}
    if kind == "hourly":
        minute = config.get("minute", 0)
        nxt = now.replace(minute=minute if isinstance(minute, int) and 0 <= minute < 60 else 0,
                          second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(hours=1)
        return nxt
    if kind == "daily":
        run_at = str(config.get("run_at") or "09:00")
        try:
            hh, mm = (int(x) for x in run_at.split(":", 1))
        except (ValueError, TypeError):
            hh, mm = 9, 0
        # 触发规则里的时间是用户本地时区（默认东八区），这里换算回 UTC。
        tz_offset_hours = 8 if str(config.get("timezone") or "Asia/Shanghai") == "Asia/Shanghai" else 0
        nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0) - timedelta(hours=tz_offset_hours)
        if nxt <= now:
            nxt += timedelta(days=1)
        return nxt
    return None


def _summarize(view_kind: str, processed: Any):
    """从处理结果里提炼通用快速字段 (label, value)。"""
    label: Optional[str] = None
    value: Optional[float] = None
    try:
        if isinstance(processed, dict):
            if "value" in processed and isinstance(processed["value"], (int, float)):
                value = float(processed["value"])
                unit = processed.get("unit") or ""
                label = f"{value:g} {unit}".strip()
            elif isinstance(processed.get("points"), list) and processed["points"]:
                last = processed["points"][-1]
                if isinstance(last.get("y"), (int, float)):
                    value = float(last["y"])
                    unit = processed.get("unit") or ""
                    label = f"{value:g} {unit}".strip()
            elif isinstance(processed.get("summary"), dict):
                summary = processed["summary"]
                if isinstance(summary.get("runs"), (int, float)):
                    value = float(summary["runs"])
                    label = f"运行 {summary['runs']} 次"
            elif isinstance(processed.get("counts"), dict):
                total = sum(v for v in processed["counts"].values() if isinstance(v, (int, float)))
                value = float(total)
                label = f"合计 {total:g}"
        elif isinstance(processed, list):
            label = f"{len(processed)} 条"
            value = float(len(processed))
    except Exception:  # noqa: BLE001 - 概要字段是尽力而为，不能影响主流程
        pass
    return label, value


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def run_widget(db, user_id: int, widget_id: int, *, request_id: str = None,
                     trigger: str = "manual") -> WidgetRunResult:
    """运行一个组件并落库一条数据点。db 为 AsyncSession；调用方负责 commit。"""
    from models import user_widget_async_dao as dao

    widget = await dao.get_owned_widget_async(db, user_id, widget_id)
    if not widget:
        raise LookupError("组件不存在或无权限")

    spec = spec_from_widget(widget)
    ctx = WidgetRunContext(
        user_id=user_id,
        now=utcnow(),
        widget_id=widget_id,
        widget_type=widget.type,
        db=db,
        request_id=request_id,
        trigger=trigger,
    )

    started = time.time()
    try:
        source = spec.get("data_source") or {}
        connector = CONNECTORS.get(source.get("kind"))
        raw = await connector.fetch(ctx, source.get("config") or {})

        proc = spec.get("processor") or {}
        processor = PROCESSORS.get(proc.get("kind", "passthrough"))
        processed = await _maybe_await(processor(ctx, raw, proc.get("config") or {}))

        view = spec.get("view") or {}
        duration_ms = int((time.time() - started) * 1000)
        label, value = _summarize(view.get("kind", "table"), processed)
        payload = {
            "ok": True,
            "view": view,
            "result": processed,
            "generated_at": ctx.now.strftime("%Y-%m-%d %H:%M:%S"),
            "source": {"kind": source.get("kind"), "provider": (source.get("config") or {}).get("provider")},
        }

        await dao.add_data_point_async(
            db, widget_id, ok=1, label=label, value=value,
            payload_json=json.dumps(payload, ensure_ascii=False), duration_ms=duration_ms,
        )
        await dao.prune_data_points_async(db, widget_id, DEFAULT_KEEP_POINTS)

        widget.last_run_at = ctx.now
        widget.last_status = "ok"
        widget.fail_count = 0
        widget.next_run_at = compute_next_run_at(spec.get("trigger") or {}, ctx.now)
        await db.flush()
        return WidgetRunResult(True, widget_id, payload, label, value, None, duration_ms)
    except Exception as exc:  # noqa: BLE001 - 运行失败要落库成失败数据点，并把错误交给上层
        duration_ms = int((time.time() - started) * 1000)
        message = str(exc)[:500]
        logger.warning(f"组件运行失败: widget_id={widget_id}, user_id={user_id}, error={message}")
        payload = {"ok": False, "view": spec.get("view") or {}, "error": message,
                   "generated_at": ctx.now.strftime("%Y-%m-%d %H:%M:%S")}
        await dao.add_data_point_async(
            db, widget_id, ok=0, label=None, value=None,
            payload_json=json.dumps(payload, ensure_ascii=False), error=message, duration_ms=duration_ms,
        )
        widget.last_run_at = ctx.now
        widget.last_status = "error"
        widget.fail_count = int(widget.fail_count or 0) + 1
        widget.next_run_at = compute_next_run_at(spec.get("trigger") or {}, ctx.now)
        await db.flush()
        return WidgetRunResult(False, widget_id, payload, None, None, message, duration_ms)
