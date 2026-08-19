from pydantic  import Field,BaseModel

from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session
from typing import Optional
from models.init_db import get_db,User
from service.dependencies import get_current_user
from service.llm import llm_config_service
from service.llm.factory import LLMFactory
from service.llm.model_catalog import supported_models as supported_model_catalog

router =APIRouter(prefix="/llm_config", tags=["模型配置"])

class ConfigSave(BaseModel):
    model_name: str = Field(min_length=1,max_length=100)
    api_key: str = Field(min_length=1, max_length=500)
    api_url: Optional[str] = Field(default=None, max_length=500)

@router.get("/list",summary="获取用户的模型配置列表")
def list_configs(
        db : Session = Depends(get_db),
        current_user : User =Depends(get_current_user)
):
    return llm_config_service.list_configs(db, current_user)


@router.get("/supported_models", summary="获取后端支持的聊天模型")
def supported_models(current_user: User = Depends(get_current_user)):
    catalog = supported_model_catalog()
    return {
        "models": [item["model_name"] for item in catalog["chat"] + catalog["embedding"]],
        "chat": catalog["chat"],
        "embedding": catalog["embedding"],
    }
@router.post("",summary="新增或更新模型配置")
def save_config(
        config :ConfigSave,
        db:Session = Depends(get_db),
        current_user : User = Depends(get_current_user)
):
    return llm_config_service.save_config(db, current_user,config.model_name, config.api_key, config.api_url)
@router.delete("/{model_name}",summary="删除模型配置")
def delete_config(
        model_name:str,
        db :Session =Depends(get_db),
        current_user = Depends(get_current_user)
):
    result = llm_config_service.delete_config_by_model(db, current_user, model_name)
    if result["message"] =="配置不存在":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    return result
