"""统一的 UTC 时间获取。

历史代码大量使用 ``datetime.utcnow()``（Python 3.12 起已废弃）。本项目所有
数据库 DateTime 列均为 naive（无时区），因此这里统一返回 naive UTC——
行为与 ``datetime.utcnow()`` 完全一致，只是不再触发废弃告警，并为将来
切换到时区感知时间留一个集中改造点。
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """当前 UTC 时间，naive（无 tzinfo），与 ``datetime.utcnow()`` 等价。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
