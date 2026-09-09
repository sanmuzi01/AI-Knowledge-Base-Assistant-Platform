"""知识库写操作业务层。

路由层只负责鉴权、限流和 HTTP 异常转换；文档入库、网页入库、
重建索引、启停和删除的事务提交统一放在这里。

兼容两条归属路径：
- 旧：agent_id（Agent 私有库）
- 新：space_id（知识库空间）—— 传 space_id 时，knowledge/task 的 agent_id 记为 NULL，
  向量集合键由 rag_service._vector_key 解析成 space_<id>
"""

from typing import Dict, List

from fastapi import BackgroundTasks

from models.knowledge_dao import clone_knowledge_for_agent, update_knowledge_enabled
from service import background_task_service
from service.rag import rag_service


def create_upload_task(
        db, background_tasks: BackgroundTasks, user_id: int, agent_id,
        file_name: str, content: bytes, file_type: str,
        *, space_id: int = None, category: str = None, tags_json: str = None, version: str = None,
) -> Dict:
    """保存待入库资料并创建索引任务。"""
    item = _prepare_upload_task(
        db, user_id, agent_id, file_name, content, file_type,
        space_id=space_id, category=category, tags_json=tags_json, version=version,
    )
    db.commit()
    background_task_service.schedule_task(item["task"], background_tasks)
    return _task_response(item)


def create_upload_tasks(
        db, background_tasks: BackgroundTasks, user_id: int, agent_id, files: List[Dict],
        *, space_id: int = None,
) -> List[Dict]:
    """批量保存待入库资料并创建索引任务，同一批次统一提交。"""
    items = [
        _prepare_upload_task(
            db, user_id, agent_id, item["file_name"], item["content"], item["file_type"],
            space_id=space_id,
            category=item.get("category"), tags_json=item.get("tags_json"), version=item.get("version"),
        )
        for item in files
    ]
    db.commit()
    for item in items:
        background_task_service.schedule_task(item["task"], background_tasks)
    return [_task_response(item) for item in items]


def create_crawl_tasks(
        db, background_tasks: BackgroundTasks, user_id: int, agent_id, pages: List[Dict],
        *, space_id: int = None,
) -> List[Dict]:
    """把已抓取网页保存为知识库资料，并创建索引任务。"""
    items = []
    for page in pages:
        task_item = _prepare_upload_task(
            db, user_id, agent_id, page["file_name"], page["content"], page["file_type"],
            space_id=space_id, source_type="web", source_url=page.get("url"),
        )
        task_item.update({"url": page["url"], "title": page["title"]})
        items.append(task_item)
    db.commit()
    for item in items:
        background_task_service.schedule_task(item["task"], background_tasks)
    return [_task_response(item) | {"url": item["url"], "title": item["title"]} for item in items]


def import_existing_document(
        db, background_tasks: BackgroundTasks, user_id: int, agent_id: int, source,
) -> Dict:
    """把当前用户已有资料复制到另一个 Agent，并创建重新入库任务。"""
    knowledge = clone_knowledge_for_agent(db, source, agent_id)
    task = background_task_service.create_background_task(
        db=db, user_id=user_id, agent_id=agent_id,
        task_type="knowledge_index", title=f"导入资料: {knowledge.file_name}",
        target_type="knowledge", target_id=knowledge.id,
    )
    db.commit()
    background_task_service.schedule_task(task, background_tasks)
    return {
        "message": "已导入资料并创建后台入库任务",
        "knowledge_id": knowledge.id,
        "source_knowledge_id": source.id,
        "task_id": task["id"],
        "status": "queued",
    }


def set_document_enabled(db, doc, is_enabled: int) -> Dict:
    """启用或禁用知识库文档。"""
    doc = update_knowledge_enabled(db, doc, is_enabled)
    db.commit()
    return {"message": "更新成功", "knowledge_id": doc.id, "is_enabled": doc.is_enabled}


def create_reindex_task(
        db, background_tasks: BackgroundTasks, user_id: int, agent_id, knowledge_id: int, file_name: str,
) -> Dict:
    """为指定文档创建重建索引任务。"""
    task = background_task_service.create_background_task(
        db=db, user_id=user_id, agent_id=agent_id,
        task_type="knowledge_reindex", title=f"重建索引: {file_name}",
        target_type="knowledge", target_id=knowledge_id,
    )
    db.commit()
    background_task_service.schedule_task(task, background_tasks)
    return {
        "message": "已创建后台重建任务",
        "knowledge_id": knowledge_id,
        "task_id": task["id"],
        "status": "queued",
    }


def delete_document_completely(db, agent_id, knowledge_id: int) -> Dict:
    """删除知识库文档、切片和向量数据。agent_id 仅用于旧路径，向量键由文档 space_id 解析。"""
    rag_service.delete_knowledge_completely(db, agent_id, knowledge_id)
    db.commit()
    return {"message": "删除成功", "knowledge_id": knowledge_id}


def _prepare_upload_task(
        db, user_id: int, agent_id, file_name: str, content: bytes, file_type: str,
        *, space_id: int = None, category: str = None, tags_json: str = None,
        version: str = None, source_type: str = "upload", source_url: str = None,
) -> Dict:
    # 走空间路径时 knowledge / task 的 agent_id 记 NULL
    row_agent_id = None if space_id else agent_id
    knowledge = rag_service.prepare_upload(
        db=db, user_id=user_id, agent_id=row_agent_id,
        file_name=file_name, file_content=content, file_type=file_type,
        space_id=space_id, category=category, tags_json=tags_json, version=version,
        source_type=source_type, source_url=source_url,
    )
    task = background_task_service.create_background_task(
        db=db, user_id=user_id, agent_id=row_agent_id,
        task_type="knowledge_index", title=f"文档入库: {file_name}",
        target_type="knowledge", target_id=knowledge.id,
    )
    return {
        "file_name": file_name,
        "knowledge_id": knowledge.id,
        "task_id": task["id"],
        "status": "queued",
        "task": task,
    }


def _task_response(item: Dict) -> Dict:
    return {
        "file_name": item["file_name"],
        "knowledge_id": item["knowledge_id"],
        "task_id": item["task_id"],
        "status": item["status"],
    }
