import os
import random
import threading
import time
import asyncio
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import httpx
import requests

from utils.logger_handler import get_logger

logger = get_logger("http_resilience")


class CircuitOpenError(Exception):
    """目标服务熔断打开时抛出，避免继续打满外部服务。"""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: float = 0


class CircuitBreaker:
    """简单进程内熔断器。

    生产多实例时，每个 API/Worker 进程各自熔断；如果需要全局熔断，可后续接 Redis。
    """

    def __init__(self):
        self._states: Dict[str, CircuitState] = {}
        self._lock = threading.RLock()

    def before_call(self, name: str) -> None:
        now = time.time()
        with self._lock:
            state = self._states.get(name)
            if state and state.opened_until > now:
                retry_after = int(state.opened_until - now) or 1
                raise CircuitOpenError(f"{name} 暂时不可用，熔断保护中，请 {retry_after} 秒后重试")

    def record_success(self, name: str) -> None:
        with self._lock:
            self._states.pop(name, None)

    def record_failure(self, name: str) -> None:
        threshold = _env_int("HTTP_CIRCUIT_FAILURE_THRESHOLD", 5)
        cooldown = _env_int("HTTP_CIRCUIT_COOLDOWN_SECONDS", 30)
        with self._lock:
            state = self._states.setdefault(name, CircuitState())
            state.failures += 1
            if threshold > 0 and state.failures >= threshold:
                state.opened_until = time.time() + cooldown
                logger.warning(f"外部服务熔断打开: service={name}, failures={state.failures}, cooldown={cooldown}s")

    def stats(self) -> Dict[str, Dict[str, int]]:
        """返回当前熔断状态，用于健康检查和排障。"""

        now = time.time()
        with self._lock:
            return {
                name: {
                    "failures": state.failures,
                    "open": state.opened_until > now,
                    "retry_after": max(0, int(state.opened_until - now)),
                }
                for name, state in self._states.items()
            }


circuit_breaker = CircuitBreaker()


def should_retry_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504}


def request_with_retry(
        service_name: str,
        sender: Callable[[float], requests.Response],
        timeout_env: str,
        default_timeout: float,
        retry_env: str = "HTTP_CLIENT_MAX_RETRIES",
        default_retries: int = 2,
) -> requests.Response:
    """同步 HTTP 请求韧性封装：超时、重试、退避、熔断。"""

    timeout = _env_float(timeout_env, default_timeout)
    retries = max(0, _env_int(retry_env, default_retries))
    base_sleep = _env_float("HTTP_CLIENT_RETRY_BASE_SECONDS", 0.3)
    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        circuit_breaker.before_call(service_name)
        try:
            response = sender(timeout)
            if should_retry_status(response.status_code):
                last_error = requests.HTTPError(f"HTTP {response.status_code}", response=response)
                raise last_error
            circuit_breaker.record_success(service_name)
            return response
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            last_error = exc
            circuit_breaker.record_failure(service_name)
            if attempt >= retries:
                break
            sleep_seconds = base_sleep * (2 ** attempt) + random.uniform(0, base_sleep)
            time.sleep(sleep_seconds)

    if last_error:
        raise last_error
    raise RuntimeError(f"{service_name} 请求失败")


async def async_request_with_retry(
        service_name: str,
        sender: Callable[[httpx.AsyncClient], object],
        timeout_env: str,
        default_timeout: float,
        retry_env: str = "HTTP_CLIENT_MAX_RETRIES",
        default_retries: int = 2,
) -> httpx.Response:
    """异步 HTTP 请求韧性封装。"""

    timeout = _env_float(timeout_env, default_timeout)
    retries = max(0, _env_int(retry_env, default_retries))
    base_sleep = _env_float("HTTP_CLIENT_RETRY_BASE_SECONDS", 0.3)
    last_error: Optional[Exception] = None

    for attempt in range(retries + 1):
        circuit_breaker.before_call(service_name)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await sender(client)
            if should_retry_status(response.status_code):
                last_error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                raise last_error
            circuit_breaker.record_success(service_name)
            return response
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError, httpx.RemoteProtocolError) as exc:
            last_error = exc
            circuit_breaker.record_failure(service_name)
            if attempt >= retries:
                break
            sleep_seconds = base_sleep * (2 ** attempt) + random.uniform(0, base_sleep)
            await asyncio.sleep(sleep_seconds)

    if last_error:
        raise last_error
    raise RuntimeError(f"{service_name} 请求失败")


def stream_request_with_circuit(
        service_name: str,
        sender: Callable[[float], requests.Response],
        timeout_env: str,
        default_timeout: float,
) -> requests.Response:
    """流式请求熔断封装。

    流式响应不做整段重试，避免用户已收到部分内容后重复输出。
    """

    timeout = _env_float(timeout_env, default_timeout)
    circuit_breaker.before_call(service_name)
    try:
        response = sender(timeout)
        response.raise_for_status()
        circuit_breaker.record_success(service_name)
        return response
    except requests.RequestException as exc:
        circuit_breaker.record_failure(service_name)
        raise exc
