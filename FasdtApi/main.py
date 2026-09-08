import os
from pathlib import Path

from service.config_validation import assert_runtime_config, validate_runtime_config

# 生产配置必须在导入路由和数据库模型前完成校验。
# 这样缺少 Redis、使用占位密钥、CORS/Host 未收紧等问题会在启动早期失败，
# 避免应用已经连接数据库或初始化业务模块后才暴露配置错误。
assert_runtime_config()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from sqlalchemy import text
from FasdtApi.login import router as login_router
from FasdtApi.agent import router as agent_router
from FasdtApi.llm_config import router as llm_config_router
from FasdtApi.chat import router as chat_router
from FasdtApi.knowledge import router as knowledge_router
from FasdtApi.agent_run import router as agent_run_router
from FasdtApi.skill_route import router as skill_router
from FasdtApi.conversation_route import router as conversation_router
from FasdtApi.memory import router as memory_router
from FasdtApi.background_task import router as background_task_router
from FasdtApi.admin import router as admin_router
from FasdtApi.evaluation import router as evaluation_router
from FasdtApi.web_monitor import router as web_monitor_router
from models.init_db import SessionLocal, engine
from service.operation_log_middleware import OperationLogMiddleware
from service.background_task_service import task_execution_mode
from service.http_resilience import circuit_breaker
from service.metrics_async_service import async_metrics_response
from service.metrics_service import update_runtime_metrics
from service.request_context_middleware import RequestContextMiddleware
from service.security_middleware import SecurityHeadersMiddleware
from utils.cache import config_cache, skill_cache, verification_cache
from utils.rate_limit import concurrency_limiter, rate_limiter

def _env_list(name: str, default: str) -> list[str]:
    """读取逗号分隔的环境变量列表。"""

    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_int(name: str, default: int) -> int:
    """读取整数环境变量，配置错误时回退默认值。"""

    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default

app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_env_list("TRUSTED_HOSTS", "127.0.0.1,localhost,api"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_env_list("CORS_ALLOW_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)
app.add_middleware(OperationLogMiddleware)
app.add_middleware(RequestContextMiddleware)

# 用绝对路径挂载 static 目录，避免依赖启动时的工作目录
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='my_static')
app.include_router(login_router)
app.include_router(agent_router)
app.include_router(llm_config_router)
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(agent_run_router)
app.include_router(skill_router)
app.include_router(conversation_router)  # 注册会话路由
app.include_router(memory_router)
app.include_router(background_task_router)
app.include_router(admin_router)
app.include_router(evaluation_router)
app.include_router(web_monitor_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health", summary="服务健康检查")
async def health_check():
    checks = []
    config_status = validate_runtime_config()

    def add_check(name: str, ok: bool, message: str = ""):
        checks.append({"name": name, "ok": ok, "message": message})

    for item in config_status["checks"]:
        add_check(item["name"], item["ok"], item["message"])

    redis_url = os.getenv("REDIS_URL")
    redis_enabled = bool(redis_url)
    config_cache_stats = config_cache.stats()
    skill_cache_stats = skill_cache.stats()
    verification_cache_stats = verification_cache.stats()
    add_check(
        "redis",
        (not redis_enabled)
        or config_cache_stats.get("redis_ok", False)
        or skill_cache_stats.get("redis_ok", False)
        or verification_cache_stats.get("redis_ok", False),
        "未配置 REDIS_URL，当前使用内存缓存"
        if not redis_enabled
        else ("连接正常" if config_cache_stats.get("redis_ok") or skill_cache_stats.get("redis_ok") or verification_cache_stats.get("redis_ok") else "Redis 不可用，已回退内存缓存"),
    )
    sms_provider = os.getenv("SMS_PROVIDER", "console").strip().lower()
    add_check(
        "sms",
        sms_provider != "webhook" or bool(os.getenv("SMS_WEBHOOK_URL")),
        "生产短信 Webhook 已配置" if sms_provider == "webhook" and os.getenv("SMS_WEBHOOK_URL")
        else ("本地日志验证码模式" if sms_provider == "console" else "缺少 SMS_WEBHOOK_URL"),
    )

    def check_database():
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True, "连接正常"
        except Exception as e:
            return False, str(e)
        finally:
            try:
                db.close()
            except Exception:
                pass

    db_ok, db_message = await run_in_threadpool(check_database)
    add_check("database", db_ok, db_message)

    pool_stats = {}
    pool = getattr(engine, "pool", None)
    if pool:
        for field, reader in {
            "size": getattr(pool, "size", None),
            "checked_in": getattr(pool, "checkedin", None),
            "checked_out": getattr(pool, "checkedout", None),
            "overflow": getattr(pool, "overflow", None),
        }.items():
            if callable(reader):
                try:
                    pool_stats[field] = reader()
                except Exception:
                    pool_stats[field] = None

    for name, path in {
        "static": BASE_DIR / "static",
        "knowledge_files": BASE_DIR / "knowledge_files",
        "vector_db": BASE_DIR / "vector_db",
        "skills": BASE_DIR / "skills",
    }.items():
        add_check(name, path.exists(), str(path))

    cache_payload = {
        "config": config_cache_stats,
        "skill": skill_cache_stats,
        "verification": verification_cache_stats,
    }
    update_runtime_metrics(pool_stats, cache_payload)

    ok = all(item["ok"] for item in checks)
    return {
        "ok": ok,
        "checks": checks,
        "config": config_status,
        "cache": cache_payload,
        "limits": {
            "rate": rate_limiter.stats(),
            "concurrency": concurrency_limiter.stats(),
        },
        "database": {
            "pool": pool_stats,
        },
        "tasks": {
            "execution_mode": task_execution_mode(),
            "worker_required": task_execution_mode() == "worker",
            "running_timeout_seconds": _env_int("TASK_RUNNING_TIMEOUT_SECONDS", 1800),
            "max_auto_retries": _env_int("TASK_MAX_AUTO_RETRIES", 2),
            "retry_base_seconds": _env_int("TASK_RETRY_BASE_SECONDS", 30),
            "retry_max_seconds": _env_int("TASK_RETRY_MAX_SECONDS", 300),
        },
        "resilience": {
            "circuits": circuit_breaker.stats(),
        },
    }


@app.get("/metrics", summary="Prometheus 指标")
async def prometheus_metrics():
    return await async_metrics_response()


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
