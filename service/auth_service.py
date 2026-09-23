from utils.timeutil import utcnow
import bcrypt
from datetime import datetime
from fastapi import HTTPException, status
from models.user_dao import get_user_by_name, get_user_by_phone, create_user, update_user_password
from sqlalchemy.exc import IntegrityError
from service.auth import create_access_token
from service.admin_service import current_user_payload, role_names
from service.password_policy import PasswordPolicyError, check_password_policy
from service.phone_verification_service import verify_register_code
import time
from utils.logger_handler import logger, log_user_behavior

# 密码加密工具（直接使用 bcrypt 库，避免 passlib 与 bcrypt 4.x 的兼容性问题）
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(password: str) -> str:
    """使用 bcrypt 对密码进行哈希"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """校验密码是否匹配"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def is_bcrypt_hash(value: str) -> bool:
    """判断存储值是否为 bcrypt 哈希。"""
    return isinstance(value, str) and value.startswith(_BCRYPT_PREFIXES)


def password_matches(plain: str, stored: str) -> bool:
    """校验明文口令是否匹配已存储的 bcrypt 哈希。

    非 bcrypt 格式（历史明文或脏数据）一律视为不匹配——存量明文口令
    须先用 scripts/migrate_plaintext_passwords.py 迁移为哈希。
    """
    if not is_bcrypt_hash(stored):
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
    except (ValueError, TypeError):
        return False
# 登录业务
def login(db, name: str, password: str):
    start = time.time()  # 记录开始时间，用于计算耗时
    # 统一的失败响应：不区分“用户不存在”和“密码错误”，避免账号枚举。
    invalid_credentials = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="账号或密码错误",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # 1. 查询用户
    user = get_user_by_name(db,name)
    if not user:
        logger.warning(f"登录失败-用户不存在: name={name}")#日志
        log_user_behavior(0, "login", "fail", start)   # ← user_id 未知传 0
        raise invalid_credentials
    # 2. 验证密码（仅接受 bcrypt 哈希；存量明文须先跑迁移脚本）
    if not password_matches(password, user.password):
        logger.warning(f"登录失败-密码错误: name={name}")#日志
        log_user_behavior(user.id, "login", "fail", start)
        raise invalid_credentials
    # 3. 凭证正确后再校验账号状态：禁用信息只对本人可见，不作为枚举入口。
    if getattr(user, "is_disabled", 0) == 1:
        logger.warning(f"登录失败-用户已禁用: user_id={user.id}, name={name}")
        log_user_behavior(user.id, "login", "fail", start)
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")
    now = utcnow()
    user.last_login_at = now
    user.last_seen_at = now
    db.commit()
    db.refresh(user)
    # 3. 登录成功，生成 token（带上当前的 token 版本号，改密码/强制下线后旧 token 会因为版本号不一致而失效）
    token_data = {
        "user_id": user.id,
        "username": user.name,
        "ver": getattr(user, "auth_version", 0) or 0,
    }
    access_token = create_access_token(token_data)
    # 4. 返回结果（带 token）
    logger.info(f"登录成功: user_id={user.id}, name={name}")#日志
    log_user_behavior(user.id, "login", "success", start)
    return {
        "message": "登录成功",
        "user_id": user.id,
        "username": user.name,
        "selected_agent_id": user.selected_agent_id,
        "roles": role_names(user),
        "is_admin": current_user_payload(user)["is_admin"],
        "access_token": access_token,
        "token_type": "bearer"
    }
# 注册业务
def register(db, name: str, password: str, age: int, phone: str, sms_code: str, accepted_terms: bool):
    start = time.time()  # 记录开始时间，用于计算耗时
    if not accepted_terms:
        logger.warning(f"注册失败-未同意用户须知: name={name}")
        log_user_behavior(0, "register", "fail", start)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="请先阅读并同意用户须知")

    if name.strip().lower() == "admin":
        logger.warning("注册失败-保留用户名: name=admin")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "admin 为系统保留账号，不能注册"}
    try:
        check_password_policy(password, username=name, phone=phone)
    except PasswordPolicyError as e:
        logger.warning(f"注册失败-密码不符合策略: name={name}")
        log_user_behavior(0, "register", "fail", start)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    phone = verify_register_code(phone, sms_code, consume=False)
    # 1. 查询用户是否存在
    user = get_user_by_name(db,name)
    if user:
        logger.warning(f"注册失败-用户已存在: name={name}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "用户已经存在"}
    if get_user_by_phone(db, phone):
        logger.warning(f"注册失败-手机号已注册: phone={phone}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "手机号已经注册"}
    # 2. 密码加密
    hashed_password = hash_password(password)
    # 3. 添加用户
    try:
        new_user = create_user(db, name, hashed_password, age, phone=phone)
    except IntegrityError:
        db.rollback()
        logger.warning(f"注册失败-并发冲突: name={name}, phone={phone}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "用户名或手机号已经存在"}
    verify_register_code(phone, sms_code, consume=True)
    logger.info(f"注册成功: user_id={new_user.id}, name={name}")
    log_user_behavior(new_user.id, "register", "success", start)
    # 4. 返回结果
    return {
        "message": "注册成功",
        "user_id": new_user.id,
        "username": new_user.name
    }


def change_password(db, user, old_password: str, new_password: str):
    """当前登录用户修改密码。成功后旧 token 全部失效（见 update_user_password）。"""
    if not password_matches(old_password, user.password):
        logger.warning(f"修改密码失败-旧密码错误: user_id={user.id}")
        return {"message": "旧密码错误"}
    try:
        check_password_policy(new_password, username=user.name, phone=getattr(user, "phone", "") or "")
    except PasswordPolicyError as e:
        return {"message": str(e)}
    if old_password == new_password:
        return {"message": "新密码不能和旧密码相同"}
    update_user_password(db, user, hash_password(new_password))
    logger.info(f"修改密码成功: user_id={user.id}")
    return {"message": "修改成功"}
