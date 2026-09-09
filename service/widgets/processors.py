"""处理器注册表。

统一接口：process(ctx, raw_data, config) -> processed_data
- 全部是固定命名函数，不做任何 eval / 动态代码执行。
- 新增处理逻辑（llm_summarize / threshold_alert / trend_analysis ...）只需注册新函数，
  runner 不用改。
"""

import json
import os
import re
from typing import Any, Callable, Dict, List

from utils.logger_handler import get_logger
from service.widgets.context import WidgetRunContext
from service.widgets.registry import Registry

logger = get_logger("widget_processors")

# process 接口
Processor = Callable[[WidgetRunContext, Any, Dict[str, Any]], Any]
PROCESSORS: Registry[Processor] = Registry("处理器")


def get_processor(kind: str) -> Processor:
    return PROCESSORS.get(kind)


# ---------------------------------------------------------------------------
# 安全的取值工具：只支持 a.b / a.0 / a[0] / a.*.b 这种点路径，不 eval
# ---------------------------------------------------------------------------

def _split_path(path: str) -> List[str]:
    tokens: List[str] = []
    for part in (path or "").replace("[", ".").replace("]", "").split("."):
        part = part.strip()
        if part:
            tokens.append(part)
    return tokens


def resolve_path(data: Any, path: str) -> Any:
    """按点路径取值；路径不存在返回 None；`*` 表示对列表逐项取后续路径。"""

    tokens = _split_path(path)
    cur: Any = data
    for i, token in enumerate(tokens):
        if token == "*":
            rest = ".".join(tokens[i + 1:])
            if not isinstance(cur, list):
                return None
            return [resolve_path(item, rest) if rest else item for item in cur]
        if isinstance(cur, dict):
            cur = cur.get(token)
        elif isinstance(cur, list):
            try:
                cur = cur[int(token)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if cur is None:
            return None
    return cur


def _as_rows(raw: Any) -> List[Dict[str, Any]]:
    """尽量把各种 raw 结构收敛成 list[dict]。"""

    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        for key in ("rows", "items", "data", "list", "results"):
            value = raw.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _to_number(value: Any):
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 处理器实现
# ---------------------------------------------------------------------------

@PROCESSORS.register("passthrough")
def _passthrough(ctx: WidgetRunContext, raw: Any, config: Dict[str, Any]) -> Any:
    return raw


@PROCESSORS.register("normalize_timeseries")
def _normalize_timeseries(ctx: WidgetRunContext, raw: Any, config: Dict[str, Any]) -> Any:
    """整理成 [{"t": ..., "y": number}]，按 t 升序。x_field/y_field 可配置。"""

    x_field = config.get("x_field") or "date"
    y_field = config.get("y_field") or "value"
    rows = _as_rows(raw)
    points = []
    for row in rows:
        t = row.get(x_field)
        y = _to_number(row.get(y_field))
        if t is None or y is None:
            continue
        points.append({"t": t, "y": y})
    points.sort(key=lambda p: str(p["t"]))
    unit = raw.get("unit") if isinstance(raw, dict) else None
    return {"points": points, "x_field": x_field, "y_field": y_field, "unit": unit}


@PROCESSORS.register("pick_fields")
def _pick_fields(ctx: WidgetRunContext, raw: Any, config: Dict[str, Any]) -> Any:
    fields = config.get("fields") or []
    if not isinstance(fields, list) or not fields:
        return _as_rows(raw)
    rows = _as_rows(raw)
    return [{f: row.get(f) for f in fields} for row in rows]


@PROCESSORS.register("aggregate")
def _aggregate(ctx: WidgetRunContext, raw: Any, config: Dict[str, Any]) -> Any:
    """对某个字段做 sum/avg/min/max/count/last，产出一个数值。"""

    op = (config.get("op") or "last").lower()
    field = config.get("field") or "value"
    rows = _as_rows(raw)
    numbers = [n for n in (_to_number(row.get(field)) for row in rows) if n is not None]
    if op == "count":
        result = len(rows)
    elif not numbers:
        result = None
    elif op == "sum":
        result = round(sum(numbers), 6)
    elif op == "avg":
        result = round(sum(numbers) / len(numbers), 6)
    elif op == "min":
        result = min(numbers)
    elif op == "max":
        result = max(numbers)
    else:  # last
        result = numbers[-1]
    prev = numbers[-2] if len(numbers) >= 2 else None
    delta = round(result - prev, 6) if (isinstance(result, (int, float)) and prev is not None) else None
    unit = raw.get("unit") if isinstance(raw, dict) else None
    return {"op": op, "field": field, "value": result, "delta": delta, "unit": unit}


@PROCESSORS.register("json_extract")
def _json_extract(ctx: WidgetRunContext, raw: Any, config: Dict[str, Any]) -> Any:
    """按安全点路径从结果里取内容。"""

    path = config.get("path") or ""
    extracted = resolve_path(raw, path)
    return {"path": path, "value": extracted}


def _summarize_input_text(raw: Any, limit: int) -> str:
    """把任意 raw 结构压成一段喂给模型的纯文本。"""
    if isinstance(raw, str):
        text = raw
    else:
        try:
            text = json.dumps(raw, ensure_ascii=False, default=str, indent=1)
        except (TypeError, ValueError):
            text = str(raw)
    return text[:limit]


# 面向普通用户的三种摘要风格
_SUMMARY_STYLES = {
    "brief": (
        "输出格式（Markdown，中文）：\n"
        "1. 第一行用一句话给结论，用 **加粗**。\n"
        "2. 空一行，然后 3~6 条 `- ` 要点，每条尽量带上具体数字 / 变化幅度 / 时间。\n"
        "3. 如有异常或需要关注的点，最后加一行 `> 提醒：…`。\n"
        "不要写引言、不要复述原始数据、不要用一级标题。"
    ),
    "report": (
        "输出格式（Markdown，中文）：用 `## 结论` / `## 关键数据` / `## 变化与趋势` / `## 建议` "
        "四个二级小节，每节 1~3 句或几条要点，带具体数字。不写引言。"
    ),
    "one_line": "只输出一句话中文结论，不超过 60 字，不要任何列表或标题。",
}

_PREAMBLE_RE = re.compile(
    r"^\s*(好的[，,]?|以下是|根据(以上|上述)?数据[:：]?|数据(分析|总结)如下[:：]?|"
    r"这是一份?|我来|让我)[^\n]{0,40}[:：]?\s*\n+",
)


@PROCESSORS.register("llm_summarize")
async def _llm_summarize(ctx: WidgetRunContext, raw: Any, config: Dict[str, Any]) -> Any:
    """用用户自己连接的聊天模型，把取到的数据总结成**有条理的一段 Markdown**（配合 markdown 视图）。

    - style: brief（默认，结论+要点）/ report（分小节）/ one_line（一句话）
    - 没有可用模型时不报错：给一段中文说明 + 折叠的原始数据，组件仍能展示。
    - 模型调用失败时抛出，交给 runner 记为失败并进入退避重试。
    """
    instruction = str(config.get("instruction") or "用中文总结下面的数据，突出关键变化和结论。").strip()
    style = str(config.get("style") or "brief").strip().lower()
    fmt = _SUMMARY_STYLES.get(style, _SUMMARY_STYLES["brief"])
    try:
        max_input = int(config.get("max_chars") or os.getenv("WIDGET_SUMMARIZE_MAX_INPUT", "6000"))
    except (TypeError, ValueError):
        max_input = 6000
    source_text = _summarize_input_text(raw, max(500, min(max_input, 20000)))
    generated_at = ctx.now.strftime("%Y-%m-%d %H:%M:%S") if ctx.now else None

    llm_call = config.get("_llm_call")  # 测试可注入
    if llm_call is None:
        from service.widgets.designer import _default_llm_call_factory

        llm_call = await _default_llm_call_factory(ctx.db, ctx.user_id)
    if llm_call is None:
        return {
            "text": "> 未连接 AI 模型，暂时无法自动总结。请在【连接模型】里启用一个聊天模型后再刷新。",
            "summary": None,
            "headline": "未连接 AI 模型",
            "raw_preview": source_text[:1200],
            "generated_at": generated_at,
            "model": None,
            "skipped": True,
        }

    messages = [
        {"role": "system", "content": (
            "你是数据摘要助手。只输出中文 Markdown，不要寒暄，不要复述原始 JSON，不要编造数据里没有的数字。\n"
            + fmt
        )},
        {"role": "user", "content": f"任务：{instruction}\n\n数据（JSON）：\n{source_text}"},
    ]
    answer = (await llm_call(messages) or "").strip()
    answer = _PREAMBLE_RE.sub("", answer).strip()
    if answer.startswith("```"):
        answer = answer.strip("`")
        if answer[:8].lower().startswith(("markdown", "md")):
            answer = answer.split("\n", 1)[-1]
    answer = answer.strip()
    if not answer:
        raise RuntimeError("AI 没有返回摘要内容")

    headline = ""
    for line in answer.splitlines():
        s = line.strip().lstrip("#>-* ").replace("**", "").strip()
        if s:
            headline = s[:80]
            break

    return {
        "text": answer,
        "summary": answer,
        "headline": headline,
        "style": style,
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# threshold_alert：按阈值判定 ok / warn / alert
# ---------------------------------------------------------------------------

_CMP = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}
_CMP_TEXT = {"gt": "高于", "gte": "不低于", "lt": "低于", "lte": "不高于", "eq": "等于", "ne": "不等于"}
_LEVEL_RANK = {"ok": 0, "warn": 1, "alert": 2}


def _extract_metric(raw: Any, field: str) -> Any:
    """从各种结构里取出一个用于比较的数值。"""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, dict):
        if field in raw and _to_number(raw.get(field)) is not None:
            return _to_number(raw[field])
        if _to_number(raw.get("value")) is not None:
            return _to_number(raw["value"])
        pts = raw.get("points")
        if isinstance(pts, list) and pts and isinstance(pts[-1], dict):
            return _to_number(pts[-1].get("y"))
        summary = raw.get("summary")
        if isinstance(summary, dict) and _to_number(summary.get(field)) is not None:
            return _to_number(summary[field])
    rows = _as_rows(raw)
    nums = [n for n in (_to_number(r.get(field)) for r in rows) if n is not None]
    if nums:
        return nums[-1]
    return None


def _norm_rules(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules = config.get("rules")
    out: List[Dict[str, Any]] = []
    if isinstance(rules, list):
        for r in rules:
            if not isinstance(r, dict):
                continue
            op = str(r.get("op") or "gt").lower()
            val = _to_number(r.get("value"))
            if op not in _CMP or val is None:
                continue
            out.append({
                "level": r.get("level") if r.get("level") in _LEVEL_RANK else "alert",
                "op": op, "value": val, "message": str(r.get("message") or "")[:200],
            })
    # 简写：顶层直接给 gt / lt / gte / lte / eq
    for op in _CMP:
        if _to_number(config.get(op)) is not None:
            out.append({"level": "alert", "op": op, "value": _to_number(config[op]), "message": ""})
    return out


@PROCESSORS.register("threshold_alert")
def _threshold_alert(ctx: WidgetRunContext, raw: Any, config: Dict[str, Any]) -> Any:
    """把取到的数值和阈值比一比，产出 level(ok/warn/alert) + 提醒文案。

    配合 metric / markdown 视图。level=alert/warn 时，list 接口会把该组件标成「需关注」。
    """
    field = str(config.get("field") or "value")
    unit = (raw.get("unit") if isinstance(raw, dict) else None) or config.get("unit") or ""
    value = _extract_metric(raw, field)
    rules = _norm_rules(config)

    if value is None:
        return {"level": "ok", "value": None, "field": field, "unit": unit,
                "text": "没取到可比较的数值", "matched": [],
                "checked_at": ctx.now.strftime("%Y-%m-%d %H:%M:%S") if ctx.now else None}

    matched: List[Dict[str, Any]] = []
    level = "ok"
    for r in rules:
        if _CMP[r["op"]](value, r["value"]):
            matched.append(r)
            if _LEVEL_RANK[r["level"]] > _LEVEL_RANK[level]:
                level = r["level"]

    if matched:
        worst = max(matched, key=lambda r: _LEVEL_RANK[r["level"]])
        reason = worst["message"] or f"当前 {value:g}{unit}，{_CMP_TEXT[worst['op']]} {worst['value']:g}{unit}"
        icon = "🔴" if level == "alert" else "🟠"
        text = f"{icon} {reason}"
    else:
        text = f"🟢 正常：当前 {value:g}{unit}"

    return {
        "level": level,
        "value": value,
        "delta": None,
        "field": field,
        "unit": unit,
        "text": text,
        "summary": text,
        "matched": matched,
        "checked_at": ctx.now.strftime("%Y-%m-%d %H:%M:%S") if ctx.now else None,
    }
