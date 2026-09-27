"""通用审计事件的写入入口（Phase 3D 阶段6，docs/enterprise-rbac-plan.md 9.5）。

跟 `service/knowledge_space/space_async_service.py::_audit` 是同一种"尽力而为"
写法：审计失败不能拖垮主流程，broad except + 独立 rollback。目前唯一的调用方是
`service/approval_service.py`（审批的创建/决定），以后企业成员/角色变更之类的写操作
要留痕时也调这里，不新建一张表。
"""
from typing import Any

from utils.logger_handler import get_logger

logger = get_logger("audit_service")


def record(db, user_id: int, action: str, *, resource_type: str = None,
           resource_id: int = None, detail: Any = None) -> None:
    from models import audit_dao

    try:
        audit_dao.record(db, user_id, action, resource_type=resource_type,
                          resource_id=resource_id, detail=detail, commit=True)
    except Exception:  # noqa: BLE001 —— 审计失败不影响主流程
        logger.warning(f"审计写入失败：user={user_id} action={action}", exc_info=True)
        db.rollback()


async def record_async(db, user_id: int, action: str, *, resource_type: str = None,
                        resource_id: int = None, detail: Any = None) -> None:
    from models import audit_dao

    try:
        await audit_dao.record_async(db, user_id, action, resource_type=resource_type,
                                      resource_id=resource_id, detail=detail)
    except Exception:  # noqa: BLE001 —— 审计失败不影响主流程
        logger.warning(f"审计写入失败：user={user_id} action={action}", exc_info=True)
        await db.rollback()
