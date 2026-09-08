import json
import os
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_

from models.background_task_dao import (
    create_task,
    get_task_by_id,
    list_tasks_by_user,
    list_all_tasks as list_all_tasks_dao,
    update_task,
)
from models.init_db import SessionLocal
from models.init_db import BackgroundTask
from service.access_control import get_owned_task
from service.rag import rag_service
from utils.logger_handler import get_logger

logger = get_logger("background_task_service")
TaskRunner = Callable[[int, int, int, int], None]
TASK_RUNNERS: Dict[str, TaskRunner] = {}


def _utcnow() -> datetime:
    """返回无时区 UTC 时间，兼容现有数据库字段。"""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def register_task_runner(task_type: str):
    """注册后台任务处理函数。

    新增任务类型时，只需要给处理函数加上这个装饰器，调度、Worker 领取和重试会自动识别。
    """

    def decorator(func: TaskRunner) -> TaskRunner:
        TASK_RUNNERS[task_type] = func
        return func

    return decorator


def supported_task_types() -> set:
    """返回当前 Worker 支持执行的任务类型。"""

    return set(TASK_RUNNERS.keys())


def _env_int(name: str, default: int) -> int:
    """读取整数环境变量，配置缺失或格式错误时使用默认值。"""

    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def ensure_user_task_quota(db, user_id: int) -> None:
    """限制单个用户排队中/运行中的后台任务数量。

    这个限制用于保护 Worker 和数据库，防止用户连续上传大量文档导致任务积压失控。
    """
    max_active_tasks = _env_int("USER_MAX_ACTIVE_BACKGROUND_TASKS", 5)
    if max_active_tasks <= 0:
        return
    active_count = (
        db.query(func.count(BackgroundTask.id))
        .filter(
            BackgroundTask.user_id == user_id,
            BackgroundTask.status.in_(["queued", "running"]),
        )
        .scalar() or 0
    )
    if active_count >= max_active_tasks:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"后台任务过多，请等待已有任务完成后再提交（最多 {max_active_tasks} 个排队/运行任务）",
        )


def task_to_dict(task) -> Dict:
    """把 ORM 任务对象转成前端可直接使用的字典。"""

    return {
        "id": task.id,
        "user_id": task.user_id,
        "agent_id": task.agent_id,
        "task_type": task.task_type,
        "status": task.status,
        "title": task.title,
        "target_type": task.target_type,
        "target_id": task.target_id,
        "progress": task.progress,
        "result": json.loads(task.result) if task.result else None,
        "error_msg": task.error_msg,
        "retry_count": task.retry_count,
        "parent_task_id": task.parent_task_id,
        "created_at": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else None,
        "started_at": task.started_at.strftime("%Y-%m-%d %H:%M:%S") if task.started_at else None,
        "finished_at": task.finished_at.strftime("%Y-%m-%d %H:%M:%S") if task.finished_at else None,
        "next_run_at": task.next_run_at.strftime("%Y-%m-%d %H:%M:%S") if getattr(task, "next_run_at", None) else None,
    }


def create_background_task(db, user_id: int, task_type: str, title: str,
                           agent_id: int = None, target_type: str = None,
                           target_id: int = None) -> Dict:
    """创建后台任务记录。

    这里只负责入库，不直接执行耗时任务；是否交给 FastAPI BackgroundTasks
    或独立 Worker，由 schedule_task 和 TASK_EXECUTION_MODE 决定。
    """
    if task_type not in supported_task_types():
        raise ValueError(f"不支持的后台任务类型: {task_type}")
    ensure_user_task_quota(db, user_id)
    task = create_task(
        db=db,
        user_id=user_id,
        task_type=task_type,
        title=title,
        agent_id=agent_id,
        target_type=target_type,
        target_id=target_id,
    )
    return task_to_dict(task)


def task_execution_mode() -> str:
    """读取后台任务执行模式。生产环境推荐 worker。"""

    return os.getenv("TASK_EXECUTION_MODE", "worker").strip().lower()


def use_fastapi_background_tasks() -> bool:
    """是否使用 FastAPI BackgroundTasks 执行任务。该模式只建议本地开发使用。"""

    return task_execution_mode() in {"fastapi", "background", "inline"}


def schedule_task(task: Dict, background_tasks=None) -> None:
    """按配置调度任务。生产建议 TASK_EXECUTION_MODE=worker，由独立 Worker 执行。"""
    if not use_fastapi_background_tasks():
        # worker 模式下任务已经写入数据库，独立 Worker 会轮询领取，不需要 API 进程执行。
        return
    if background_tasks is None:
        raise ValueError("当前配置需要 FastAPI BackgroundTasks，但未传入 background_tasks")
    task_type = task.get("task_type")
    task_id = task["id"]
    user_id = task["user_id"]
    agent_id = task.get("agent_id")
    target_id = task.get("target_id")
    runner = TASK_RUNNERS.get(task_type)
    if not runner:
        raise ValueError(f"不支持的后台任务类型: {task_type}")
    background_tasks.add_task(runner, task_id, user_id, agent_id, target_id)


def get_user_task(db, user_id: int, task_id: int) -> Optional[Dict]:
    """查询当前用户自己的任务详情。"""

    task = get_owned_task(db, user_id, task_id)
    return task_to_dict(task) if task else None


def list_user_tasks(db, user_id: int, limit: int = 30,
                    status: str = None, task_type: str = None) -> List[Dict]:
    """查询当前用户任务列表，支持按状态和任务类型筛选。"""

    return [task_to_dict(t) for t in list_tasks_by_user(
        db, user_id, limit=limit, status=status, task_type=task_type
    )]


def list_all_tasks(db, limit: int = 50,
                   status: str = None, task_type: str = None) -> List[Dict]:
    # 管理员查询全局任务，支持筛选
    return [task_to_dict(t) for t in list_all_tasks_dao(
        db, limit=limit, status=status, task_type=task_type
    )]


def _get_task_for_action(db, user_id: int, task_id: int, is_admin: bool = False):
    """根据操作者身份获取任务：管理员可操作全局任务，普通用户只能操作自己的任务。"""

    if is_admin:
        return get_task_by_id(db, task_id)
    return get_owned_task(db, user_id, task_id)


def cancel_task(db, user_id: int, task_id: int, is_admin: bool = False) -> Optional[Dict]:
    """取消后台任务（只允许取消 queued 状态的任务）

    FastAPI BackgroundTasks 无法强制中断 running 状态的任务，
    所以只支持取消排队中的任务。running 状态会返回 None 由路由层报错。
    """
    task = _get_task_for_action(db, user_id, task_id, is_admin=is_admin)
    if not task:
        return None
    if task.status != "queued":
        # running/finished/failed/cancelled 都不允许取消
        return None
    update_task(db, task, status="cancelled", progress=0)
    db.commit()
    logger.info(f"取消后台任务: task={task_id}, user={user_id}")
    return task_to_dict(task)


def retry_task(db, user_id: int, task_id: int, is_admin: bool = False) -> Optional[Dict]:
    """重试后台任务（只允许重试 failed/cancelled 状态的任务）

    逻辑：
      1. 校验权限 + 状态（failed/cancelled 才能重试）
      2. 复制原任务参数，创建新任务（parent_task_id 指向原任务，retry_count+1）
      3. 返回新任务 dict（路由层统一调用 schedule_task 按配置调度）

    注意：本函数只创建任务记录，不直接执行。生产 worker 模式由独立 Worker 领取任务。
    """
    from models.background_task_dao import create_task as dao_create
    task = _get_task_for_action(db, user_id, task_id, is_admin=is_admin)
    if not task:
        return None
    if task.status not in {"failed", "cancelled"}:
        # queued/running/finished 不允许重试
        return None
    ensure_user_task_quota(db, task.user_id)
    # 创建新任务，继承原任务参数
    new_task = dao_create(
        db=db,
        user_id=task.user_id,
        task_type=task.task_type,
        title=task.title,
        agent_id=task.agent_id,
        target_type=task.target_type,
        target_id=task.target_id,
        parent_task_id=task.id,
    )
    # retry_count = 原任务的重试代数 + 1（表示这是第 N 次重试产生的任务）
    new_task.retry_count = (task.retry_count or 0) + 1
    db.flush()
    db.commit()
    logger.info(f"重试后台任务: 原task={task_id} → 新task={new_task.id}, user={user_id}")
    return task_to_dict(new_task)


def requeue_stale_running_tasks(db) -> int:
    """把超时的 running 任务重新放回队列。

    Worker 异常退出时，任务可能停留在 running 状态。这里按 started_at 判断超时，
    将任务恢复为 queued，避免任务永久卡死。
    """
    timeout_seconds = _env_int("TASK_RUNNING_TIMEOUT_SECONDS", 1800)
    if timeout_seconds <= 0:
        return 0
    cutoff = _utcnow() - timedelta(seconds=timeout_seconds)
    tasks = (
        db.query(BackgroundTask)
        .filter(BackgroundTask.status == "running", BackgroundTask.started_at < cutoff)
        .all()
    )
    for task in tasks:
        task.status = "queued"
        task.started_at = None
        task.finished_at = None
        task.next_run_at = _utcnow()
        task.error_msg = "任务执行超时，已重新排队"
        task.progress = 0
    db.flush()
    return len(tasks)


def claim_next_task(db) -> Optional[BackgroundTask]:
    """领取下一个可执行任务。

    with_for_update(skip_locked=True) 用于多 Worker 部署：一个 Worker 锁定任务后，
    其他 Worker 会跳过这条记录，避免重复执行。
    """
    task = (
        db.query(BackgroundTask)
        .filter(
            BackgroundTask.status == "queued",
            BackgroundTask.task_type.in_(supported_task_types()),
            or_(BackgroundTask.next_run_at.is_(None), BackgroundTask.next_run_at <= _utcnow()),
        )
        .order_by(BackgroundTask.next_run_at.asc(), BackgroundTask.created_at.asc(), BackgroundTask.id.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if not task:
        return None
    update_task(db, task, status="running", progress=max(task.progress or 0, 5))
    db.flush()
    return task


def mark_task_failed(db, task_id: int, message: str) -> None:
    """把任务标记为失败，并保存截断后的错误信息。"""

    task = get_task_by_id(db, task_id)
    if not task:
        return
    _mark_task_failed_or_retry(db, task, message)
    db.flush()


def run_task_by_id(task_id: int) -> bool:
    """按任务 ID 执行任务。

    这里先读取任务必要字段后关闭会话，再让具体任务函数创建自己的会话执行。
    这样可以避免长时间持有领取任务时的数据库连接。
    """
    db = SessionLocal()
    try:
        task = get_task_by_id(db, task_id)
        if not task or task.status == "cancelled":
            return False
        task_type = task.task_type
        user_id = task.user_id
        agent_id = task.agent_id
        target_id = task.target_id
    finally:
        db.close()

    runner = TASK_RUNNERS.get(task_type)
    if runner:
        runner(task_id, user_id, agent_id, target_id)
        return True

    db = SessionLocal()
    try:
        mark_task_failed(db, task_id, f"不支持的后台任务类型: {task_type}")
        db.commit()
    finally:
        db.close()
    return False


def _run_task_with_status(
        task_id: int,
        action: Callable,
        success_log: str,
        failure_log: str,
):
    """统一执行任务并维护状态。

    任务函数只负责描述“具体做什么”，状态流转、提交事务和失败记录都集中在这里。
    """
    db = SessionLocal()
    try:
        task = get_task_by_id(db, task_id)
        if not task:
            return
        # 取消检查：queued→cancelled 的任务被触发时跳过执行
        if task.status == "cancelled":
            logger.info(f"任务已取消，跳过执行: task={task_id}")
            return
        update_task(db, task, status="running", progress=10)
        db.commit()
        result = action(db)
        update_task(db, task, status="finished", progress=100, result=json.dumps(result, ensure_ascii=False))
        db.commit()
        logger.info(success_log)
    except Exception as e:
        db.rollback()
        logger.error(f"{failure_log}: task={task_id}, error={e}")
        try:
            task = get_task_by_id(db, task_id)
            if task:
                _mark_task_failed_or_retry(db, task, str(e))
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def _retry_delay_seconds(retry_count: int) -> int:
    """按重试次数计算退避时间，避免失败任务立刻反复占用 Worker。"""

    base_seconds = _env_int("TASK_RETRY_BASE_SECONDS", 30)
    max_seconds = _env_int("TASK_RETRY_MAX_SECONDS", 300)
    retry_count = max(0, retry_count)
    return max(1, min(max_seconds, base_seconds * (2 ** retry_count)))


def _mark_task_failed_or_retry(db, task: BackgroundTask, message: str) -> None:
    """失败时优先延迟重试；超过最大次数后才进入 failed 终态。"""

    max_retries = _env_int("TASK_MAX_AUTO_RETRIES", 2)
    error_msg = (message or "任务执行失败")[:1000]
    current_retry = int(task.retry_count or 0)
    if max_retries > 0 and current_retry < max_retries:
        delay = _retry_delay_seconds(current_retry)
        task.retry_count = current_retry + 1
        update_task(
            db,
            task,
            status="queued",
            progress=0,
            error_msg=f"{error_msg}；将在 {delay} 秒后自动重试（第 {task.retry_count}/{max_retries} 次）",
            next_run_at=_utcnow() + timedelta(seconds=delay),
        )
        logger.warning(f"任务失败，已安排自动重试: task={task.id}, retry={task.retry_count}/{max_retries}, delay={delay}s")
        return
    update_task(db, task, status="failed", progress=100, error_msg=error_msg)


@register_task_runner("knowledge_index")
def run_knowledge_index_task(task_id: int, user_id: int, agent_id: int, knowledge_id: int):
    _run_task_with_status(
        task_id=task_id,
        action=lambda db: rag_service.index_existing_knowledge(db, user_id, agent_id, knowledge_id),
        success_log=f"后台知识库入库完成: task={task_id}, knowledge={knowledge_id}",
        failure_log="后台知识库入库失败",
    )


@register_task_runner("knowledge_reindex")
def run_knowledge_reindex_task(task_id: int, user_id: int, agent_id: int, knowledge_id: int):
    _run_task_with_status(
        task_id=task_id,
        action=lambda db: rag_service.reindex_knowledge(db, user_id, agent_id, knowledge_id),
        success_log=f"后台知识库重建完成: task={task_id}, knowledge={knowledge_id}",
        failure_log="后台知识库重建失败",
    )
