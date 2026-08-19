import logging
import os
import sys
import time

from datetime import datetime

from utils.path_tool import get_abs_path

#日志保存的根目录
LOG_ROOT = get_abs_path("logs")

#确保日志的目录存在
os.makedirs(LOG_ROOT, exist_ok=True)

#日志的格式配置：error info debug
DEFAULT_LOG_FORMAT = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
#定义日志
def get_logger(
        name:str="agent",
        console_level:int=logging.INFO,
        file_level:int=logging.DEBUG,
        log_file = None,
)->logging.Logger:

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    #避免重复添加Handler，判断
    if logger.handlers:
        return logger

    #控制台Handler,把日志打印到控制终端
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(console_handler)

    #文件Handler
    if not log_file:
        log_file = os.path.join(
            LOG_ROOT, #日志文件存放的绝对路径
            f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        # 创建文件处理器（按天切割，自动保留7天）
        from logging.handlers import TimedRotatingFileHandler
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(DEFAULT_LOG_FORMAT)

        logger.addHandler(file_handler)
    return logger

logger = get_logger()
# 用户行为日志辅助函数（配合 log_to_csv 解析）
def log_user_behavior(user_id: int, action: str, status: str, start: float):
    """
    打印 USER_BEHAVIOR 格式日志
    :param user_id: 用户ID（未知时传 0）
    :param action: 行为类型，如 "login" / "register"
    :param status: "success" 或 "fail"
    :param start: 开始时间戳，由 time.time() 产生
    """
    duration = int((time.time() - start) * 1000)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logger.info(f"USER_BEHAVIOR|{user_id}|{action}|{status}|{duration}|{now}")
#快捷获取日志管理器