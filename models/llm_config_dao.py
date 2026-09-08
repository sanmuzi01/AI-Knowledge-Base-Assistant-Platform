from typing import Optional,List
from models.init_db import LLMConfig

def get_config_by_user_and_model(db,user_id:int,model_name:str)-> Optional[LLMConfig]:
    """查询用户某个模型的配置"""
    return db.query(LLMConfig).filter(
        LLMConfig.user_id == user_id,
        LLMConfig.model_name == model_name
    ).first()
def list_configs_by_user(db,user_id:int)->Optional[List[LLMConfig]]:
    """查询用户的所有模型配置"""
    return db.query(LLMConfig).filter(
        LLMConfig.user_id == user_id
    ).all()
def create_config(db,user_id:int,model_name:str,api_key: str, api_url: str = None) -> LLMConfig:
    """创建模型配置"""
    config = LLMConfig(
        user_id = user_id,
        model_name = model_name,
        api_key = api_key,
        api_url = api_url,
        is_active =1
    )
    db.add(config)
    db.flush()
    return config

def update_config(db, config: LLMConfig, api_key: str = None, api_url: str = None, is_active: int = None) -> LLMConfig:
    """更新模型配置"""
    if api_key is not None:
        config.api_key = api_key
    if api_url is not None:
        config.api_url = api_url
    if is_active is not None:
        config.is_active = is_active
    db.flush()
    return config

def delete_config(db, config: LLMConfig) -> None:
    """删除模型配置"""
    db.delete(config)
    db.flush()
