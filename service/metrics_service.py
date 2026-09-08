from typing import Dict

from starlette.responses import PlainTextResponse

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
except ImportError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = Gauge = Histogram = None


_HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)

if Counter:
    REQUEST_COUNT = Counter(
        "agent_http_requests_total",
        "HTTP 请求总数",
        ("method", "path", "status"),
    )
    REQUEST_LATENCY = Histogram(
        "agent_http_request_duration_seconds",
        "HTTP 请求耗时",
        ("method", "path"),
        buckets=_HTTP_BUCKETS,
    )
    REQUEST_ERRORS = Counter(
        "agent_http_errors_total",
        "HTTP 异常响应总数",
        ("method", "path", "status"),
    )
    DB_POOL_GAUGE = Gauge(
        "agent_db_pool_connections",
        "数据库连接池状态",
        ("state",),
    )
    CACHE_BACKEND_GAUGE = Gauge(
        "agent_cache_backend",
        "缓存后端状态，1 表示当前命名空间使用该后端",
        ("namespace", "backend"),
    )
else:
    REQUEST_COUNT = REQUEST_LATENCY = REQUEST_ERRORS = DB_POOL_GAUGE = CACHE_BACKEND_GAUGE = None


def normalize_metric_path(path: str) -> str:
    """降低指标标签基数，避免用户 ID、任务 ID 等动态路径撑爆 Prometheus。"""

    parts = []
    for part in (path or "/").split("/"):
        if part.isdigit():
            parts.append("{id}")
        elif len(part) > 32 and any(ch.isdigit() for ch in part):
            parts.append("{token}")
        else:
            parts.append(part)
    normalized = "/".join(parts) or "/"
    return normalized[:200]


def observe_http_request(method: str, path: str, status_code: int, elapsed_seconds: float) -> None:
    """记录一次 HTTP 请求指标。Prometheus 未安装时静默跳过。"""

    if not REQUEST_COUNT:
        return
    normalized_path = normalize_metric_path(path)
    status = str(status_code or 0)
    REQUEST_COUNT.labels(method=method, path=normalized_path, status=status).inc()
    REQUEST_LATENCY.labels(method=method, path=normalized_path).observe(max(0, elapsed_seconds))
    if status_code >= 500:
        REQUEST_ERRORS.labels(method=method, path=normalized_path, status=status).inc()


def update_runtime_metrics(pool_stats: Dict[str, int], cache_stats: Dict[str, Dict]) -> None:
    """刷新连接池和缓存状态指标。"""

    if not DB_POOL_GAUGE:
        return
    for state, value in (pool_stats or {}).items():
        if isinstance(value, (int, float)):
            DB_POOL_GAUGE.labels(state=state).set(value)

    for namespace, stats in (cache_stats or {}).items():
        backend = stats.get("backend") or "unknown"
        for candidate in ("redis", "memory", "unknown"):
            CACHE_BACKEND_GAUGE.labels(namespace=namespace, backend=candidate).set(1 if backend == candidate else 0)


def metrics_response() -> PlainTextResponse:
    """返回 Prometheus 文本格式指标。"""

    if not generate_latest:
        return PlainTextResponse(
            "# prometheus-client is not installed\n",
            media_type=CONTENT_TYPE_LATEST,
            status_code=503,
        )
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)



