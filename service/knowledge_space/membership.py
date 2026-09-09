"""知识库空间的成员/角色解析。

阶段1：只有 owner（space.user_id == 当前用户）。
阶段6：接 space_members(space_id, user_id, role) + 团队/组织，只改这里的实现，
调用方（写操作的 role 校验）不用动。
"""

ROLES = ("owner", "admin", "editor", "viewer")
_WRITE_DOC = {"owner", "admin", "editor"}
_MANAGE_SPACE = {"owner", "admin"}
_DELETE_SPACE = {"owner"}


def resolve_role(user_id: int, space) -> str | None:
    """返回当前用户对该空间的角色；无权返回 None。"""
    if space is None:
        return None
    if getattr(space, "user_id", None) == user_id:
        return "owner"
    # 阶段6：查 space_members
    return None


def can_write_doc(role: str | None) -> bool:
    return role in _WRITE_DOC


def can_manage_space(role: str | None) -> bool:
    return role in _MANAGE_SPACE


def can_delete_space(role: str | None) -> bool:
    return role in _DELETE_SPACE
