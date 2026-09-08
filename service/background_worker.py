import os
import time

from models.init_db import SessionLocal
from service import background_task_service
from utils.logger_handler import get_logger

logger = get_logger("background_worker")


def _env_float(name: str, default: float) -> float:
    """读取浮点型环境变量，主要用于 Worker 轮询间隔。"""

    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def run_once() -> bool:
    """执行一轮 Worker 调度。

    返回 True 表示本轮领取并执行了任务；返回 False 表示本轮没有可执行任务。
    拆出 run_once 是为了后续可以单独测试 Worker 领取逻辑，而不用启动无限循环。
    """
    db = SessionLocal()
    try:
        # 先恢复超时任务，再领取新任务，避免异常退出留下永久 running。
        requeued = background_task_service.requeue_stale_running_tasks(db)
        if requeued:
            logger.warning(f"已重新排队超时任务: {requeued} 个")

        task = background_task_service.claim_next_task(db)
        if not task:
            db.commit()
            return False

        # 领取任务后先提交事务，释放数据库行锁，再进入真正耗时的任务执行。
        task_id = task.id
        task_type = task.task_type
        db.commit()
        logger.info(f"Worker 领取任务: task={task_id}, type={task_type}")
    except Exception as e:
        db.rollback()
        logger.error(f"Worker 领取任务失败: {e}")
        return False
    finally:
        db.close()

    try:
        return background_task_service.run_task_by_id(task_id)
    except Exception as e:
        # 理论上具体任务函数会自己记录失败；这里是最后一道兜底，避免 Worker 崩掉。
        db = SessionLocal()
        try:
            background_task_service.mark_task_failed(db, task_id, str(e))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        logger.error(f"Worker 执行任务失败: task={task_id}, error={e}")
        return False


def run_forever() -> None:
    """持续运行 Worker。

    生产环境应由 Docker、systemd 或进程管理器托管该进程；进程退出后由外部系统拉起。
    """
    poll_seconds = _env_float("TASK_WORKER_POLL_SECONDS", 2.0)
    logger.info(f"后台任务 Worker 已启动，poll={poll_seconds}s")
    while True:
        handled = run_once()
        if not handled:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
