"""领域异常层次 —— 让「哪一类问题」在日志里一眼可辨，并统一映射成 HTTP 状态码。

用法：
- service 层抛这些异常，不要再散落 `raise ValueError` / `HTTPException` / 裸 `Exception`。
- 路由层不用 try/except：FasdtApi/main.py 注册了统一处理器，按 `http_status` 返回
  `{"detail": <消息>, "code": <code>}`，并按 `code` 记一行 WARNING 日志。

对照：
    InvalidInput      400  入参非法 / 校验不过
    Unauthorized      401  未登录 / token 失效
    PermissionDenied  403  已登录但无权
    NotFound          404  资源不存在或不属于当前用户
    Conflict          409  状态冲突（重复、并发）
    RateLimited       429  触发限流
    QuotaExceeded     429  套餐配额用尽（区别于限流：限流是"太快"，配额是"太多"）
    UpstreamError     502  外部服务 / 模型 / 爬虫失败
    AppError          500  兜底
"""

from typing import Any, Dict, Optional


class AppError(Exception):
    """所有领域异常的基类。"""

    http_status: int = 500
    code: str = "app_error"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        http_status: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.context = context or {}

    def __str__(self) -> str:  # noqa: D401
        return self.message


class InvalidInput(AppError):
    http_status = 400
    code = "invalid_input"


class Unauthorized(AppError):
    http_status = 401
    code = "unauthorized"


class PermissionDenied(AppError):
    http_status = 403
    code = "permission_denied"


class NotFound(AppError):
    http_status = 404
    code = "not_found"


class Conflict(AppError):
    http_status = 409
    code = "conflict"


class RateLimited(AppError):
    http_status = 429
    code = "rate_limited"


class QuotaExceeded(AppError):
    """套餐配额用尽（如本月 Token 用量达到套餐上限）。

    单独成类而不是复用 RateLimited：限流是短期节流，过一会儿重试就好；
    配额是资源用尽，要么等下个周期重置，要么找管理员升级套餐——
    前端需要区分这两种情况给用户不同的提示文案。
    """

    http_status = 429
    code = "quota_exceeded"


class UpstreamError(AppError):
    """调用外部依赖（第三方 API、LLM、向量库、爬虫）失败。"""

    http_status = 502
    code = "upstream_error"
