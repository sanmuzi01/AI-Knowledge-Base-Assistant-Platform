"""知识库空间内的文档管理编排。

读（列表 / facet）走 async；写（上传 / 抓取 / 重建 / 启停 / 删除 / 改元数据）沿用
knowledge_service 的同步 + 后台任务链路。归属：get_owned_space[_async]。
"""

import json
from typing import Any, Dict, List, Optional

from service.exceptions import InvalidInput, NotFound

ALLOWED_TYPES = {"txt", "md", "pdf", "docx"}
_STATUS_LABEL = {"pending": "待处理", "processing": "解析中", "done": "已入库", "failed": "失败"}


def _doc_dict(k) -> Dict[str, Any]:
    try:
        tags = json.loads(k.tags_json) if k.tags_json else []
    except (TypeError, ValueError):
        tags = []
    return {
        "id": k.id,
        "file_name": k.file_name,
        "file_type": k.file_type,
        "file_size": k.file_size,
        "chunk_count": k.chunk_count,
        "status": k.status,
        "status_label": _STATUS_LABEL.get(k.status, k.status),
        "is_enabled": (k.is_enabled if k.is_enabled is not None else 1),
        "error_msg": k.error_msg,
        "category": k.category,
        "tags": tags,
        "version": k.version,
        "source_type": k.source_type or "upload",
        "source_url": k.source_url,
        "created_at": k.created_at.strftime("%Y-%m-%d %H:%M:%S") if k.created_at else None,
        "updated_at": k.updated_at.strftime("%Y-%m-%d %H:%M:%S") if k.updated_at else None,
    }


def _tags_json(raw) -> Optional[str]:
    if not isinstance(raw, list):
        return None
    tags = [str(t).strip()[:40] for t in raw if str(t).strip()][:20]
    return json.dumps(tags, ensure_ascii=False) if tags else None


# ---------------- 读 ----------------

async def list_documents(
        async_db, user_id: int, space_id: int, *,
        category: str = None, tag: str = None, status: str = None, is_enabled: int = None,
) -> Dict[str, Any]:
    from models import knowledge_async_dao as kdao
    from service.access_control import get_owned_space_async

    if await get_owned_space_async(async_db, user_id, space_id) is None:
        raise NotFound("知识库空间不存在或无权限")

    all_docs = await kdao.list_knowledge_by_space_async(async_db, space_id)
    filtered = await kdao.list_knowledge_by_space_async(
        async_db, space_id, category=category, tag=tag, status=status, is_enabled=is_enabled,
    )
    categories = sorted({d.category for d in all_docs if d.category})
    tags_set = set()
    for d in all_docs:
        try:
            tags_set.update(json.loads(d.tags_json) if d.tags_json else [])
        except (TypeError, ValueError):
            pass
    return {
        "items": [_doc_dict(d) for d in filtered],
        "total": len(all_docs),
        "facets": {
            "categories": categories,
            "tags": sorted(tags_set),
            "statuses": [{"key": k, "label": v} for k, v in _STATUS_LABEL.items()],
        },
    }


# ---------------- 写（sync + BackgroundTasks） ----------------

def _owned_space_or_404(db, user_id: int, space_id: int):
    from service.access_control import get_owned_space

    space = get_owned_space(db, user_id, space_id)
    if space is None:
        raise NotFound("知识库空间不存在或无权限")
    return space


def _validate_file(file_name: str) -> str:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in (file_name or "") else ""
    if ext not in ALLOWED_TYPES:
        raise InvalidInput(f"不支持的文件类型: {ext}，支持: {sorted(ALLOWED_TYPES)}")
    return ext


def upload(db, background_tasks, user_id: int, space_id: int, file_name: str, content: bytes,
          *, category: str = None, tags: List[str] = None, version: str = None) -> Dict[str, Any]:
    _owned_space_or_404(db, user_id, space_id)
    file_type = _validate_file(file_name)
    if not content:
        raise InvalidInput("上传文件为空")
    from service import knowledge_service
    return knowledge_service.create_upload_task(
        db, background_tasks, user_id, None, file_name, content, file_type,
        space_id=space_id, category=category, tags_json=_tags_json(tags), version=version,
    )


def upload_batch(db, background_tasks, user_id: int, space_id: int, files: List[Dict]) -> List[Dict]:
    _owned_space_or_404(db, user_id, space_id)
    if not files:
        raise InvalidInput("请选择至少一个文件")
    if len(files) > 20:
        raise InvalidInput("一次最多上传 20 个文件")
    prepared = []
    for f in files:
        _validate_file(f["file_name"])
        if not f.get("content"):
            raise InvalidInput(f"文件为空：{f['file_name']}")
        prepared.append({"file_name": f["file_name"], "content": f["content"],
                         "file_type": f["file_name"].rsplit(".", 1)[-1].lower()})
    from service import knowledge_service
    return knowledge_service.create_upload_tasks(db, background_tasks, user_id, None, prepared, space_id=space_id)


def crawl(db, background_tasks, user_id: int, space_id: int, pages: List[Dict]) -> List[Dict]:
    _owned_space_or_404(db, user_id, space_id)
    from service import knowledge_service
    return knowledge_service.create_crawl_tasks(db, background_tasks, user_id, None, pages, space_id=space_id)


def set_enabled(db, user_id: int, space_id: int, knowledge_id: int, is_enabled: int) -> Dict:
    _owned_space_or_404(db, user_id, space_id)
    from models.knowledge_dao import get_owned_knowledge_in_space
    from service import knowledge_service

    doc = get_owned_knowledge_in_space(db, user_id, space_id, knowledge_id)
    if not doc:
        raise NotFound("文档不存在或无权限")
    return knowledge_service.set_document_enabled(db, doc, is_enabled)


def update_meta(db, user_id: int, space_id: int, knowledge_id: int, *,
                category=None, tags=None, version=None) -> Dict:
    _owned_space_or_404(db, user_id, space_id)
    from models.knowledge_dao import get_owned_knowledge_in_space, update_knowledge_meta

    doc = get_owned_knowledge_in_space(db, user_id, space_id, knowledge_id)
    if not doc:
        raise NotFound("文档不存在或无权限")
    update_knowledge_meta(
        db, doc,
        category=(category if category is not None else None),
        tags_json=(_tags_json(tags) or "" if tags is not None else None),
        version=(version if version is not None else None),
    )
    db.commit()
    return _doc_dict(doc)


def reindex(db, background_tasks, user_id: int, space_id: int, knowledge_id: int) -> Dict:
    _owned_space_or_404(db, user_id, space_id)
    from models.knowledge_dao import get_owned_knowledge_in_space
    from service import knowledge_service

    doc = get_owned_knowledge_in_space(db, user_id, space_id, knowledge_id)
    if not doc:
        raise NotFound("文档不存在或无权限")
    return knowledge_service.create_reindex_task(
        db, background_tasks, user_id, doc.agent_id, knowledge_id, doc.file_name
    )


def delete(db, user_id: int, space_id: int, knowledge_id: int) -> Dict:
    _owned_space_or_404(db, user_id, space_id)
    from models.knowledge_dao import get_owned_knowledge_in_space
    from service import knowledge_service
    from service.knowledge_space.space_service import recount_space

    doc = get_owned_knowledge_in_space(db, user_id, space_id, knowledge_id)
    if not doc:
        raise NotFound("文档不存在或无权限")
    out = knowledge_service.delete_document_completely(db, doc.agent_id, knowledge_id)
    recount_space(db, space_id)
    return out
