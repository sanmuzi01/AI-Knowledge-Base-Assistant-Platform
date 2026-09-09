"""组件配置的白名单与结构定义 —— 单一事实来源。

后端路由 / 服务 / 校验器，以及前端枚举语义，都以这里为准；LLM 也只能产出这里
列出的 type / capability / connector / processor / view / trigger / action。
新增能力时改这一处 + 注册对应实现即可。
"""

from typing import Any, Dict, List

# 组件协议版本。以后配置结构升级时 +1，配合 UserWidget.spec_version 做兼容。
SPEC_VERSION = 1

# ---------------------------------------------------------------------------
# 白名单枚举
# ---------------------------------------------------------------------------

WIDGET_TYPES: List[str] = [
    "web_monitor",     # 网页监控
    "api_data",        # API 数据窗口
    "chart",           # 图表窗口
    "metric",          # 指标卡片
    "markdown",        # 文本摘要
    "table",           # 表格窗口
    "task_list",       # 任务/提醒窗口
    "system_stats",    # 系统或 Agent 运行统计窗口
]

CAPABILITIES: List[str] = [
    "fetch",       # 会去取数据
    "schedule",    # 会定时运行
    "chart", "metric", "table", "text", "monitor", "list", "stats",
]

CONNECTOR_KINDS: List[str] = [
    "sample",         # 内置示例数据，保证演示永远能跑
    "catalog",        # 服务端内置数据源目录（gold_price / usd_cny / weather ...）
    "system_stats",   # 当前用户的系统 / 运行概览
    "agent_runs",     # 当前用户的 Agent 运行记录统计
    # --- P2：外部数据源，统一走出站安全校验（SSRF 防护）+ 超时/重试/熔断 ---
    "http",           # 用户自定义接口 URL（JSON / 文本）
    "web_page",       # 抓取一个网页正文，可做「有没有更新」的监控
    "knowledge_base", # 从「我的知识库」按问题检索
]

# 以后再加 trend_analysis / classification / ranking
PROCESSOR_KINDS: List[str] = [
    "passthrough",
    "normalize_timeseries",
    "pick_fields",
    "aggregate",
    "json_extract",
    "llm_summarize",    # 用用户自己的模型把取到的数据总结成一段话
    "threshold_alert",  # 按阈值判定 ok / warn / alert，给出提醒文案
]

# P2 再加 calendar / kanban / map / timeline / alert / progress / image / file_preview
VIEW_KINDS: List[str] = [
    "chart",
    "metric",
    "markdown",
    "table",
    "web_monitor",
    "task_list",
    "system_stats",
]

# P1 支持保存 manual / hourly / daily；P2 再加 event / webhook / cron
TRIGGER_KINDS: List[str] = ["manual", "hourly", "daily"]

ACTIONS: List[str] = ["refresh", "edit", "hide", "delete"]
DEFAULT_ACTIONS: List[str] = ["refresh", "edit", "hide", "delete"]

CHART_TYPES: List[str] = ["line", "bar", "pie"]

# ---------------------------------------------------------------------------
# 面向普通用户的中文文案（前端只展示这些，不展示 data_source/processor 等技术字段）
# ---------------------------------------------------------------------------

TYPE_LABELS: Dict[str, str] = {
    "web_monitor": "网页监控",
    "api_data": "数据窗口",
    "chart": "图表",
    "metric": "指标卡片",
    "markdown": "文字摘要",
    "table": "表格",
    "task_list": "待办提醒",
    "system_stats": "运行统计",
}

CONNECTOR_LABELS: Dict[str, str] = {
    "sample": "内置示例数据",
    "catalog": "平台数据服务",
    "system_stats": "我的使用与运行概览",
    "agent_runs": "我的 AI 运行记录",
    "http": "外部接口地址",
    "web_page": "网页内容",
    "knowledge_base": "我的知识库",
}

CATALOG_PROVIDER_LABELS: Dict[str, str] = {
    "gold_price": "黄金价格",
    "usd_cny": "美元兑人民币汇率",
    "weather": "天气",
}

VIEW_LABELS: Dict[str, str] = {
    "chart": "图表",
    "metric": "指标卡片",
    "markdown": "文字摘要",
    "table": "表格",
    "web_monitor": "网页监控",
    "task_list": "待办提醒",
    "system_stats": "运行统计",
}

TRIGGER_LABELS: Dict[str, str] = {
    "manual": "手动刷新",
    "hourly": "每小时自动更新",
    "daily": "每天自动更新",
}

ACTION_LABELS: Dict[str, str] = {
    "refresh": "刷新",
    "edit": "编辑",
    "hide": "隐藏",
    "delete": "删除",
}

# 每种组件类型默认的 view / capability，校验器在字段缺失时据此补齐
TYPE_DEFAULT_VIEW: Dict[str, str] = {
    "web_monitor": "web_monitor",
    "api_data": "table",
    "chart": "chart",
    "metric": "metric",
    "markdown": "markdown",
    "table": "table",
    "task_list": "task_list",
    "system_stats": "system_stats",
}

TYPE_CAPABILITIES: Dict[str, List[str]] = {
    "web_monitor": ["fetch", "monitor"],
    "api_data": ["fetch"],
    "chart": ["fetch", "chart"],
    "metric": ["fetch", "metric"],
    "markdown": ["fetch", "text"],
    "table": ["fetch", "table"],
    "task_list": ["fetch", "list"],
    "system_stats": ["fetch", "stats"],
}


def describe_spec(spec: Dict[str, Any]) -> Dict[str, str]:
    """把配置翻译成普通用户看得懂的四句话：数据从哪来 / 系统会做什么 / 怎么展示 / 多久更新。"""

    source = spec.get("data_source") or {}
    source_kind = source.get("kind")
    source_config = source.get("config") or {}
    if source_kind == "catalog":
        provider = source_config.get("provider")
        data_from = CATALOG_PROVIDER_LABELS.get(provider, "平台数据服务")
    elif source_kind == "sample":
        data_from = "内置示例数据（用于演示）"
    elif source_kind in ("http", "web_page"):
        url = str(source_config.get("url") or "").strip()
        host = url.split("//", 1)[-1].split("/", 1)[0] if url else ""
        data_from = f"{CONNECTOR_LABELS[source_kind]}（{host}）" if host else CONNECTOR_LABELS[source_kind]
    else:
        data_from = CONNECTOR_LABELS.get(source_kind, "数据服务")

    processor_kind = (spec.get("processor") or {}).get("kind", "passthrough")
    system_does = {
        "passthrough": "原样整理数据",
        "normalize_timeseries": "整理成按时间排列的走势数据",
        "pick_fields": "只保留需要的字段",
        "aggregate": "汇总计算出一个数值",
        "json_extract": "从结果里取出指定内容",
        "llm_summarize": "用 AI 总结成一段话",
        "threshold_alert": "按阈值判断要不要提醒",
    }.get(processor_kind, "整理数据")

    view = spec.get("view") or {}
    view_kind = view.get("kind", "table")
    chart_type = (view.get("config") or {}).get("chart_type")
    if view_kind == "chart" and chart_type:
        show_as = {"line": "折线图", "bar": "柱状图", "pie": "饼图"}.get(chart_type, "图表")
    else:
        show_as = VIEW_LABELS.get(view_kind, "表格")

    trigger = spec.get("trigger") or {}
    trigger_kind = trigger.get("kind", "manual")
    if trigger_kind == "daily":
        run_at = (trigger.get("config") or {}).get("run_at", "09:00")
        update_every = f"每天 {run_at} 自动更新"
    elif trigger_kind == "hourly":
        update_every = "每小时自动更新"
    else:
        update_every = "手动点击刷新时更新"

    return {
        "data_from": data_from,
        "system_does": system_does,
        "show_as": show_as,
        "update_every": update_every,
    }


def public_catalog() -> Dict[str, Any]:
    """给前端「AI 创建组件」页面用的、纯展示用的能力目录（不含任何技术实现细节）。"""

    return {
        "spec_version": SPEC_VERSION,
        "widget_types": [{"key": k, "label": TYPE_LABELS.get(k, k)} for k in WIDGET_TYPES],
        "views": [{"key": k, "label": VIEW_LABELS.get(k, k)} for k in VIEW_KINDS],
        "triggers": [{"key": k, "label": TRIGGER_LABELS[k]} for k in TRIGGER_KINDS],
        "actions": [{"key": k, "label": ACTION_LABELS[k]} for k in ACTIONS],
        "data_sources": [
            {"key": k, "label": CONNECTOR_LABELS.get(k, k)} for k in CONNECTOR_KINDS
        ],
        "catalog_providers": [
            {"key": k, "label": v} for k, v in CATALOG_PROVIDER_LABELS.items()
        ],
    }
