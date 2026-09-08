from datetime import datetime, timezone
from typing import List, Optional

from models.init_db import BackgroundTask


def _utcnow() -> datetime:
    """返回无时区 UTC 时间，兼容现有数据库字段。"""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_task(db, user_id: int, task_type: str, title: str,
                agent_id: int = None, target_type: str = None,
                target_id: int = None,
                parent_task_id: int = None) -> BackgroundTask:
    task = BackgroundTask(
        user_id=user_id,
        agent_id=agent_id,
        task_type=task_type,
        title=title,
        target_type=target_type,
        target_id=target_id,
        status="queued",
        progress=0,
        retry_count=0,
        parent_task_id=parent_task_id,
        next_run_at=None,
    )
    db.add(task)
    db.flush()
    return task


def get_task_by_id(db, task_id: int) -> Optional[BackgroundTask]:
    return db.query(BackgroundTask).filter(BackgroundTask.id == task_id).first()


def list_tasks_by_user(db, user_id: int, limit: int = 30,
                       status: str = None, task_type: str = None) -> List[BackgroundTask]:
    # 查询用户的后台任务，支持按 status / task_type 筛选
    q = db.query(BackgroundTask).filter(BackgroundTask.user_id == user_id)
    if status:
        q = q.filter(BackgroundTask.status == status)
    if task_type:
        q = q.filter(BackgroundTask.task_type == task_type)
    return q.order_by(BackgroundTask.created_at.desc()).limit(limit).all()


def list_all_tasks(db, limit: int = 50,
                   status: str = None, task_type: str = None) -> List[BackgroundTask]:
    # 管理员查询全局后台任务，支持筛选
    q = db.query(BackgroundTask)
    if status:
        q = q.filter(BackgroundTask.status == status)
    if task_type:
        q = q.filter(BackgroundTask.task_type == task_type)
    return q.order_by(BackgroundTask.created_at.desc()).limit(limit).all()


def update_task(db, task: BackgroundTask, status: str = None,
                progress: int = None, result: str = None,
                error_msg: str = None, next_run_at=None) -> BackgroundTask:
    if status is not None:
        task.status = status
        if status == "running" and not task.started_at:
            task.started_at = _utcnow()
        if status == "queued":
            task.started_at = None
            task.finished_at = None
        # finished/failed/cancelled 都算结束，记录 finished_at
        if status in {"finished", "failed", "cancelled"}:
            task.finished_at = _utcnow()
    if progress is not None:
        task.progress = max(0, min(100, int(progress)))
    if result is not None:
        task.result = result
    if error_msg is not None:
        task.error_msg = error_msg
    if next_run_at is not None or status in {"running", "finished", "failed", "cancelled"}:
        task.next_run_at = next_run_at
    db.flush()
    return task
