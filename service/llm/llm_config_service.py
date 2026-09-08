from typing import Dict,Any
from models.llm_config_dao import get_config_by_user_and_model, list_configs_by_user, create_config, update_config, delete_config
from models.llm_config_async_dao import (
    create_config_async,
    delete_config_async,
    get_config_by_user_and_model_async,
    list_configs_by_user_async,
    update_config_async,
)
from utils.crypto import encrypt, decrypt
from utils.cache import config_cache
from service.llm.model_catalog import default_api_url, model_type, normalize_model_name, provider


def invalidate_user_config_cache(user_id: int, model_name: str = None):
    if model_name:
        config_cache.invalidate(("llm_api_config", user_id, model_name))
        config_cache.invalidate(("llm_api_key", user_id, model_name))
    config_cache.invalidate(prefix=("llm_config_list", user_id))
    config_cache.invalidate(("embedding_api_config", user_id))

def list_configs(db,user)->list:
    """获取用户的模型配置列表（api_key 脱敏显示）"""
    def load():
        configs = list_configs_by_user(db, user.id)
        return [
            {
                "id": c.id,
                "model_name": c.model_name,
                "api_key": c.api_key[:10] + "****" if c.api_key else None,
                "api_url": default_api_url(c.model_name),
                "provider": provider(c.model_name),
                "kind": model_type(c.model_name),
                "is_active": c.is_active
            }
            for c in configs
        ]
    return config_cache.get_or_set(("llm_config_list", user.id), load)


async def async_list_configs(db, user) -> list:
    """异步获取用户的模型配置列表（api_key 脱敏显示）。"""

    cached = config_cache.get(("llm_config_list", user.id))
    if cached is not None:
        return cached
    configs = await list_configs_by_user_async(db, user.id)
    rows = [
        {
            "id": c.id,
            "model_name": c.model_name,
            "api_key": c.api_key[:10] + "****" if c.api_key else None,
            "api_url": default_api_url(c.model_name),
            "provider": provider(c.model_name),
            "kind": model_type(c.model_name),
            "is_active": c.is_active
        }
        for c in configs
    ]
    config_cache.set(("llm_config_list", user.id), rows)
    return rows

def save_config(db, user, model_name: str, api_key: str, api_url: str = None) -> Dict[str, Any]:
    """新增或更新模型配置（URL 由后端按模型名自动适配）"""
    model_name = normalize_model_name(model_name)
    api_url = default_api_url(model_name)
    encrypted_key = encrypt(api_key)
    existing = get_config_by_user_and_model(db, user.id, model_name)
    if existing:
        update_config(
            db,existing,api_key = encrypted_key,api_url=api_url,
        )
        db.commit()
        invalidate_user_config_cache(user.id, model_name)
        return {"message": "更新成功", "model_name": model_name}
    create_config(db, user.id, model_name, encrypted_key, api_url)
    db.commit()
    invalidate_user_config_cache(user.id, model_name)
    return  {"message": "配置成功", "model_name": model_name}


async def async_save_config(db, user, model_name: str, api_key: str, api_url: str = None) -> Dict[str, Any]:
    """异步新增或更新模型配置（URL 由后端按模型名自动适配）。"""

    model_name = normalize_model_name(model_name)
    api_url = default_api_url(model_name)
    encrypted_key = encrypt(api_key)
    existing = await get_config_by_user_and_model_async(db, user.id, model_name)
    if existing:
        await update_config_async(db, existing, api_key=encrypted_key, api_url=api_url)
        await db.commit()
        invalidate_user_config_cache(user.id, model_name)
        return {"message": "更新成功", "model_name": model_name}
    await create_config_async(db, user.id, model_name, encrypted_key, api_url)
    await db.commit()
    invalidate_user_config_cache(user.id, model_name)
    return {"message": "配置成功", "model_name": model_name}


def delete_config_by_model(db,user,model_name:str)->Dict[str, Any]:
    """删除模型配置"""
    config = get_config_by_user_and_model(db, user.id, model_name)
    if not config:
        return {"message": "配置不存在"}
    delete_config(db, config)
    db.commit()
    invalidate_user_config_cache(user.id, model_name)
    return {"message": "删除成功", "model_name": model_name}


async def async_delete_config_by_model(db, user, model_name: str) -> Dict[str, Any]:
    """异步删除模型配置。"""

    model_name = normalize_model_name(model_name)
    config = await get_config_by_user_and_model_async(db, user.id, model_name)
    if not config:
        return {"message": "配置不存在"}
    await delete_config_async(db, config)
    await db.commit()
    invalidate_user_config_cache(user.id, model_name)
    return {"message": "删除成功", "model_name": model_name}


def get_api_key(db,user_id:int,model_name:str)->str:
    """获取解密后的 API Key（供 LLM Factory 调用）"""
    def load():
        config = get_config_by_user_and_model(db, user_id, model_name)
        if not config or not config.is_active:
            return None
        return decrypt(config.api_key)
    return config_cache.get_or_set(("llm_api_key", user_id, model_name), load)

def get_api_config(db, user_id: int, model_name: str):
    """获取当前用户某个模型的完整调用配置。"""
    def load():
        config = get_config_by_user_and_model(db, user_id, model_name)
        if not config or not config.is_active:
            return None
        return {
            "model_name": config.model_name,
            "api_key": decrypt(config.api_key),
            "api_url": default_api_url(config.model_name),
        }
    return config_cache.get_or_set(("llm_api_config", user_id, model_name), load)


async def async_get_api_config(db, user_id: int, model_name: str):
    """异步获取当前用户某个模型的完整调用配置。"""

    model_name = normalize_model_name(model_name)
    cached = config_cache.get(("llm_api_config", user_id, model_name))
    if cached is not None:
        return cached
    config = await get_config_by_user_and_model_async(db, user_id, model_name)
    if not config or not config.is_active:
        return None
    payload = {
        "model_name": config.model_name,
        "api_key": decrypt(config.api_key),
        "api_url": default_api_url(config.model_name),
    }
    config_cache.set(("llm_api_config", user_id, model_name), payload)
    return payload


def get_first_embedding_config(db, user_id: int):
    """按优先级查找当前用户可用的向量模型配置。"""
    def load():
        priority = [
            "embedding-3",
            "embedding-2",
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ]
        configs = list_configs_by_user(db, user_id)
        active = {c.model_name: c for c in configs if c.is_active}
        for model_name in priority:
            config = active.get(model_name)
            if config:
                return {
                    "model_name": config.model_name,
                    "api_key": decrypt(config.api_key),
                    "api_url": default_api_url(config.model_name),
                }
        glm_config = active.get("glm-4")
        if glm_config:
            return {
                "model_name": "embedding-3",
                "api_key": decrypt(glm_config.api_key),
                "api_url": default_api_url("embedding-3"),
            }
        return None
    return config_cache.get_or_set(("embedding_api_config", user_id), load)


def test_config(db, user, model_name: str) -> Dict[str, Any]:
    """测试当前用户已保存的模型配置是否可用。"""
    import time

    model_name = normalize_model_name(model_name)
    api_config = get_api_config(db, user.id, model_name)
    if not api_config:
        return {
            "ok": False,
            "model_name": model_name,
            "message": "配置不存在或已停用",
        }

    started = time.time()
    kind = model_type(model_name)
    try:
        if kind == "embedding":
            from service.rag.embedding.factory import EmbeddingFactory

            client = EmbeddingFactory.create(
                model_name=api_config["model_name"],
                api_key=api_config["api_key"],
                api_url=api_config.get("api_url"),
            )
            vector = client.embed_query("连接测试")
            elapsed_ms = int((time.time() - started) * 1000)
            return {
                "ok": True,
                "model_name": model_name,
                "kind": "embedding",
                "message": "向量模型连接正常",
                "elapsed_ms": elapsed_ms,
                "dimension": len(vector),
            }

        from service.llm.factory import LLMFactory

        client = LLMFactory.create(
            model_name=api_config["model_name"],
            api_key=api_config["api_key"],
            api_url=api_config.get("api_url"),
        )
        answer = client.chat([
            {"role": "system", "content": "你只需要用中文简短回复。"},
            {"role": "user", "content": "请回复：连接正常"},
        ], temperature=0)
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "ok": True,
            "model_name": model_name,
            "kind": "chat",
            "message": "聊天模型连接正常",
            "elapsed_ms": elapsed_ms,
            "preview": (answer or "")[:100],
        }
    except Exception as e:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "ok": False,
            "model_name": model_name,
            "kind": kind,
            "message": "连接测试失败",
            "elapsed_ms": elapsed_ms,
            "error": str(e)[:500],
        }


async def async_test_config(db, user, model_name: str) -> Dict[str, Any]:
    """异步测试当前用户已保存的模型配置是否可用。"""

    import time

    model_name = normalize_model_name(model_name)
    api_config = await async_get_api_config(db, user.id, model_name)
    if not api_config:
        return {
            "ok": False,
            "model_name": model_name,
            "message": "配置不存在或已停用",
        }

    started = time.time()
    kind = model_type(model_name)
    try:
        if kind == "embedding":
            from service.rag.embedding.factory import EmbeddingFactory

            client = EmbeddingFactory.create(
                model_name=api_config["model_name"],
                api_key=api_config["api_key"],
                api_url=api_config.get("api_url"),
            )
            vector = await client.aembed_query("连接测试")
            elapsed_ms = int((time.time() - started) * 1000)
            return {
                "ok": True,
                "model_name": model_name,
                "kind": "embedding",
                "message": "向量模型连接正常",
                "elapsed_ms": elapsed_ms,
                "dimension": len(vector),
            }

        from service.llm.factory import LLMFactory

        client = LLMFactory.create(
            model_name=api_config["model_name"],
            api_key=api_config["api_key"],
            api_url=api_config.get("api_url"),
        )
        answer = await client.achat([
            {"role": "system", "content": "你只需要用中文简短回复。"},
            {"role": "user", "content": "请回复：连接正常"},
        ], temperature=0)
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "ok": True,
            "model_name": model_name,
            "kind": "chat",
            "message": "聊天模型连接正常",
            "elapsed_ms": elapsed_ms,
            "preview": (answer or "")[:100],
        }
    except Exception as e:
        elapsed_ms = int((time.time() - started) * 1000)
        return {
            "ok": False,
            "model_name": model_name,
            "kind": kind,
            "message": "连接测试失败",
            "elapsed_ms": elapsed_ms,
            "error": str(e)[:500],
        }
