"""聊天附件：上传给助手处理，以及下载助手（脚本）生成的文件。

附件的用途是喂给 Skill 脚本，所以脚本沙箱没开时不接受上传。
"""
import mimetypes

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from models.init_db import User
from service import attachment_service, sandbox
from service.dependencies import get_current_user
from service.exceptions import InvalidInput, NotFound

router = APIRouter(prefix="/attachment", tags=["聊天附件"])


@router.get("/status", summary="附件/脚本沙箱是否开启")
def attachment_status(current_user: User = Depends(get_current_user)):
    return {"enabled": sandbox.is_enabled(), "max_bytes": attachment_service.MAX_UPLOAD_BYTES}


@router.post("", summary="上传附件")
def upload_attachment(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    if not sandbox.is_enabled():
        raise InvalidInput("附件依赖 Skill 脚本沙箱，当前未开启，请联系管理员")
    try:
        content = file.file.read(attachment_service.MAX_UPLOAD_BYTES + 1)
        return attachment_service.save(current_user.id, file.filename or "file", content)
    except attachment_service.AttachmentError as e:
        raise InvalidInput(str(e))


@router.get("/{att_id}/download", summary="下载附件或脚本生成的文件")
def download_attachment(att_id: str, current_user: User = Depends(get_current_user)):
    found = attachment_service.resolve(current_user.id, att_id)
    if not found:
        raise NotFound("文件不存在或已过期（文件只保留几天）")
    path, name = found
    return FileResponse(path, filename=name, media_type=mimetypes.guess_type(name)[0] or "application/octet-stream")
