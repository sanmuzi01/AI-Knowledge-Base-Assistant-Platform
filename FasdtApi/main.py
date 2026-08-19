import os
from pathlib import Path
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
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
from models.init_db import SessionLocal
from service.operation_log_middleware import OperationLogMiddleware
from utils.cache import config_cache, skill_cache

app = FastAPI()
app.add_middleware(OperationLogMiddleware)

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


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health", summary="服务健康检查")
def health_check():
    checks = []

    def add_check(name: str, ok: bool, message: str = ""):
        checks.append({"name": name, "ok": ok, "message": message})

    for key in ("JWT_SECRET_KEY", "LLM_ENCRYPTION_KEY"):
        add_check(key, bool(os.getenv(key)), "已配置" if os.getenv(key) else "缺少环境变量")

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        add_check("database", True, "连接正常")
    except Exception as e:
        add_check("database", False, str(e))
    finally:
        try:
            db.close()
        except Exception:
            pass

    for name, path in {
        "static": BASE_DIR / "static",
        "knowledge_files": BASE_DIR / "knowledge_files",
        "vector_db": BASE_DIR / "vector_db",
        "skills": BASE_DIR / "skills",
    }.items():
        add_check(name, path.exists(), str(path))

    ok = all(item["ok"] for item in checks)
    return {
        "ok": ok,
        "checks": checks,
        "cache": {
            "config": config_cache.stats(),
            "skill": skill_cache.stats(),
        },
    }


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
