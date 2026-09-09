from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from models.init_db import User, get_db
from models.async_db import get_async_db
from service.dependencies import get_current_user, get_current_user_async
from service.exceptions import InvalidInput, NotFound
from service import skill_async_service
from service.skill_service import (
    bind_skill,
    create_template,
    delete_template,
    export_skill_package,
    create_skill,
    delete_skill,
    get_template_config,
    import_skill_from_upload,
    install_public_skill,
    list_available_tools,
    list_templates,
    unbind_skill,
    update_agent_skills,
    update_skill,
    update_skill_with_config,
    update_skill_config,
    update_template,
)

router = APIRouter(prefix="/skill", tags=["Skill管理"])

# 迁移边界：读接口（我的/公开/单个 Skill、校验、Agent 绑定列表）已全量 AsyncSession，
# 不再保留「未装 asyncmy 回退同步」的死分支（asyncmy 已是硬依赖）。
# 创建 / 绑定 / 导入导出 / 安装公共 Skill 仍用同步 get_db —— skill_service / skills_core
# 里混了文件系统操作（写 SKILL.md、打包 zip）和同步 ORM，FastAPI 会把 def 端点放线程池。
# 待 skills_core 迁到 AsyncSession 后再统一收口，见 docs/sync-async-boundary.md。


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    template_filename: str = ""
    is_public: int = 0
    system_prompt: str = ""
    tool_names: List[str] = Field(default_factory=list)
    permissions: Dict[str, Any] = Field(default_factory=dict)


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    template_filename: Optional[str] = None
    is_public: Optional[int] = None
    system_prompt: Optional[str] = None
    tool_names: Optional[List[str]] = None
    permissions: Optional[Dict[str, Any]] = None


class SkillTemplateSave(BaseModel):
    name: str
    description: str = ""
    system_prompt: str
    tool_names: List[str] = Field(default_factory=list)


@router.post("/", summary="创建Skill")
def api_create_skill(
    data: SkillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = create_skill(
        db=db,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        template_filename=data.template_filename,
        is_public=data.is_public,
        system_prompt=data.system_prompt,
        tool_names=data.tool_names,
        permissions=data.permissions,
    )
    if not skill:
        raise InvalidInput("创建Skill失败，请检查模板文件名是否正确")
    return {"code": 200, "msg": "创建成功", "data": skill}


@router.get("/", summary="查询当前用户的所有Skill")
async def api_list_my_skills(
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    skills = await skill_async_service.list_user_skills(async_db, current_user.id)
    return {"code": 200, "msg": "查询成功", "data": skills}


@router.get("/public", summary="查询所有公开Skill")
async def api_list_public_skills(
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    skills = await skill_async_service.list_public_skills(async_db)
    return {"code": 200, "msg": "查询成功", "data": skills}


@router.get("/templates", summary="列出可用YML模板")
def api_list_templates(
    current_user: User = Depends(get_current_user),
):
    templates = list_templates(current_user.id)
    return {"code": 200, "msg": "查询成功", "data": templates}


@router.post("/templates", summary="创建用户Skill模板")
def api_create_template(
    data: SkillTemplateSave,
    current_user: User = Depends(get_current_user),
):
    template = create_template(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        tool_names=data.tool_names,
    )
    if not template:
        raise InvalidInput("创建模板失败，请检查工具和指令")
    return {"code": 200, "msg": "创建成功", "data": template}


@router.get("/templates/{template_filename:path}", summary="查询Skill模板详情")
def api_get_template(
    template_filename: str,
    current_user: User = Depends(get_current_user),
):
    template = get_template_config(template_filename, user_id=current_user.id)
    if not template:
        raise NotFound("模板不存在")
    return {"code": 200, "msg": "查询成功", "data": template}


@router.put("/templates/{template_filename:path}", summary="更新用户Skill模板")
def api_update_template(
    template_filename: str,
    data: SkillTemplateSave,
    current_user: User = Depends(get_current_user),
):
    template = update_template(
        user_id=current_user.id,
        template_filename=template_filename,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        tool_names=data.tool_names,
    )
    if not template:
        raise InvalidInput("更新模板失败，只能修改自己的模板")
    return {"code": 200, "msg": "更新成功", "data": template}


@router.delete("/templates/{template_filename:path}", summary="删除用户Skill模板")
def api_delete_template(
    template_filename: str,
    current_user: User = Depends(get_current_user),
):
    success = delete_template(current_user.id, template_filename)
    if not success:
        raise InvalidInput("删除模板失败，只能删除自己的模板")
    return {"code": 200, "msg": "删除成功"}


@router.get("/tools", summary="列出可用于Skill的工具")
def api_list_tools(
    current_user: User = Depends(get_current_user),
):
    tools = list_available_tools()
    return {"code": 200, "msg": "查询成功", "data": tools}


@router.get("/{skill_id}/validate", summary="校验Skill是否可用")
async def api_validate_skill(
    skill_id: int,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    result = await skill_async_service.validate_skill(async_db, skill_id, user_id=current_user.id)
    if not result:
        raise NotFound("Skill不存在")
    return {"code": 200, "msg": "校验完成", "data": result}


@router.get("/{skill_id}/export", summary="导出Skill包")
def api_export_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        package = export_skill_package(db, skill_id, user_id=current_user.id)
    except ValueError as e:
        raise InvalidInput(str(e))
    if not package:
        raise NotFound("Skill不存在")
    return FileResponse(
        package["path"],
        filename=package["filename"],
        media_type="application/zip",
    )


@router.post("/{skill_id}/install", summary="安装公开Skill到我的能力库")
def api_install_public_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = install_public_skill(db, current_user.id, skill_id)
    if not skill:
        raise InvalidInput("安装失败：Skill不存在或不是公开能力")
    return {"code": 200, "msg": "安装成功", "data": skill}


@router.post("/import", summary="导入外部Skill包")
async def api_import_skill(
    file: UploadFile = File(...),
    is_public: int = Form(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    if not content:
        raise InvalidInput("上传文件为空")

    skill = import_skill_from_upload(
        db=db,
        user_id=current_user.id,
        filename=file.filename or "skill.zip",
        content=content,
        is_public=is_public,
    )
    if not skill:
        raise InvalidInput("导入失败：请上传 .zip Skill包，或符合格式的 .yml/.yaml 文件")
    return {"code": 200, "msg": "导入成功", "data": skill}


@router.get("/{skill_id}", summary="查询单个Skill详情")
async def api_get_skill(
    skill_id: int,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    skill = await skill_async_service.get_skill_with_config(async_db, skill_id, user_id=current_user.id)
    if not skill:
        raise NotFound("Skill不存在")
    return {"code": 200, "msg": "查询成功", "data": skill}


@router.put("/{skill_id}", summary="更新Skill")
def api_update_skill(
    skill_id: int,
    data: SkillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = data.model_dump(exclude_none=True)
    config_payload = {}
    for key in ("system_prompt", "tool_names", "permissions"):
        if key in payload:
            config_payload[key] = payload.pop(key)
    skill = update_skill_with_config(
        db,
        skill_id,
        user_id=current_user.id,
        fields=payload,
        config_fields=config_payload,
    )
    if not skill:
        raise InvalidInput("更新失败，Skill不存在、模板文件名错误或配置不可用")
    return {"code": 200, "msg": "更新成功", "data": skill}


@router.delete("/{skill_id}", summary="删除Skill")
def api_delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = delete_skill(db, skill_id, user_id=current_user.id)
    if not success:
        raise NotFound("Skill不存在")
    return {"code": 200, "msg": "删除成功"}


@router.post("/agent/{agent_id}/bind/{skill_id}", summary="绑定Skill到Agent")
def api_bind_skill(
    agent_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = bind_skill(db, agent_id, skill_id, user_id=current_user.id)
    if not success:
        raise InvalidInput("绑定失败，请检查Agent和Skill是否存在且有权限")
    return {"code": 200, "msg": "绑定成功"}


@router.delete("/agent/{agent_id}/unbind/{skill_id}", summary="解绑Skill")
def api_unbind_skill(
    agent_id: int,
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = unbind_skill(db, agent_id, skill_id, user_id=current_user.id)
    if not success:
        raise InvalidInput("解绑失败")
    return {"code": 200, "msg": "解绑成功"}


@router.get("/agent/{agent_id}", summary="查询Agent绑定的所有Skill")
async def api_list_agent_skills(
    agent_id: int,
    async_db=Depends(get_async_db),
    current_user: User = Depends(get_current_user_async),
):
    skills = await skill_async_service.list_agent_skills(async_db, agent_id, user_id=current_user.id)
    return {"code": 200, "msg": "查询成功", "data": skills}


@router.put("/agent/{agent_id}", summary="批量更新Agent绑定的Skill")
def api_update_agent_skills(
    agent_id: int,
    skill_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = update_agent_skills(db, agent_id, skill_ids, user_id=current_user.id)
    if not success:
        raise InvalidInput("更新失败")
    return {"code": 200, "msg": "更新成功"}
