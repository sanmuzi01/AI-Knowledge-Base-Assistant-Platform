"""数据形态识别：判断处理结果是不是「按时间排列的一列数值」。

用途：即使用户建组件时选的是文字摘要 / 表格，只要取到的数据本质上是一条时间序列，
运行引擎就顺手算出一个「更适合的展示方式」（auto_view=折线图）塞进 payload，
前端可以一键切换过去，不用重新建组件。

纯函数，不依赖数据库 / 模型，方便单测。
"""

from typing import Any, Dict, List, Optional

# 认得出的时间字段名（按优先级）
_TIME_KEYS = ("t", "date", "time", "datetime", "timestamp", "ts", "day", "month", "period", "x")
# 认得出的数值字段名（按优先级）
_VALUE_KEYS = ("y", "value", "val", "count", "amount", "num", "total", "price", "score")

MIN_POINTS = 3          # 少于这个点数不值得画图
MAX_POINTS = 500        # 再多就截断，保护前端

# 分类维度字段名
_LABEL_KEYS = ("name", "label", "category", "cat", "key", "type", "status", "group", "bucket")
_CAT_MIN = 2
_CAT_MAX = 12           # 类目太多柱状图也看不清


def _to_number(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rows_from(processed: Any) -> List[Dict[str, Any]]:
    if isinstance(processed, list):
        return [r for r in processed if isinstance(r, dict)]
    if isinstance(processed, dict):
        # normalize_timeseries 的产出：{"points": [{"t","y"}]}
        pts = processed.get("points")
        if isinstance(pts, list) and pts and all(isinstance(p, dict) for p in pts):
            return pts
        for key in ("rows", "items", "data", "list", "results", "series"):
            v = processed.get(key)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
    return []


def _pick_key(sample: Dict[str, Any], candidates) -> Optional[str]:
    for k in candidates:
        if k in sample:
            return k
    return None


def detect_series(processed: Any) -> Optional[Dict[str, Any]]:
    """识别时间序列。返回 None 表示不是；否则返回：

        {
          "points": [{"t": <label>, "y": <float>}, ...],   # 已按 t 升序、去空
          "unit": <str|None>,
          "x_field": <str>, "y_field": <str>,
          "suggested_view": {"kind": "chart", "config": {...}},
        }
    """
    rows = _rows_from(processed)
    if len(rows) < MIN_POINTS:
        return None

    sample = rows[0]
    x_field = _pick_key(sample, _TIME_KEYS)
    y_field = _pick_key(sample, _VALUE_KEYS)
    if not x_field or not y_field:
        # 退一步：只有两个字段且其中一个能转数字，也当序列
        if len(sample) == 2:
            keys = list(sample.keys())
            num_key = next((k for k in keys if _to_number(sample.get(k)) is not None), None)
            if num_key:
                y_field = num_key
                x_field = next(k for k in keys if k != num_key)
    if not x_field or not y_field:
        return None

    points: List[Dict[str, Any]] = []
    for r in rows:
        y = _to_number(r.get(y_field))
        t = r.get(x_field)
        if y is None or t is None:
            continue
        points.append({"t": t, "y": y})
    if len(points) < MIN_POINTS:
        return None

    points.sort(key=lambda p: str(p["t"]))
    points = points[-MAX_POINTS:]

    unit = None
    if isinstance(processed, dict):
        unit = processed.get("unit") or (processed.get("_meta") or {}).get("unit")

    return {
        "points": points,
        "unit": unit,
        "x_field": "t",
        "y_field": "y",
        "suggested_view": {
            "kind": "chart",
            "config": {"chart_type": "line", "x_field": "t", "y_field": "y", "unit": unit or ""},
        },
    }


def detect_categorical(processed: Any) -> Optional[Dict[str, Any]]:
    """识别「若干类目各一个数值」（例如按状态统计的次数），建议柱状图。

    认三种形态：{"counts": {k: n}} / {"by_status": {k: n}} / list[dict{label, value}]。
    """
    mapping: Optional[Dict[str, Any]] = None
    if isinstance(processed, dict):
        for key in ("counts", "by_status", "distribution", "breakdown"):
            v = processed.get(key)
            if isinstance(v, dict) and v:
                mapping = v
                break

    points: List[Dict[str, Any]] = []
    if mapping is not None:
        for k, val in mapping.items():
            y = _to_number(val)
            if y is not None:
                points.append({"t": str(k), "y": y})
    else:
        rows = _rows_from(processed)
        if not rows:
            return None
        sample = rows[0]
        label_key = _pick_key(sample, _LABEL_KEYS)
        value_key = _pick_key(sample, _VALUE_KEYS)
        if not label_key or not value_key:
            return None
        for r in rows:
            y = _to_number(r.get(value_key))
            if y is None:
                continue
            points.append({"t": str(r.get(label_key)), "y": y})

    # 类目数量要合适，且不能是时间序列（避免和 detect_series 抢）
    if not (_CAT_MIN <= len(points) <= _CAT_MAX):
        return None
    labels = [p["t"] for p in points]
    if len(set(labels)) != len(labels):
        return None
    if all(_looks_like_time(x) for x in labels):
        return None

    return {
        "points": points,
        "unit": None,
        "suggested_view": {
            "kind": "chart",
            "config": {"chart_type": "bar", "x_field": "t", "y_field": "y", "unit": ""},
        },
    }


def _looks_like_time(s: str) -> bool:
    s = str(s)
    return bool(s) and any(c in s for c in ("-", "/", ":")) and any(c.isdigit() for c in s)
