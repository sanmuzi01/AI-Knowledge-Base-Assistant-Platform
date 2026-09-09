"""自定义工作台组件：编排层（供路由调用）。

路由 -> 本服务 -> user_widget_async_dao / service.widgets.*
对外返回的结构里，面向普通用户的字段放在 friendly，技术配置放在 config（前端默认不展示）。
"""

import json
from typing import Any, Dict, Optional

from service.exceptions import InvalidInput, NotFound

from models import user_widget_async_dao as dao
from utils.timeutil import utcnow
from service.widgets import schema
from service.widgets.designer import design_widget
from service.widgets.runner import compute_next_run_at, run_spec_preview, run_widget, spec_from_widget
from service.widgets.validator import validate_and_normalize


def _spec_to_fields(spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": spec["name"],
        "type": spec["type"],
        "description": spec.get("description") or "",
        "spec_version": spec.get("spec_version", schema.SPEC_VERSION),
        "capabilities_json": json.dumps(spec.get("capabilities", []), ensure_ascii=False),
        "data_source_json": json.dumps(spec.get("data_source", {}), ensure_ascii=False),
        "processor_json": json.dumps(spec.get("processor", {}), ensure_ascii=False),
        "view_json": json.dumps(spec.get("view", {}), ensure_ascii=False),
        "trigger_json": json.dumps(spec.get("trigger", {}), ensure_ascii=False),
        "actions_json": json.dumps(spec.get("actions", list(schema.DEFAULT_ACTIONS)), ensure_ascii=False),
    }


def _point_to_dict(point) -> Optional[Dict[str, Any]]:
    if not point:
        return None
    try:
        payload = json.loads(point.payload_json) if point.payload_json else None
    except (TypeError, ValueError):
        payload = None
    return {
        "ok": bool(point.ok),
        "label": point.label,
        "value": point.value,
        "error": point.error,
        "payload": payload,
        "recorded_at": point.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if point.recorded_at else None,
    }


def _attention_from_point(point) -> Optional[str]:
    """从最近一次运行结果里判断这个组件是否「需要关注」。

    - threshold_alert 处理器给出的 level=alert/warn
    - web_page monitor 模式检测到内容变化 changed=true
    返回 "alert" / "warn" / "changed" / None。
    """
    if not point or not point.payload_json:
        return None
    try:
        payload = json.loads(point.payload_json)
    except (TypeError, ValueError):
        return None
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return None
    level = result.get("level")
    if level in ("alert", "warn"):
        return level
    if result.get("changed") is True:
        return "changed"
    return None


def _widget_to_dict(widget, latest=None) -> Dict[str, Any]:
    spec = spec_from_widget(widget)
    return {
        "attention": _attention_from_point(latest),
        "id": widget.id,
        "name": widget.name,
        "type": widget.type,
        "type_label": schema.TYPE_LABELS.get(widget.type, widget.type),
        "description": widget.description or "",
        "enabled": bool(widget.enabled),
        "sort_order": widget.sort_order,
        "spec_version": widget.spec_version,
        "view_kind": spec["view"].get("kind"),
        "view": spec["view"],
        "actions": spec["actions"],
        "friendly": schema.describe_spec(spec),
        "config": {
            "data_source": spec["data_source"],
            "processor": spec["processor"],
            "view": spec["view"],
            "trigger": spec["trigger"],
        },
        "status": {
            "last_run_at": widget.last_run_at.strftime("%Y-%m-%d %H:%M:%S") if widget.last_run_at else None,
            "last_status": widget.last_status,
            "fail_count": widget.fail_count,
            "next_run_at": widget.next_run_at.strftime("%Y-%m-%d %H:%M:%S") if widget.next_run_at else None,
        },
        "latest": _point_to_dict(latest),
    }


# ---------------------------------------------------------------------------
# 对外方法
# ---------------------------------------------------------------------------

async def design(db, user, prompt: str) -> Dict[str, Any]:
    return await design_widget(db, user.id, prompt)


async def preview_widget(db, user, draft: Dict[str, Any]) -> Dict[str, Any]:
    """按草稿真实跑一次取数/处理流程，但不落库。用于「创建前先看看效果」。"""
    result = validate_and_normalize(draft)
    if result.needs_clarification:
        raise InvalidInput(result.message)
    if not result.ok:
        raise InvalidInput(result.message or "组件配置无效")

    spec = result.spec
    run = await run_spec_preview(db, user.id, spec)
    return {
        "ok": run.ok,
        "message": "预览成功" if run.ok else ("这次没取到数据：" + (run.error or "未知原因")),
        "explain": schema.describe_spec(spec),
        "view": spec["view"],
        "view_kind": spec["view"].get("kind"),
        "data": run.payload,
        "label": run.label,
        "value": run.value,
    }


async def export_widget(db, user, widget_id: int) -> Dict[str, Any]:
    """导出一个组件的配置（可分享 / 再导入）。只含 spec，不含运行状态和用户信息。"""
    widget = await dao.get_owned_widget_async(db, user.id, widget_id)
    if not widget:
        raise NotFound("组件不存在或无权限")
    spec = spec_from_widget(widget)
    return {
        "export_version": 1,
        "kind": "user_widget",
        "name": widget.name,
        "exported_at": utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "spec": spec,
    }


async def import_widget(db, user, payload: Dict[str, Any]) -> Dict[str, Any]:
    """从导出的 JSON 再建一个组件。服务端照常校验，不信任导入内容。"""
    if not isinstance(payload, dict):
        raise InvalidInput("导入内容格式不对")
    spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else payload
    if not isinstance(spec, dict) or not spec.get("type"):
        raise InvalidInput("导入内容里没有可用的组件配置")
    return await create_widget(db, user, spec)


async def list_widgets(db, user_id: int) -> Dict[str, Any]:
    widgets = await dao.list_widgets_by_user_async(db, user_id)
    items = []
    for widget in widgets:
        latest = await dao.latest_data_point_async(db, widget.id)
        items.append(_widget_to_dict(widget, latest))
    return {"items": items, "catalog": schema.public_catalog()}


async def create_widget(db, user, draft: Dict[str, Any]) -> Dict[str, Any]:
    result = validate_and_normalize(draft)
    if result.needs_clarification:
        raise InvalidInput(result.message)
    if not result.ok:
        raise InvalidInput(result.message or "组件配置无效")

    spec = result.spec
    fields = _spec_to_fields(spec)
    fields["sort_order"] = await dao.next_sort_order_async(db, user.id)
    fields["enabled"] = 1
    fields["next_run_at"] = compute_next_run_at(spec["trigger"], utcnow())
    widget = await dao.create_widget_async(db, user.id, fields)
    await db.commit()
    await db.refresh(widget)
    return _widget_to_dict(widget, None)


async def update_widget(db, user, widget_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    widget = await dao.get_owned_widget_async(db, user.id, widget_id)
    if not widget:
        raise NotFound("组件不存在或无权限")

    fields: Dict[str, Any] = {}
    if "name" in patch and patch["name"] is not None:
        name = str(patch["name"]).strip()[:120]
        if not name:
            raise InvalidInput("名称不能为空")
        fields["name"] = name
    if "description" in patch and patch["description"] is not None:
        fields["description"] = str(patch["description"]).strip()[:500]
    if "enabled" in patch and patch["enabled"] is not None:
        fields["enabled"] = 1 if patch["enabled"] else 0
    if "sort_order" in patch and patch["sort_order"] is not None:
        try:
            fields["sort_order"] = int(patch["sort_order"])
        except (TypeError, ValueError):
            raise InvalidInput("排序值必须是数字")

    # 允许整体替换配置（前端"编辑"里重新用自然语言生成后回传 spec）
    if isinstance(patch.get("spec"), dict):
        result = validate_and_normalize(patch["spec"])
        if not result.ok:
            raise InvalidInput(result.message or "组件配置无效")
        fields.update(_spec_to_fields(result.spec))
        fields["next_run_at"] = compute_next_run_at(result.spec["trigger"], utcnow())
        fields["fail_count"] = 0

    if not fields:
        raise InvalidInput("没有需要更新的内容")

    widget = await dao.update_widget_async(db, widget, fields)
    await db.commit()
    await db.refresh(widget)
    latest = await dao.latest_data_point_async(db, widget.id)
    return _widget_to_dict(widget, latest)


async def delete_widget(db, user, widget_id: int) -> Dict[str, Any]:
    widget = await dao.get_owned_widget_async(db, user.id, widget_id)
    if not widget:
        raise NotFound("组件不存在或无权限")
    await dao.delete_widget_async(db, widget)
    await db.commit()
    return {"message": "已删除", "id": widget_id}


async def run_widget_now(db, user, widget_id: int, request_id: str = None) -> Dict[str, Any]:
    widget = await dao.get_owned_widget_async(db, user.id, widget_id)
    if not widget:
        raise NotFound("组件不存在或无权限")
    result = await run_widget(db, user.id, widget_id, request_id=request_id, trigger="manual")
    await db.commit()
    if not result.ok:
        return {"ok": False, "message": "这次没取到数据：" + (result.error or "未知原因"), "data": result.payload}
    return {"ok": True, "message": "已更新", "data": result.payload, "label": result.label, "value": result.value}


async def get_widget_data(db, user, widget_id: int, with_series: bool = False) -> Dict[str, Any]:
    widget = await dao.get_owned_widget_async(db, user.id, widget_id)
    if not widget:
        raise NotFound("组件不存在或无权限")
    latest = await dao.latest_data_point_async(db, widget_id)
    out: Dict[str, Any] = {"widget": _widget_to_dict(widget, latest)}
    if with_series:
        points = await dao.list_data_points_async(db, widget_id, limit=120)
        out["series"] = [
            {
                "recorded_at": p.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if p.recorded_at else None,
                "ok": bool(p.ok),
                "label": p.label,
                "value": p.value,
            }
            for p in reversed(points)
        ]
    return out
