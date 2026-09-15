"""后台任务异步读服务。"""

from typing import Dict, List, Optional

from starlette.concurrency import run_in_threadpool

from models import background_task_async_dao as dao
from service import background_task_service
from service.background_task_service import task_to_dict


async def get_user_task(db, user_id: int, task_id: int) -> Optional[Dict]:
    task = await dao.get_owned_task_async(db, user_id, task_id)
    return task_to_dict(task) if task else None


async def list_user_tasks(
        db,
        user_id: int,
        limit: int = 30,
        status: str = None,
        task_type: str = None,
) -> List[Dict]:
    tasks = await dao.list_tasks_by_user_async(
        db, user_id, limit=limit, status=status, task_type=task_type
    )
    return [task_to_dict(task) for task in tasks]


async def list_all_tasks(
        db,
        limit: int = 50,
        offset: int = 0,
        status: str = None,
        task_type: str = None,
) -> Dict:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = await dao.count_all_tasks_async(db, status=status, task_type=task_type)
    tasks = await dao.list_all_tasks_async(
        db, limit=limit, offset=offset, status=status, task_type=task_type
    )
    return {
        "items": [task_to_dict(task) for task in tasks],
        "total": total, "limit": limit, "offset": offset,
    }


async def retry_task(user_id: int, task_id: int, is_admin: bool = False) -> Optional[Dict]:
    """在独立同步会话中执行同步实现（内部自行 commit），结果为纯 dict。"""
    from models.init_db import SessionLocal

    def _run() -> Optional[Dict]:
        session = SessionLocal()
        try:
            return background_task_service.retry_task(session, user_id, task_id, is_admin)
        finally:
            session.close()

    return await run_in_threadpool(_run)


async def cancel_task(user_id: int, task_id: int, is_admin: bool = False) -> Optional[Dict]:
    from models.init_db import SessionLocal

    def _run() -> Optional[Dict]:
        session = SessionLocal()
        try:
            return background_task_service.cancel_task(session, user_id, task_id, is_admin)
        finally:
            session.close()

    return await run_in_threadpool(_run)
