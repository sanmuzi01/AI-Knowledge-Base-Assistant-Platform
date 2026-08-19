from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.init_db import User, get_db
from service import admin_service
from service.dependencies import get_current_admin_user

router = APIRouter(prefix="/admin", tags=["管理员后台"])


class UserRolesUpdate(BaseModel):
    roles: List[str] = Field(default_factory=list)


class UserStatusUpdate(BaseModel):
    disabled: bool


class UserPasswordUpdate(BaseModel):
    new_password: str = Field(min_length=6)


@router.get("/me", summary="查询当前管理员信息")
def admin_me(current_user: User = Depends(get_current_admin_user)):
    return admin_service.current_user_payload(current_user)


@router.get("/overview", summary="后台总览统计")
def admin_overview(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    return admin_service.overview(db)


@router.get("/users", summary="用户管控列表")
def admin_users(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    return admin_service.list_users(db)


@router.get("/users/{user_id}", summary="查询用户详情")
def admin_user_detail(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    result = admin_service.get_user_detail(db, user_id)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return result


@router.put("/users/{user_id}/roles", summary="更新用户角色")
def admin_update_user_roles(
        user_id: int,
        data: UserRolesUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    result = admin_service.set_user_roles(db, user_id, data.roles, current_user.id)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    db.commit()
    return result


@router.patch("/users/{user_id}/status", summary="启用或禁用用户")
def admin_update_user_status(
        user_id: int,
        data: UserStatusUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    result = admin_service.set_user_disabled(db, user_id, data.disabled, current_user.id)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    db.commit()
    return result


@router.put("/users/{user_id}/password", summary="重置用户密码")
def admin_reset_user_password(
        user_id: int,
        data: UserPasswordUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    result = admin_service.reset_user_password(db, user_id, data.new_password)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    db.commit()
    return result


@router.delete("/users/{user_id}", summary="删除用户")
def admin_delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    result = admin_service.delete_user(db, user_id, current_user.id)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
    db.commit()
    return result


@router.get("/tasks", summary="查询全局后台任务")
def admin_tasks(
        limit: int = Query(default=50, ge=1, le=200),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user),
):
    return admin_service.list_recent_tasks(db, limit=limit)
