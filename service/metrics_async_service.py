"""Prometheus 指标异步服务。"""

from starlette.concurrency import run_in_threadpool

from service.metrics_service import metrics_response


async def async_metrics_response():
    return await run_in_threadpool(metrics_response)
