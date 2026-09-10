"""把原始 JSON（LLM 产出，或前端回传的草稿）校验、归一成白名单内的合法组件配置。

设计原则：
- 只接受 schema.py 列出的枚举；越界一律拒绝或降级，不猜测执行。
- 字段缺失时按组件类型补默认值，让"说得比较简单"的需求也能落地。
- 需求不明确时返回 needs_clarification=True + 中文追问。
- 这一层要能脱离 LLM 单独测。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from service.widgets import schema
from service.widgets.connectors import CONNECTORS

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
_GENERIC_CLARIFY = "没太明白你的需求，能补充一下吗？比如：数据来自哪里、想看成什么样、多久更新一次。"


@dataclass
class ValidationResult:
    ok: bool
    spec: Optional[Dict[str, Any]] = None
    needs_clarification: bool = False
    message: str = ""
    errors: List[str] = field(default_factory=list)

    @classmethod
    def clarify(cls, message: str) -> "ValidationResult":
        return cls(ok=False, needs_clarification=True, message=message or _GENERIC_CLARIFY)

    @classmethod
    def invalid(cls, errors: List[str]) -> "ValidationResult":
        return cls(ok=False, errors=errors, message="；".join(errors))


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_str(value: Any, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, (str, int, float)) else ""


def _norm_trigger(raw: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
    kind = str(raw.get("kind") or "manual").strip()
    if kind not in schema.TRIGGER_KINDS:
        errors.append(f"暂不支持的更新方式：{kind}")
        kind = "manual"
    config = _as_dict(raw.get("config"))
    out: Dict[str, Any] = {"kind": kind, "config": {}}
    if kind == "daily":
        run_at = str(config.get("run_at") or "09:00").strip()
        if not _TIME_RE.match(run_at):
            run_at = "09:00"
        out["config"] = {
            "run_at": run_at,
            "timezone": str(config.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai",
        }
    elif kind == "hourly":
        minute = config.get("minute", 0)
        out["config"] = {"minute": minute if isinstance(minute, int) and 0 <= minute < 60 else 0}
    return out


def _norm_view(raw: Dict[str, Any], widget_type: str, errors: List[str]) -> Dict[str, Any]:
    kind = str(raw.get("kind") or schema.TYPE_DEFAULT_VIEW.get(widget_type, "table")).strip()
    if kind not in schema.VIEW_KINDS:
        errors.append(f"暂不支持的展示方式：{kind}")
        kind = schema.TYPE_DEFAULT_VIEW.get(widget_type, "table")
    config = _as_dict(raw.get("config"))
    out: Dict[str, Any] = {"kind": kind, "config": {}}
    if kind == "chart":
        chart_type = str(config.get("chart_type") or "line").strip()
        if chart_type not in schema.CHART_TYPES:
            chart_type = "line"
        out["config"] = {
            "chart_type": chart_type,
            "x_field": str(config.get("x_field") or "t"),
            "y_field": str(config.get("y_field") or "y"),
            "unit": _clean_str(config.get("unit"), 20),
        }
    elif kind == "metric":
        out["config"] = {
            "unit": _clean_str(config.get("unit"), 20),
            "label": _clean_str(config.get("label"), 40),
        }
    elif kind == "table":
        cols = config.get("columns")
        out["config"] = {"columns": [str(c)[:40] for c in cols][:20] if isinstance(cols, list) else []}
    return out


def _norm_processor(raw: Dict[str, Any], view_kind: str, errors: List[str]) -> Dict[str, Any]:
    provided = raw.get("kind")
    if provided is None:
        kind = {
            "chart": "normalize_timeseries",
            "metric": "aggregate",
        }.get(view_kind, "passthrough")
    else:
        kind = str(provided).strip()
        if kind not in schema.PROCESSOR_KINDS:
            errors.append(f"暂不支持的处理方式：{kind}")
            kind = "passthrough"
    return {"kind": kind, "config": _as_dict(raw.get("config"))}


def _norm_data_source(raw: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
    kind = str(raw.get("kind") or "").strip()
    if not kind:
        return None
    if kind not in schema.CONNECTOR_KINDS or not CONNECTORS.has(kind):
        errors.append(f"暂不支持的数据来源：{kind}")
        return {"kind": kind, "config": {}}
    config = _as_dict(raw.get("config"))
    for msg in CONNECTORS.get(kind).validate_config(config):
        errors.append(msg)
    return {"kind": kind, "config": config}


def _derive_capabilities(widget_type: str, trigger_kind: str, provided: Any) -> List[str]:
    base = list(schema.TYPE_CAPABILITIES.get(widget_type, ["fetch"]))
    if trigger_kind in ("daily", "hourly"):
        base.append("schedule")
    if isinstance(provided, list):
        for cap in provided:
            if cap in schema.CAPABILITIES and cap not in base:
                base.append(cap)
    return list(dict.fromkeys(c for c in base if c in schema.CAPABILITIES))


def validate_and_normalize(data: Any) -> ValidationResult:
    if not isinstance(data, dict):
        return ValidationResult.clarify(_GENERIC_CLARIFY)

    if data.get("needs_clarification"):
        return ValidationResult.clarify(
            _clean_str(data.get("question") or data.get("message"), 300) or _GENERIC_CLARIFY
        )

    widget_type = str(data.get("type") or "").strip()
    if widget_type not in schema.WIDGET_TYPES:
        return ValidationResult.clarify(
            "没太确定你想要哪种小窗口（比如图表、指标卡片、表格、文字摘要、网页监控）。你更想要哪一种？"
        )

    errors: List[str] = []

    data_source = _norm_data_source(_as_dict(data.get("data_source")), errors)
    if data_source is None:
        return ValidationResult.clarify(
            "没识别到数据要从哪里来。可以说：用平台内置的黄金价格 / 汇率 / 天气，或者用我的运行统计。"
        )

    trigger = _norm_trigger(_as_dict(data.get("trigger")), errors)
    view = _norm_view(_as_dict(data.get("view")), widget_type, errors)
    processor = _norm_processor(_as_dict(data.get("processor")), view["kind"], errors)

    # web_query 联网检索：结果是「当前值 + 来源」，固定用 markdown 展示（连接器输出带 summary），
    # 即便 LLM 选了 chart/metric 也纠正——否则没抠出数字时只会显示「还没有数据」。走势靠每天攒。
    if data_source["kind"] == "web_query" and view["kind"] not in ("markdown", "table"):
        widget_type = "markdown"
        view = {"kind": "markdown", "config": {}}
        processor = {"kind": "passthrough", "config": {}}

    actions = [a for a in (data.get("actions") or []) if a in schema.ACTIONS]
    if not actions:
        actions = list(schema.DEFAULT_ACTIONS)
    for required in ("refresh", "delete"):
        if required not in actions:
            actions.append(required)

    spec = {
        "spec_version": schema.SPEC_VERSION,
        "name": _clean_str(data.get("name"), 120) or schema.TYPE_LABELS.get(widget_type, "自定义小窗口"),
        "type": widget_type,
        "description": _clean_str(data.get("description"), 500),
        "capabilities": _derive_capabilities(widget_type, trigger["kind"], data.get("capabilities")),
        "data_source": data_source,
        "processor": processor,
        "view": view,
        "trigger": trigger,
        "actions": actions,
    }

    if errors:
        return ValidationResult.invalid(errors)
    return ValidationResult(ok=True, spec=spec)
