"""E2E 冒烟测试用的后端启动器：真实 FastAPI 应用 + 真实 MySQL + 内嵌 ChromaDB，
只把"会花钱 / 需要联网"的两处（大模型、向量化）换成进程内假实现（见 fakes.py）。

和 `scripts/e2e_smoke.py`（编排 + 7 个流程的 Playwright 脚本）配合用，不单独跑。
必须在 monkeypatch 之后再 import FasdtApi.main，且全程只有这一个进程碰 ChromaDB
的内嵌 PersistentClient——它不是多进程安全的，另开进程/Worker 一起写会有锁冲突风险。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _configure_env() -> None:
    os.environ["APP_ENV"] = "test"
    os.environ.setdefault("JWT_SECRET_KEY", "e2e-smoke-jwt-secret-not-for-production")
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("LLM_ENCRYPTION_KEY", "LG5sThiGcVsg9jRbbN_fezONjfKdo3E72yQPYIUwZHQ=")
    os.environ.setdefault("TRUSTED_HOSTS", "127.0.0.1,localhost")
    os.environ.setdefault("CORS_ALLOW_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    os.environ.setdefault("REDIS_URL", "")
    os.environ.setdefault("SMS_PROVIDER", "console")
    os.environ["SMS_EXPOSE_DEV_CODE"] = "1"  # E2E 脚本要能从接口响应里直接拿到验证码
    # 用 worker 模式（和生产一致）：上传接口只落库、不在请求里跑索引；真正执行靠
    # main() 里起的后台轮询线程调 background_worker.run_once()。
    # 之前试过 TASK_EXECUTION_MODE=inline（FastAPI BackgroundTasks 在本请求里直接跑），
    # 实测在这个项目的中间件链下背景任务从不执行（任务永远停在 queued）——这条路径本来就
    # 只有"本地开发"在用、生产和大多数本地开发也是起独立 Worker 进程，几乎没有真正被走过，
    # 所以不去费力查中间件到底在哪一层把 BackgroundTasks 弄丢，直接换成和生产同款的路子。
    os.environ.setdefault("TASK_EXECUTION_MODE", "worker")
    # ChromaDB 走内嵌 PersistentClient（不设 CHROMA_SERVER_HOST），数据放独立临时目录，
    # 跑完整个冒烟测试后由 scripts/e2e_smoke.py 统一清理，不污染本地开发用的 vector_db/
    os.environ.setdefault("VECTOR_DB_PATH", os.path.join(
        os.environ.get("E2E_DATA_DIR", os.path.join(os.path.dirname(__file__), ".e2e_data")), "vector_db",
    ))
    # 模型/向量化换成假实现，但出站校验本来就该放行本地地址——防御性设置，即使这次用不到
    os.environ.setdefault("CRAWLER_ALLOW_PRIVATE_NETWORK", "1")


def _patch_fakes() -> None:
    """必须在 import 任何用到这两个工厂的模块之前打上，否则已经绑定的引用不会跟着变。"""
    from tests_e2e.fakes import FakeEmbedding, make_fake_chat_model

    import service.rag.embedding_service as embedding_service
    embedding_service._get_client = lambda db, user_id, model_name=None: FakeEmbedding()

    async def _fake_get_client_async(db, user_id, model_name=None):
        return FakeEmbedding()
    embedding_service._get_client_async = _fake_get_client_async

    import service.tools.executor as executor

    def _fake_create_langchain_llm(db, user_id, model_name, temperature=0.7, api_url=None):
        answer = os.environ.get(
            "E2E_FAKE_ANSWER",
            "已经查过资料：专业版一年授权的价格是 39 元/月，包含数据分析和自动化两项能力。【来源1】",
        )
        return make_fake_chat_model(answer)
    executor.create_langchain_llm = _fake_create_langchain_llm


def _start_inline_worker_thread() -> None:
    """在本进程内起一个轮询线程跑 service.background_worker.run_once()——和真的独立
    Worker 进程做一样的事（claim_next_task + run_task_by_id），只是不用另开进程。
    必须是同一个进程：ChromaDB 内嵌 PersistentClient 不是多进程安全的。
    """
    import threading
    import time

    from service import background_worker

    def _loop() -> None:
        while True:
            try:
                background_worker.run_once()
            except Exception:  # noqa: BLE001 - 探测循环本身不能被单次任务异常打断
                pass
            time.sleep(0.3)

    threading.Thread(target=_loop, daemon=True, name="e2e-inline-worker").start()


def main() -> None:
    _configure_env()
    _patch_fakes()

    import uvicorn

    from models.init_db import bootstrap_database
    bootstrap_database(force=True)

    from FasdtApi.main import app

    _start_inline_worker_thread()

    port = int(os.environ.get("E2E_BACKEND_PORT", "8011"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
