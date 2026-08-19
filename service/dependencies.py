from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.init_db import SessionLocal, get_db
from models.user_dao import get_user_by_id
from service.auth import decode_access_token
from service.admin_service import is_admin_user

# 使用 HTTPBearer：Swagger 会显示一个简单的 Bearer Token 输入框
# 用户直接填 token 即可，不需要走 OAuth2 密码流表单
security = HTTPBearer()


def _touch_user_seen(user_id: int) -> bool:
    """独立会话记录访问心跳，避免影响当前请求自己的事务。"""
    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE `user` SET last_seen_at = :last_seen_at WHERE id = :user_id"),
            {"last_seen_at": datetime.utcnow(), "user_id": user_id},
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    解析 token，返回当前登录用户
    :raises HTTPException: token 无效/过期/用户不存在时抛 401
    :return: User 对象
    """
    # 从 HTTPBearer 返回的凭证中提取 token 字符串
    token = credentials.credentials
    # 1. 解析 token
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 2. 从 payload 取 user_id
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token 中缺少用户信息",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 3. 查询用户是否存在（防止用户已注销但 token 还有效）
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if getattr(user, "is_disabled", 0) == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用，请联系管理员",
        )
    now = datetime.utcnow()
    last_seen_at = getattr(user, "last_seen_at", None)
    if not last_seen_at or (now - last_seen_at).total_seconds() > 30:
        if _touch_user_seen(user.id):
            db.refresh(user)
    # 4. 返回用户对象
    return user


def get_current_admin_user(current_user=Depends(get_current_user)):
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
