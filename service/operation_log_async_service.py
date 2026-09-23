"""操作日志异步查询服务。"""

from utils.timeutil import utcnow
from datetime import timedelta
from typing import Dict

from sqlalchemy import func, or_, select

from models.init_db import OperationLog
from service.operation_log_service import _format_dt


async def list_operation_logs(
        db,
        limit: int = 100,
        offset: int = 0,
        keyword: str = None,
        method: str = None,
        status_group: str = None,
        user_id: int = None,
        days: int = 7,
) -> Dict:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    days = max(1, min(days, 90))
    conditions = [OperationLog.created_at >= utcnow() - timedelta(days=days)]

    if user_id:
        conditions.append(OperationLog.user_id == user_id)
    if method:
        conditions.append(OperationLog.method == method.upper())
    if status_group == "success":
        conditions.extend([OperationLog.status_code >= 200, OperationLog.status_code < 400])
    elif status_group == "error":
        conditions.append(OperationLog.status_code >= 400)
    elif status_group == "slow":
        conditions.append(OperationLog.latency_ms >= 1000)
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(or_(
            OperationLog.path.like(like),
            OperationLog.username.like(like),
            OperationLog.client_ip.like(like),
            OperationLog.error_msg.like(like),
        ))

    total = int((await db.execute(select(func.count(OperationLog.id)).where(*conditions))).scalar() or 0)

    result = await db.execute(
        select(OperationLog)
        .where(*conditions)
        .order_by(OperationLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [
        {
            "id": item.id,
            "user_id": item.user_id,
            "username": item.username,
            "method": item.method,
            "path": item.path,
            "status_code": item.status_code,
            "latency_ms": item.latency_ms,
            "client_ip": item.client_ip,
            "user_agent": item.user_agent,
            "error_msg": item.error_msg,
            "created_at": _format_dt(item.created_at),
        }
        for item in result.scalars().all()
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
