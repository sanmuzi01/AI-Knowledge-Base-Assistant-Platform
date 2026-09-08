"""异步认证服务。"""

from datetime import datetime
import time

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from models.user_async_dao import (
    create_user_async,
    get_user_by_name_async,
    get_user_by_phone_async,
    update_user_login_seen_async,
    update_user_password_async,
)
from service.admin_service import current_user_payload, role_names
from service.auth import create_access_token
from service.auth_service import hash_password, verify_password
from service.phone_verification_service import verify_register_code
from utils.logger_handler import logger, log_user_behavior


async def login(db, name: str, password: str):
    """异步登录：数据库走 AsyncSession，bcrypt 放线程池。"""

    start = time.time()
    # 统一的失败响应：不区分“用户不存在”和“密码错误”，避免账号枚举。
    invalid_credentials = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="账号或密码错误",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = await get_user_by_name_async(db, name)
    if not user:
        logger.warning(f"登录失败-用户不存在: name={name}")
        log_user_behavior(0, "login", "fail", start)
        raise invalid_credentials

    if user.password.startswith("$2b$"):
        ok = await run_in_threadpool(verify_password, password, user.password)
        if not ok:
            logger.warning(f"登录失败-密码错误: name={name}")
            log_user_behavior(user.id, "login", "fail", start)
            raise invalid_credentials
    else:
        if user.password != password:
            logger.warning(f"登录失败-密码错误: name={name}")
            log_user_behavior(user.id, "login", "fail", start)
            raise invalid_credentials
        hashed = await run_in_threadpool(hash_password, password)
        await update_user_password_async(db, user.id, hashed)
        user.password = hashed

    # 凭证正确后再校验账号状态：禁用信息只对本人可见，不作为枚举入口。
    if getattr(user, "is_disabled", 0) == 1:
        logger.warning(f"登录失败-用户已禁用: user_id={user.id}, name={name}")
        log_user_behavior(user.id, "login", "fail", start)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")

    now = datetime.utcnow()
    await update_user_login_seen_async(db, user.id, now)
    user.last_login_at = now
    user.last_seen_at = now

    access_token = create_access_token({
        "user_id": user.id,
        "username": user.name,
    })
    logger.info(f"登录成功: user_id={user.id}, name={name}")
    log_user_behavior(user.id, "login", "success", start)
    return {
        "message": "登录成功",
        "user_id": user.id,
        "username": user.name,
        "selected_agent_id": user.selected_agent_id,
        "roles": role_names(user),
        "is_admin": current_user_payload(user)["is_admin"],
        "access_token": access_token,
        "token_type": "bearer",
    }


async def register(db, name: str, password: str, age: int, phone: str, sms_code: str, accepted_terms: bool):
    """异步注册：验证码校验保持共享缓存逻辑，数据库读写使用 AsyncSession。"""

    start = time.time()
    if not accepted_terms:
        logger.warning(f"注册失败-未同意用户须知: name={name}")
        log_user_behavior(0, "register", "fail", start)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="请先阅读并同意用户须知")

    if name.strip().lower() == "admin":
        logger.warning("注册失败-保留用户名: name=admin")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "admin 为系统保留账号，不能注册"}

    phone = await run_in_threadpool(verify_register_code, phone, sms_code, False)
    if await get_user_by_name_async(db, name):
        logger.warning(f"注册失败-用户已存在: name={name}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "用户已经存在"}
    if await get_user_by_phone_async(db, phone):
        logger.warning(f"注册失败-手机号已注册: phone={phone}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "手机号已经注册"}

    hashed_password = await run_in_threadpool(hash_password, password)
    try:
        new_user = await create_user_async(db, name, hashed_password, age, phone=phone)
    except IntegrityError:
        await db.rollback()
        logger.warning(f"注册失败-并发冲突: name={name}, phone={phone}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "用户名或手机号已经存在"}

    await run_in_threadpool(verify_register_code, phone, sms_code, True)
    logger.info(f"注册成功: user_id={new_user.id}, name={name}")
    log_user_behavior(new_user.id, "register", "success", start)
    return {
        "message": "注册成功",
        "user_id": new_user.id,
        "username": new_user.name,
    }


async def change_password(db, user, old_password: str, new_password: str):
    """异步修改当前登录用户密码，bcrypt 放线程池执行。"""

    if user.password.startswith("$2b$"):
        ok = await run_in_threadpool(verify_password, old_password, user.password)
    else:
        ok = user.password == old_password
    if not ok:
        logger.warning(f"修改密码失败-旧密码错误: user_id={user.id}")
        return {"message": "旧密码错误"}
    if old_password == new_password:
        return {"message": "新密码不能和旧密码相同"}
    hashed = await run_in_threadpool(hash_password, new_password)
    await update_user_password_async(db, user.id, hashed)
    logger.info(f"修改密码成功: user_id={user.id}")
    return {"message": "修改成功"}
