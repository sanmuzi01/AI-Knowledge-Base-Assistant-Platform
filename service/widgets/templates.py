"""工作台组件模板：选一个、填几个字段就能建，不走大模型。

每个模板 = 展示信息 + 字段表（前端据此渲染表单）+ `build(params)`（产出 raw spec，
再走 validator）。数据源都用可靠连接器（知识库健康 / 我的用量 / 内部接口 / 网页 /
每日简报）；示例/合成数据源（sample / catalog）不进模板。

自然语言那条路（designer）保留为「高级」入口，不在这里。
"""

from typing import Any, Dict, List

from service.widgets import schema
from service.widgets.validator import validate_and_normalize


class TemplateError(ValueError):
    """字段没填对时抛，路由转 400。"""


# --------------------------------------------------------------------------- 字段辅助

def _field(name: str, label: str, ftype: str, *, required: bool = True,
           placeholder: str = "", help: str = "", default: Any = None,
           options: List[Dict[str, str]] = None, show_if: Dict[str, Any] = None,
           min: Any = None, max: Any = None) -> Dict[str, Any]:
    f: Dict[str, Any] = {"name": name, "label": label, "type": ftype, "required": required}
    if placeholder:
        f["placeholder"] = placeholder
    if help:
        f["help"] = help
    if default is not None:
        f["default"] = default
    if options:
        f["options"] = options
    if show_if:
        f["show_if"] = show_if
    if min is not None:
        f["min"] = min
    if max is not None:
        f["max"] = max
    return f


def _need(params: Dict[str, Any], key: str, label: str) -> Any:
    v = params.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        raise TemplateError(f"请填写「{label}」")
    return v


def _int(params: Dict[str, Any], key: str, label: str, *, default: int = None,
         lo: int = None, hi: int = None) -> int:
    raw = params.get(key)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if default is not None:
            return default
        raise TemplateError(f"请填写「{label}」")
    try:
        n = int(float(raw))
    except (TypeError, ValueError):
        raise TemplateError(f"「{label}」需要是数字")
    if lo is not None and n < lo:
        n = lo
    if hi is not None and n > hi:
        n = hi
    return n


def _url(params: Dict[str, Any], key: str, label: str) -> str:
    u = str(_need(params, key, label)).strip()
    if not u.lower().startswith(("http://", "https://")):
        raise TemplateError(f"「{label}」要以 http:// 或 https:// 开头")
    return u


def _trigger(params: Dict[str, Any], *, default_kind: str = "daily",
             default_run_at: str = "09:00") -> Dict[str, Any]:
    kind = str(params.get("trigger") or default_kind).strip()
    if kind not in schema.TRIGGER_KINDS:
        kind = default_kind
    if kind == "daily":
        run_at = str(params.get("run_at") or default_run_at).strip()
        return {"kind": "daily", "config": {"run_at": run_at, "timezone": "Asia/Shanghai"}}
    return {"kind": kind, "config": {}}


def _actions() -> List[str]:
    return list(schema.DEFAULT_ACTIONS)


# --------------------------------------------------------------------------- 各模板 build

def _b_kb_health(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("name") or "知识库健康看板",
        "type": "table",
        "description": "文档质量 + 检索命中率 + 健康分",
        "data_source": {"kind": "knowledge_space",
                        "config": {"space_id": _int(p, "space_id", "知识库空间")}},
        "processor": {"kind": "passthrough", "config": {}},
        "view": {"kind": "table", "config": {}},
        "trigger": _trigger(p, default_run_at="08:30"),
        "actions": _actions(),
    }


def _b_kb_probe(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("name") or "知识库检索抽查",
        "type": "table",
        "description": "看某个问题在知识库里能检索到哪些片段",
        "data_source": {"kind": "knowledge_base", "config": {
            "agent_id": _int(p, "agent_id", "助手"),
            "query": str(_need(p, "query", "检索问题")).strip(),
            "top_k": _int(p, "top_k", "返回条数", default=5, lo=1, hi=10),
        }},
        "processor": {"kind": "passthrough", "config": {}},
        "view": {"kind": "table", "config": {}},
        "trigger": _trigger(p, default_kind="manual"),
        "actions": _actions(),
    }


def _b_my_usage(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("name") or "我的 AI 运行次数",
        "type": "chart",
        "description": "按天统计我的 Agent 运行次数",
        "data_source": {"kind": "agent_runs",
                        "config": {"days": _int(p, "days", "统计天数", default=14, lo=1, hi=90)}},
        "processor": {"kind": "normalize_timeseries", "config": {"x_field": "date", "y_field": "value"}},
        "view": {"kind": "chart", "config": {"chart_type": "bar"}},
        "trigger": _trigger(p, default_run_at="09:00"),
        "actions": _actions(),
    }


def _b_my_overview(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("name") or "我的使用概览",
        "type": "system_stats",
        "description": "会话 / 知识库 / 组件 / 运行的总体情况",
        "data_source": {"kind": "system_stats", "config": {}},
        "processor": {"kind": "passthrough", "config": {}},
        "view": {"kind": "system_stats", "config": {}},
        "trigger": _trigger(p, default_kind="manual"),
        "actions": _actions(),
    }


def _b_api_table(p: Dict[str, Any]) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "url": _url(p, "url", "接口地址"),
        "method": str(p.get("method") or "GET").strip().upper(),
        "as": "json",
    }
    jp = str(p.get("json_path") or "").strip()
    if jp:
        cfg["json_path"] = jp
    fields = [s.strip() for s in str(p.get("fields") or "").split(",") if s.strip()]
    processor = ({"kind": "pick_fields", "config": {"fields": fields}}
                 if fields else {"kind": "passthrough", "config": {}})
    return {
        "name": p.get("name") or "内部接口数据",
        "type": "table",
        "description": f"拉取 {cfg['url']}",
        "data_source": {"kind": "http", "config": cfg},
        "processor": processor,
        "view": {"kind": "table", "config": {"columns": fields}},
        "trigger": _trigger(p, default_kind="hourly"),
        "actions": _actions(),
    }


def _b_api_metric_alert(p: Dict[str, Any]) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {"url": _url(p, "url", "接口地址"), "method": "GET", "as": "json"}
    jp = str(p.get("json_path") or "").strip()
    if jp:
        cfg["json_path"] = jp
    op = str(p.get("alert_when") or "gt").strip().lower()
    if op not in ("gt", "lt", "gte", "lte"):
        op = "gt"
    rules: List[Dict[str, Any]] = []
    warn_v = p.get("warn_value")
    alert_v = p.get("alert_value")
    field = str(p.get("field") or "value").strip() or "value"
    if warn_v not in (None, ""):
        rules.append({"level": "warn", "op": op, "value": float(warn_v),
                      "message": f"{field} {op} {warn_v}"})
    if alert_v not in (None, ""):
        rules.append({"level": "alert", "op": op, "value": float(alert_v),
                      "message": f"{field} {op} {alert_v}"})
    if not rules:
        raise TemplateError("至少填一个「提醒阈值」或「警报阈值」")
    return {
        "name": p.get("name") or "接口数值监控",
        "type": "metric",
        "description": f"监控 {cfg['url']} 返回的数值",
        "data_source": {"kind": "http", "config": cfg},
        "processor": {"kind": "threshold_alert", "config": {"field": field, "rules": rules}},
        "view": {"kind": "metric", "config": {"unit": str(p.get("unit") or "").strip(),
                                              "label": str(p.get("label") or field).strip()}},
        "trigger": _trigger(p, default_kind="hourly"),
        "actions": _actions(),
    }


def _b_web_monitor(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("name") or "网页更新监控",
        "type": "web_monitor",
        "description": f"盯着 {_url(p, 'url', '网页地址')} 有没有变化",
        "data_source": {"kind": "web_page", "config": {"url": _url(p, "url", "网页地址"), "mode": "monitor"}},
        "processor": {"kind": "passthrough", "config": {}},
        "view": {"kind": "web_monitor", "config": {}},
        "trigger": _trigger(p, default_run_at="09:00"),
        "actions": _actions(),
    }


def _b_web_snapshot(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("name") or "网页正文快照",
        "type": "markdown",
        "description": f"每次运行抓一遍 {_url(p, 'url', '网页地址')} 的正文",
        "data_source": {"kind": "web_page", "config": {
            "url": _url(p, "url", "网页地址"), "mode": "text",
            "max_chars": _int(p, "max_chars", "保留字数", default=4000, lo=200, hi=20000),
        }},
        "processor": {"kind": "passthrough", "config": {}},
        "view": {"kind": "markdown", "config": {}},
        "trigger": _trigger(p, default_kind="daily", default_run_at="08:00"),
        "actions": _actions(),
    }


_BRIEF_SOURCES = {
    "my_usage": lambda p: {"kind": "system_stats", "config": {}},
    "my_runs": lambda p: {"kind": "agent_runs", "config": {"days": 14}},
    "internal_api": lambda p: {"kind": "http", "config": {"url": _url(p, "url", "接口地址"), "method": "GET", "as": "json"}},
    "web_page": lambda p: {"kind": "web_page", "config": {"url": _url(p, "url", "网页地址"), "mode": "text", "max_chars": 6000}},
}


def _b_daily_briefing(p: Dict[str, Any]) -> Dict[str, Any]:
    src_key = str(p.get("source") or "my_usage").strip()
    make_src = _BRIEF_SOURCES.get(src_key)
    if not make_src:
        raise TemplateError("请选择数据来源")
    style = str(p.get("style") or "brief").strip().lower()
    if style not in ("brief", "report", "one_line"):
        style = "brief"
    instruction = str(p.get("instruction") or "").strip() or "用中文总结下面的数据，突出关键变化和结论。"
    return {
        "name": p.get("name") or "每日 AI 简报",
        "type": "markdown",
        "description": "每天定时把数据用 AI 总结成一段话",
        "data_source": make_src(p),
        "processor": {"kind": "llm_summarize", "config": {"instruction": instruction, "style": style}},
        "view": {"kind": "markdown", "config": {}},
        "trigger": _trigger(p, default_kind="daily", default_run_at="08:00"),
        "actions": _actions(),
    }


def _b_web_query_daily(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("name") or "联网查一个指标",
        "type": "markdown",
        "description": "每天用你配置的联网模型查一次（实验性，冷门数据可能查不到）",
        "data_source": {"kind": "web_query", "config": {"query": str(_need(p, "query", "要查什么")).strip()}},
        "processor": {"kind": "passthrough", "config": {}},
        "view": {"kind": "markdown", "config": {}},
        "trigger": _trigger(p, default_kind="daily", default_run_at="09:00"),
        "actions": _actions(),
    }


# --------------------------------------------------------------------------- 注册表

_RUN_AT = _field("run_at", "每天几点跑", "time", required=False, default="09:00",
                 show_if={"field": "trigger", "eq": "daily"})
_TRIGGER = _field("trigger", "更新频率", "select", required=False, default="daily", options=[
    {"value": "daily", "label": "每天"}, {"value": "hourly", "label": "每小时"},
    {"value": "manual", "label": "手动刷新"},
])
_NAME = _field("name", "组件名称", "text", required=False, placeholder="留空自动命名")


TEMPLATES: List[Dict[str, Any]] = [
    {
        "key": "kb_health", "name": "知识库健康看板", "icon": "activity",
        "description": "盯一个知识库空间的文档失败率、检索命中率、健康分。",
        "tags": ["知识库", "质量"], "experimental": False,
        "fields": [_field("space_id", "知识库空间", "space"), _TRIGGER, _RUN_AT, _NAME],
        "build": _b_kb_health,
    },
    {
        "key": "kb_probe", "name": "知识库检索抽查", "icon": "search",
        "description": "输入一个问题，看它在某个助手的知识库里能检索到什么片段。",
        "tags": ["知识库", "调试"], "experimental": False,
        "fields": [
            _field("agent_id", "助手", "agent"),
            _field("query", "检索问题", "text", placeholder="例如：报销上限是多少"),
            _field("top_k", "返回条数", "number", required=False, default=5, min=1, max=10),
            _TRIGGER, _RUN_AT, _NAME,
        ],
        "build": _b_kb_probe,
    },
    {
        "key": "my_usage", "name": "我的 AI 运行次数", "icon": "bar-chart-3",
        "description": "按天统计我的 Agent 运行次数，柱状图。",
        "tags": ["用量"], "experimental": False,
        "fields": [
            _field("days", "统计天数", "number", required=False, default=14, min=1, max=90),
            _TRIGGER, _RUN_AT, _NAME,
        ],
        "build": _b_my_usage,
    },
    {
        "key": "my_overview", "name": "我的使用概览", "icon": "layout-dashboard",
        "description": "会话 / 知识库 / 组件 / 运行的总体情况，一张卡。",
        "tags": ["用量"], "experimental": False,
        "fields": [_TRIGGER, _RUN_AT, _NAME],
        "build": _b_my_overview,
    },
    {
        "key": "api_table", "name": "内部接口数据（表格）", "icon": "table-2",
        "description": "贴一个返回 JSON 的接口地址，平台定时拉取并列成表格。",
        "tags": ["接口"], "experimental": False,
        "fields": [
            _field("url", "接口地址", "url", placeholder="https://内网/api/xxx"),
            _field("method", "请求方式", "select", required=False, default="GET",
                   options=[{"value": "GET", "label": "GET"}, {"value": "POST", "label": "POST"}]),
            _field("json_path", "取值路径", "text", required=False,
                   placeholder="data.list", help="只取响应里的一部分，点号路径；留空取整个响应"),
            _field("fields", "只看这些列", "text", required=False,
                   placeholder="name,count,updated_at", help="逗号分隔；留空显示所有列"),
            _TRIGGER, _RUN_AT, _NAME,
        ],
        "build": _b_api_table,
    },
    {
        "key": "api_metric_alert", "name": "接口数值 + 阈值告警", "icon": "gauge",
        "description": "接口返回的某个数字做成指标卡，超过阈值就标黄/标红。",
        "tags": ["接口", "告警"], "experimental": False,
        "fields": [
            _field("url", "接口地址", "url", placeholder="https://内网/api/metric"),
            _field("json_path", "取值路径", "text", required=False, placeholder="data",
                   help="指向那个数字所在的位置；留空取整个响应"),
            _field("field", "数字字段名", "text", required=False, default="value",
                   help="取值路径指到对象时，用哪个字段比较"),
            _field("alert_when", "什么时候提醒", "select", required=False, default="gt", options=[
                {"value": "gt", "label": "高于阈值"}, {"value": "lt", "label": "低于阈值"},
                {"value": "gte", "label": "达到阈值"}, {"value": "lte", "label": "不超过阈值"},
            ]),
            _field("warn_value", "提醒阈值（黄）", "number", required=False),
            _field("alert_value", "警报阈值（红）", "number", required=False),
            _field("unit", "单位", "text", required=False, placeholder="次 / % / 元"),
            _TRIGGER, _RUN_AT, _NAME,
        ],
        "build": _b_api_metric_alert,
    },
    {
        "key": "web_monitor", "name": "网页更新监控", "icon": "globe",
        "description": "盯着一个网页，正文变了就在工作台标「有更新」。",
        "tags": ["网页", "监控"], "experimental": False,
        "fields": [
            _field("url", "网页地址", "url", placeholder="https://example.com/notice"),
            _TRIGGER, _RUN_AT, _NAME,
        ],
        "build": _b_web_monitor,
    },
    {
        "key": "web_snapshot", "name": "网页正文快照", "icon": "file-text",
        "description": "每次运行抓一遍网页正文，直接看内容。",
        "tags": ["网页"], "experimental": False,
        "fields": [
            _field("url", "网页地址", "url", placeholder="https://example.com/page"),
            _field("max_chars", "保留字数", "number", required=False, default=4000, min=200, max=20000),
            _TRIGGER, _RUN_AT, _NAME,
        ],
        "build": _b_web_snapshot,
    },
    {
        "key": "daily_briefing", "name": "每日 AI 简报", "icon": "newspaper",
        "description": "每天定点把选定的数据用你的模型总结成一段话。",
        "tags": ["AI", "定时"], "experimental": False,
        "fields": [
            _field("source", "数据来源", "select", default="my_usage", options=[
                {"value": "my_usage", "label": "我的使用概览"},
                {"value": "my_runs", "label": "我的运行记录（近 14 天）"},
                {"value": "internal_api", "label": "一个内部接口"},
                {"value": "web_page", "label": "一个网页"},
            ]),
            _field("url", "地址", "url", required=False,
                   show_if={"field": "source", "in": ["internal_api", "web_page"]}),
            _field("instruction", "总结要求", "textarea", required=False,
                   placeholder="用中文总结，突出关键变化和要注意的地方"),
            _field("style", "风格", "select", required=False, default="brief", options=[
                {"value": "brief", "label": "结论 + 要点"},
                {"value": "report", "label": "分小节报告"},
                {"value": "one_line", "label": "一句话"},
            ]),
            _field("run_at", "每天几点跑", "time", required=False, default="08:00"),
            _NAME,
        ],
        "build": _b_daily_briefing,
    },
    {
        "key": "web_query_daily", "name": "联网查一个指标", "icon": "radar",
        "description": "每天用你配置的联网模型查一次某个当前数值。冷门数据可能查不到。",
        "tags": ["联网", "实验性"], "experimental": True,
        "fields": [
            _field("query", "要查什么", "text", placeholder="例如：上证指数 今日收盘"),
            _field("run_at", "每天几点跑", "time", required=False, default="09:00"),
            _NAME,
        ],
        "build": _b_web_query_daily,
    },
]

_BY_KEY: Dict[str, Dict[str, Any]] = {t["key"]: t for t in TEMPLATES}


def list_templates() -> List[Dict[str, Any]]:
    """给前端的模板目录（去掉 build 函数）。"""
    return [{k: v for k, v in t.items() if k != "build"} for t in TEMPLATES]


def build_spec(template_key: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """按模板 + 参数产出**已校验归一**的 spec。字段问题抛 TemplateError。"""
    tpl = _BY_KEY.get(template_key)
    if not tpl:
        raise TemplateError(f"没有这个模板：{template_key}")
    raw = tpl["build"](params or {})
    result = validate_and_normalize(raw)
    if not result.ok:
        # 模板产出的 spec 不该失败——失败说明模板本身或字段校验有 bug
        raise TemplateError(result.message or "模板参数不完整")
    return result.spec
