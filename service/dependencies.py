from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from models.init_db import get_db
from models.user_dao import get_user_by_id
from service.auth import decode_access_token

# tokenUrl 指向登录接口的路径，Swagger UI 会用它做登录按钮
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    解析 token，返回当前登录用户
    :raises HTTPException: token 无效/过期/用户不存在时抛 401
    :return: User 对象
    """
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
    # 4. 返回用户对象
    return user