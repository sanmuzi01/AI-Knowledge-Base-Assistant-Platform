import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time"
_REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.:-]{8,80}$")


def normalize_request_id(value: str = "") -> str:
    """校验外部传入的请求 ID，不可信或为空时生成新的 ID。"""
    request_id = (value or "").strip()
    if _REQUEST_ID_PATTERN.match(request_id):
        return request_id
    return uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求注入追踪上下文，便于前端报错和后台日志定位同一次请求。"""

    async def dispatch(self, request, call_next):
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id

        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[PROCESS_TIME_HEADER] = f"{elapsed:.4f}"
        return response

