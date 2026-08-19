from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from models.init_db import get_db, User
from service.dependencies import get_current_user
from service.rag import rag_service
from service import background_task_service
from models.knowledge_dao import list_knowledge_by_agent, update_knowledge_enabled
from models.knowledge_chunk_dao import list_chunks_by_knowledge
from service.access_control import get_owned_agent, get_owned_knowledge

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])

# 允许的文件类型
ALLOWED_TYPES = {"txt", "md", "pdf", "docx"}


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    knowledge_id: Optional[int] = None


class KnowledgeEnabledUpdate(BaseModel):
    is_enabled: int = Field(ge=0, le=1)


def _ensure_agent_owner(db: Session, user_id: int, agent_id: int):
    agent = get_owned_agent(db, user_id, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="智能体不存在或无权限",
        )
    return agent


def _validate_upload_file_name(file_name: str) -> str:
    file_type = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if file_type not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file_type}，支持: {list(ALLOWED_TYPES)}"
        )
    return file_type


def _create_upload_task(
        db: Session,
        background_tasks: BackgroundTasks,
        user_id: int,
        agent_id: int,
        file_name: str,
        content: bytes,
        file_type: str,
):
    knowledge = rag_service.prepare_upload(
        db=db,
        user_id=user_id,
        agent_id=agent_id,
        file_name=file_name,
        file_content=content,
        file_type=file_type,
    )
    task = background_task_service.create_background_task(
        db=db,
        user_id=user_id,
        agent_id=agent_id,
        task_type="knowledge_index",
        title=f"文档入库: {file_name}",
        target_type="knowledge",
        target_id=knowledge.id,
    )
    background_tasks.add_task(
        background_task_service.run_knowledge_index_task,
        task["id"],
        user_id,
        agent_id,
        knowledge.id,
    )
    return {
        "file_name": file_name,
        "knowledge_id": knowledge.id,
        "task_id": task["id"],
        "status": "queued",
    }


@router.post("/{agent_id}/upload", summary="上传文档并入库")
async def upload_document(
        agent_id: int,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)

    # 1. 校验文件类型
    file_name = file.filename
    file_type = _validate_upload_file_name(file_name)

    # 2. 读取文件内容
    content = await file.read()

    # 3. 调用RAG服务上传入库
    try:
        item = _create_upload_task(
            db, background_tasks, current_user.id, agent_id, file_name, content, file_type
        )
        db.commit()
        return {
            "message": "已创建后台入库任务",
            "knowledge_id": item["knowledge_id"],
            "task_id": item["task_id"],
            "status": item["status"],
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"上传失败: {str(e)}")


@router.post("/{agent_id}/upload-batch", summary="批量上传文档并入库")
async def upload_documents(
        agent_id: int,
        background_tasks: BackgroundTasks,
        files: List[UploadFile] = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="请选择至少一个文件")
    if len(files) > 20:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="一次最多上传20个文件")

    created = []
    try:
        for file in files:
            file_name = file.filename
            file_type = _validate_upload_file_name(file_name)
            content = await file.read()
            created.append(_create_upload_task(
                db, background_tasks, current_user.id, agent_id, file_name, content, file_type
            ))
        db.commit()
        return {
            "message": f"已创建{len(created)}个后台入库任务",
            "count": len(created),
            "items": created,
        }
    except HTTPException:
        db.rollback()
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"批量上传失败: {str(e)}")


@router.get("/{agent_id}/list", summary="查看知识库文档列表")
def list_documents(
        agent_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    docs = list_knowledge_by_agent(db, agent_id)
    return [
        {
            "id": d.id,
            "file_name": d.file_name,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "is_enabled": d.is_enabled if d.is_enabled is not None else 1,
            "error_msg": d.error_msg,
            "created_at": d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/{agent_id}/{knowledge_id}", summary="查看知识库文档详情")
def get_document(
        agent_id: int,
        knowledge_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    doc = get_owned_knowledge(db, current_user.id, knowledge_id, agent_id=agent_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在或无权限")
    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "is_enabled": doc.is_enabled if doc.is_enabled is not None else 1,
        "error_msg": doc.error_msg,
        "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M:%S") if doc.created_at else None,
    }


@router.get("/{agent_id}/{knowledge_id}/chunks", summary="查看文档切分片段")
def list_document_chunks(
        agent_id: int,
        knowledge_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    doc = get_owned_knowledge(db, current_user.id, knowledge_id, agent_id=agent_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在或无权限")
    chunks = list_chunks_by_knowledge(db, knowledge_id)
    return {
        "knowledge_id": knowledge_id,
        "count": len(chunks),
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "token_count": c.token_count,
                "vector_id": c.vector_id,
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None,
            }
            for c in chunks
        ],
    }


@router.post("/{agent_id}/search", summary="检索知识库")
def search_knowledge(
        agent_id: int,
        data: KnowledgeSearchRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    query = data.query.strip()
    if not query:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="检索关键词不能为空")
    if data.knowledge_id is not None:
        doc = get_owned_knowledge(db, current_user.id, data.knowledge_id, agent_id=agent_id)
        if not doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在或无权限")
        if doc.is_enabled == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="该文档已禁用，不参与检索")
    try:
        results = rag_service.search(
            db=db,
            user_id=current_user.id,
            agent_id=agent_id,
            query=query,
            top_k=data.top_k,
            knowledge_id=data.knowledge_id,
        )
        return {"query": query, "count": len(results), "top_k": data.top_k, "results": results}
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检索失败: {str(e)}")


@router.patch("/{agent_id}/{knowledge_id}/enabled", summary="启用或禁用知识库文档")
def update_document_enabled(
        agent_id: int,
        knowledge_id: int,
        data: KnowledgeEnabledUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    doc = get_owned_knowledge(db, current_user.id, knowledge_id, agent_id=agent_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在或无权限")
    doc = update_knowledge_enabled(db, doc, data.is_enabled)
    db.commit()
    return {
        "message": "更新成功",
        "knowledge_id": doc.id,
        "is_enabled": doc.is_enabled,
    }


@router.post("/{agent_id}/{knowledge_id}/reindex", summary="重新入库/重建索引")
def reindex_document(
        agent_id: int,
        knowledge_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    doc = get_owned_knowledge(db, current_user.id, knowledge_id, agent_id=agent_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在或无权限")
    try:
        task = background_task_service.create_background_task(
            db=db,
            user_id=current_user.id,
            agent_id=agent_id,
            task_type="knowledge_reindex",
            title=f"重建索引: {doc.file_name}",
            target_type="knowledge",
            target_id=knowledge_id,
        )
        db.commit()
        background_tasks.add_task(
            background_task_service.run_knowledge_reindex_task,
            task["id"],
            current_user.id,
            agent_id,
            knowledge_id,
        )
        return {
            "message": "已创建后台重建任务",
            "knowledge_id": knowledge_id,
            "task_id": task["id"],
            "status": "queued",
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"重新入库失败: {str(e)}")


@router.delete("/{agent_id}/{knowledge_id}", summary="删除知识库文档")
def delete_document(
        agent_id: int,
        knowledge_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    _ensure_agent_owner(db, current_user.id, agent_id)
    knowledge = get_owned_knowledge(db, current_user.id, knowledge_id, agent_id=agent_id)
    if not knowledge:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="文档不存在或无权限")

    try:
        rag_service.delete_knowledge_completely(db, agent_id, knowledge_id)
        db.commit()
        return {"message": "删除成功", "knowledge_id": knowledge_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除失败: {str(e)}")
