from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from models.init_db import User, get_db
from service import background_task_service
from service.admin_service import is_admin_user
from service.dependencies import get_current_user

router = APIRouter(prefix="/task", tags=["后台任务"])


def _require_admin(current_user: User):
    if not is_admin_user(current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )


@router.get("/", summary="查询当前用户后台任务（支持筛选）")
def list_tasks(
    limit: int = 30,
    status: str = None,
    task_type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return background_task_service.list_user_tasks(
        db, current_user.id, limit=limit, status=status, task_type=task_type
    )


@router.get("/all", summary="管理员查询全局后台任务")
def list_all_tasks(
    limit: int = 50,
    status: str = None,
    task_type: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return background_task_service.list_all_tasks(
        db, limit=limit, status=status, task_type=task_type
    )


@router.get("/{task_id}", summary="查询后台任务详情")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = background_task_service.get_user_task(db, current_user.id, task_id)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在或无权限")
    return task


@router.post("/{task_id}/retry", summary="重试后台任务")
def retry_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. 创建重试任务（service 层校验权限 + 状态 + 复制参数）
    new_task = background_task_service.retry_task(db, current_user.id, task_id, is_admin=is_admin_user(current_user))
    if not new_task:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="任务不存在、无权限，或当前状态不允许重试（仅 failed/cancelled 可重试）",
        )
    # 2. 根据 task_type 用 BackgroundTasks 触发执行
    _dispatch_task_runner(new_task, background_tasks)
    return {
        "code": 200,
        "msg": "已创建重试任务并开始执行",
        "data": new_task,
    }


@router.post("/{task_id}/cancel", summary="取消后台任务")
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = background_task_service.cancel_task(db, current_user.id, task_id, is_admin=is_admin_user(current_user))
    if not task:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="任务不存在、无权限，或当前状态不允许取消（仅 queued 可取消；running 无法中断）",
        )
    return {
        "code": 200,
        "msg": "已取消任务",
        "data": task,
    }


def _dispatch_task_runner(task: dict, background_tasks: BackgroundTasks):
    """根据 task_type 把对应的 run_xxx 函数加入 BackgroundTasks

    task_type 与 run 函数的映射：
      knowledge_index   → run_knowledge_index_task(task_id, user_id, agent_id, knowledge_id)
      knowledge_reindex → run_knowledge_reindex_task(task_id, user_id, agent_id, knowledge_id)
      其他类型          → 不触发（任务保持 queued，需手动处理或后续扩展）
    """
    task_type = task.get("task_type")
    new_id = task["id"]
    user_id = task["user_id"]
    agent_id = task.get("agent_id")
    # target_id 对知识库任务就是 knowledge_id
    knowledge_id = task.get("target_id")

    if task_type == "knowledge_index":
        background_tasks.add_task(
            background_task_service.run_knowledge_index_task,
            new_id, user_id, agent_id, knowledge_id,
        )
    elif task_type == "knowledge_reindex":
        background_tasks.add_task(
            background_task_service.run_knowledge_reindex_task,
            new_id, user_id, agent_id, knowledge_id,
        )
    # 其他 task_type：暂不支持自动重试，任务保持 queued 状态
