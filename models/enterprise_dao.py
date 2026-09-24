"""企业/部门成员关系的只读查询（Phase 3B，docs/enterprise-rbac-plan.md）。

只服务一件事：knowledge_spaces 的可见性计算要不要把"部门管理员"算进去——
service/access_control.py 是唯一调用方，别处不要直接查这几张表，避免以后
"谁是部门管理员"的判定逻辑散落在多个地方。
"""
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_TEAM_ADMIN_OF_TEAM_SQL = (
    "SELECT 1 FROM team_members tm JOIN enterprise_role er ON tm.role_id = er.id "
    "WHERE tm.user_id = :uid AND tm.team_id = :tid AND tm.status = 'active' "
    "AND er.scope = 'team' AND er.code = 'admin' LIMIT 1"
)

_SPACE_IDS_WHERE_TEAM_ADMIN_SQL = (
    "SELECT ks.id FROM knowledge_spaces ks "
    "JOIN team_members tm ON tm.team_id = ks.team_id "
    "JOIN enterprise_role er ON tm.role_id = er.id "
    "WHERE tm.user_id = :uid AND tm.status = 'active' "
    "AND er.scope = 'team' AND er.code = 'admin'"
)


# ---------------- 同步 ----------------

def is_team_admin_of_team(db, user_id: int, team_id: Optional[int]) -> bool:
    if team_id is None:
        return False
    return db.execute(text(_TEAM_ADMIN_OF_TEAM_SQL), {"uid": user_id, "tid": team_id}).first() is not None


def list_space_ids_where_team_admin(db, user_id: int) -> List[int]:
    rows = db.execute(text(_SPACE_IDS_WHERE_TEAM_ADMIN_SQL), {"uid": user_id}).all()
    return [r[0] for r in rows]


# ---------------- 异步 ----------------

async def is_team_admin_of_team_async(db: AsyncSession, user_id: int, team_id: Optional[int]) -> bool:
    if team_id is None:
        return False
    res = await db.execute(text(_TEAM_ADMIN_OF_TEAM_SQL), {"uid": user_id, "tid": team_id})
    return res.first() is not None


async def list_space_ids_where_team_admin_async(db: AsyncSession, user_id: int) -> List[int]:
    res = await db.execute(text(_SPACE_IDS_WHERE_TEAM_ADMIN_SQL), {"uid": user_id})
    return [row[0] for row in res.all()]
