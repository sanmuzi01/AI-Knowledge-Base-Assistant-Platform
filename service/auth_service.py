from passlib.context import CryptContext
from models.user_dao import get_user_by_name, create_user,update_user_password
from sqlalchemy.exc import IntegrityError
from models.init_db import SessionLocal
from service.auth import create_access_token
import time
from utils.logger_handler import logger, log_user_behavior
# 密码加密工具
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)
# 登录业务
def login(db, name: str, password: str):
    start = time.time()  # 记录开始时间，用于计算耗时
    # 1. 查询用户
    user = get_user_by_name(db,name)
    if not user:
        logger.warning(f"登录失败-用户不存在: name={name}")#日志
        log_user_behavior(0, "login", "fail", start)   # ← user_id 未知传 0
        return {"message": "用户不存在"}
    # 2. 验证密码
    if user.password.startswith("$2b$"):
        # 新哈希密码：用 verify 校验
        if not pwd_context.verify(password, user.password):
            logger.warning(f"登录失败-密码错误: name={name}")#日志
            log_user_behavior(user.id, "login", "fail", start)
            return {"message": "密码错误"}
    else:
        # 老明文密码：直接比对
        if user.password != password:
            logger.warning(f"登录失败-密码错误: name={name}")#日志
            log_user_behavior(user.id, "login", "fail", start)
            return {"message": "密码错误"}
        # 顺手升级为哈希
        hashed = pwd_context.hash(password)
        update_user_password(db, user, hashed)
    # 3. 登录成功，生成 token
    token_data = {
        "user_id": user.id,
        "username": user.name
    }
    access_token = create_access_token(token_data)
    # 4. 返回结果（带 token）
    logger.info(f"登录成功: user_id={user.id}, name={name}")#日志
    log_user_behavior(user.id, "login", "success", start)
    return {
        "message": "登录成功",
        "user_id": user.id,
        "username": user.name,
        "access_token": access_token,
        "token_type": "bearer"
    }
# 注册业务
def register(db,name: str,password: str,age: int):
    start = time.time()  # 记录开始时间，用于计算耗时
    # 1. 查询用户是否存在
    user = get_user_by_name(db,name)
    if user:
        logger.warning(f"注册失败-用户已存在: name={name}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "用户已经存在"}
    # 2. 密码加密
    hashed_password = pwd_context.hash(password)
    # 3. 添加用户
    try:
        new_user = create_user(db, name, hashed_password, age)
    except IntegrityError:
        db.rollback()
        logger.warning(f"注册失败-并发冲突: name={name}")
        log_user_behavior(0, "register", "fail", start)
        return {"message": "用户已经存在"}
    logger.info(f"注册成功: user_id={new_user.id}, name={name}")
    log_user_behavior(new_user.id, "register", "success", start)
    # 4. 返回结果
    return {
        "message": "注册成功",
        "user_id": new_user.id,
        "username": new_user.name
    }