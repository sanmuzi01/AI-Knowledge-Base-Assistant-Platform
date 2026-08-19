import json
from typing import Dict, List, Optional

from models.background_task_dao import (
    create_task,
    get_task_by_id,
    list_tasks_by_user,
    list_all_tasks as list_all_tasks_dao,
    update_task,
)
from models.init_db import SessionLocal
from service.access_control import get_owned_task
from service.rag import rag_service
from utils.logger_handler import get_logger

logger = get_logger("background_task_service")


def task_to_dict(task) -> Dict:
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
    }


def create_background_task(db, user_id: int, task_type: str, title: str,
                           agent_id: int = None, target_type: str = None,
                           target_id: int = None) -> Dict:
    task = create_task(
        db=db,
        user_id=user_id,
        task_type=task_type,
        title=title,
        target_type=target_type,
        target_id=target_id,
    )
    return task_to_dict(task)


def get_user_task(db, user_id: int, task_id: int) -> Optional[Dict]:
    task = get_owned_task(db, user_id, task_id)
    return task_to_dict(task) if task else None


def list_user_tasks(db, user_id: int, limit: int = 30,
                    status: str = None, task_type: str = None) -> List[Dict]:
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
      3. 返回新任务 dict（路由层根据 task_type 用 BackgroundTasks 触发执行）

    注意：本函数只创建任务记录，不触发执行。执行由路由层 dispatch。
    """
    from models.background_task_dao import create_task as dao_create
    task = _get_task_for_action(db, user_id, task_id, is_admin=is_admin)
    if not task:
        return None
    if task.status not in {"failed", "cancelled"}:
        # queued/running/finished 不允许重试
        return None
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


def run_knowledge_index_task(task_id: int, user_id: int, agent_id: int, knowledge_id: int):
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
        result = rag_service.index_existing_knowledge(db, user_id, agent_id, knowledge_id)
        update_task(db, task, status="finished", progress=100, result=json.dumps(result, ensure_ascii=False))
        db.commit()
        logger.info(f"后台知识库入库完成: task={task_id}, knowledge={knowledge_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"后台知识库入库失败: task={task_id}, error={e}")
        try:
            task = get_task_by_id(db, task_id)
            if task:
                update_task(db, task, status="failed", progress=100, error_msg=str(e)[:1000])
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def run_knowledge_reindex_task(task_id: int, user_id: int, agent_id: int, knowledge_id: int):
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
        result = rag_service.reindex_knowledge(db, user_id, agent_id, knowledge_id)
        update_task(db, task, status="finished", progress=100, result=json.dumps(result, ensure_ascii=False))
        db.commit()
        logger.info(f"后台知识库重建完成: task={task_id}, knowledge={knowledge_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"后台知识库重建失败: task={task_id}, error={e}")
        try:
            task = get_task_by_id(db, task_id)
            if task:
                update_task(db, task, status="failed", progress=100, error_msg=str(e)[:1000])
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
