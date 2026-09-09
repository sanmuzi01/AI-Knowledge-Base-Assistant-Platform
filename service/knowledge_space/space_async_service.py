"""知识库空间：路由编排层（async）。

对外返回面向普通用户的结构；技术字段（legacy_agent_id / vector_migrated）不下发。
"""

import json
from typing import Any, Dict, List, Optional

from models import knowledge_space_async_dao as dao
from service.access_control import get_owned_space_async
from service.exceptions import InvalidInput, NotFound

PURPOSES = [
    "customer_service", "policy", "product", "sales", "legal", "tech", "research", "other",
]
PURPOSE_LABELS = {
    "customer_service": "客服知识库", "policy": "企业制度知识库", "product": "产品文档知识库",
    "sales": "销售资料知识库", "legal": "合同/法务知识库", "tech": "技术文档知识库",
    "research": "投研资料知识库", "other": "其他",
}


def _tags(raw) -> List[str]:
    if isinstance(raw, list):
        return [str(t).strip()[:40] for t in raw if str(t).strip()][:20]
    return []


def _dump_tags(raw) -> Optional[str]:
    tags = _tags(raw)
    return json.dumps(tags, ensure_ascii=False) if tags else None


def _to_dict(space, stats: Dict[str, int] = None) -> Dict[str, Any]:
    try:
        tags = json.loads(space.tags_json) if space.tags_json else []
    except (TypeError, ValueError):
        tags = []
    d = {
        "id": space.id,
        "name": space.name,
        "description": space.description or "",
        "purpose": space.purpose,
        "purpose_label": PURPOSE_LABELS.get(space.purpose or "", ""),
        "tags": tags,
        "is_enabled": bool(space.is_enabled),
        "status": space.status,
        "doc_count": space.doc_count,
        "chunk_count": space.chunk_count,
        "health_score": space.health_score,
        "last_indexed_at": space.last_indexed_at.strftime("%Y-%m-%d %H:%M:%S") if space.last_indexed_at else None,
        "created_at": space.created_at.strftime("%Y-%m-%d %H:%M:%S") if space.created_at else None,
        "updated_at": space.updated_at.strftime("%Y-%m-%d %H:%M:%S") if space.updated_at else None,
        # 阶段6 预留（前端可先忽略）
        "scope": "personal",
        "my_role": "owner",
    }
    if stats:
        d.update(stats)
    return d


async def list_spaces(db, user_id: int) -> Dict[str, Any]:
    spaces = await dao.list_spaces_by_user_async(db, user_id)
    items = []
    for s in spaces:
        stats = await dao.live_stats_async(db, s.id)
        items.append(_to_dict(s, stats))
    return {
        "items": items,
        "purposes": [{"key": k, "label": PURPOSE_LABELS[k]} for k in PURPOSES],
    }


async def get_space(db, user_id: int, space_id: int) -> Dict[str, Any]:
    space = await get_owned_space_async(db, user_id, space_id)
    if not space:
        raise NotFound("知识库空间不存在或无权限")
    stats = await dao.live_stats_async(db, space_id)
    return _to_dict(space, stats)


def _clean_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name") or "").strip()[:120]
    if not name:
        raise InvalidInput("知识库空间名称不能为空")
    purpose = payload.get("purpose")
    if purpose is not None and purpose not in PURPOSES:
        purpose = "other"
    return {
        "name": name,
        "description": str(payload.get("description") or "").strip()[:500] or None,
        "purpose": purpose,
        "tags_json": _dump_tags(payload.get("tags")),
    }


async def create_space(db, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    fields = _clean_create(payload)
    space = await dao.create_space_async(db, user_id, fields)
    return _to_dict(space, {"doc_count": 0, "chunk_count": 0, "bound_agent_count": 0})


async def update_space(db, user_id: int, space_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
    space = await get_owned_space_async(db, user_id, space_id)
    if not space:
        raise NotFound("知识库空间不存在或无权限")
    fields: Dict[str, Any] = {}
    if "name" in patch and patch["name"] is not None:
        name = str(patch["name"]).strip()[:120]
        if not name:
            raise InvalidInput("名称不能为空")
        fields["name"] = name
    if "description" in patch and patch["description"] is not None:
        fields["description"] = str(patch["description"]).strip()[:500] or None
    if "purpose" in patch and patch["purpose"] is not None:
        fields["purpose"] = patch["purpose"] if patch["purpose"] in PURPOSES else "other"
    if "tags" in patch and patch["tags"] is not None:
        fields["tags_json"] = _dump_tags(patch["tags"])
    if "is_enabled" in patch and patch["is_enabled"] is not None:
        fields["is_enabled"] = 1 if patch["is_enabled"] else 0
    if "status" in patch and patch["status"] in ("active", "archived"):
        fields["status"] = patch["status"]
    if not fields:
        raise InvalidInput("没有需要更新的内容")
    space = await dao.update_space_async(db, space, fields)
    stats = await dao.live_stats_async(db, space_id)
    return _to_dict(space, stats)


async def delete_space(db, user_id: int, space_id: int) -> Dict[str, Any]:
    space = await get_owned_space_async(db, user_id, space_id)
    if not space:
        raise NotFound("知识库空间不存在或无权限")
    stats = await dao.live_stats_async(db, space_id)
    if stats["doc_count"] > 0:
        raise InvalidInput("空间下还有文档，请先清空文档或改为归档")
    await dao.delete_space_async(db, space)
    return {"message": "已删除", "id": space_id}
