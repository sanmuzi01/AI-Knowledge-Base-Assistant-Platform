"""处理器注册表。

统一接口：process(ctx, raw_data, config) -> processed_data
- 全部是固定命名函数，不做任何 eval / 动态代码执行。
- 新增处理逻辑（llm_summarize / threshold_alert / trend_analysis ...）只需注册新函数，
  runner 不用改。
"""

from typing import Any, Callable, Dict, List

from service.widgets.context import WidgetRunContext
from service.widgets.registry import Registry

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
