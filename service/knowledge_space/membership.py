"""知识库空间的成员/角色解析。

阶段1：只有 owner（space.user_id == 当前用户）。
阶段6：owner 隐含（space.user_id），其余角色查 space_members(space_id, user_id, role)。
调用方拿 role 后用 can_* 判定能不能写。teams/organizations 建了表但暂不参与可见性计算。
"""

ROLES = ("owner", "admin", "editor", "viewer")
ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}

_WRITE_DOC = {"owner", "admin", "editor"}
_MANAGE_SPACE = {"owner", "admin"}
_DELETE_SPACE = {"owner"}
_MANAGE_MEMBERS = {"owner", "admin"}


def resolve_role(user_id: int, space, member_role: str | None = None) -> str | None:
    """当前用户对该空间的角色；无权返回 None。

    member_role 由调用方从 space_members 查出后传入（DAO 隔离，本函数保持纯逻辑）。
    """
    if space is None:
        return None
    if getattr(space, "user_id", None) == user_id:
        return "owner"
    return member_role if member_role in ROLES else None


def at_least(role: str | None, minimum: str) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK.get(minimum, 99)


def can_write_doc(role: str | None) -> bool:
    return role in _WRITE_DOC


def can_manage_space(role: str | None) -> bool:
    return role in _MANAGE_SPACE


def can_delete_space(role: str | None) -> bool:
    return role in _DELETE_SPACE


def can_manage_members(role: str | None) -> bool:
    return role in _MANAGE_MEMBERS
