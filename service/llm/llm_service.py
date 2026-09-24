from typing import Dict, Generator, List, Optional, Tuple
from service.llm.factory import LLMFactory
from service.llm.llm_config_service import async_get_api_config, get_api_config
from utils.logger_handler import get_logger

logger = get_logger("llm_service")


def chat(
    db,
    user_id: int,
    model_name: str,
    system_prompt: str,
    history: List[Dict[str, str]],
    user_message: str,
    temperature: float = 0.5,
) -> str:
    """完整的大模型调用链路：取配置 -> 建Client -> 组装messages -> 调用。"""
    api_config = get_api_config(db, user_id, model_name)
    if not api_config:
        logger.warning(f"用户 {user_id} 未配置模型 {model_name} 的 API Key")
        raise ValueError(f"请先在【模型配置】中配置 {model_name} 的 API Key")

    client = LLMFactory.create(model_name, api_config["api_key"], api_config.get("api_url"))
    logger.info(f"用户 {user_id} 调用 {model_name}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        answer = client.chat(messages, temperature)
        logger.info(f"大模型回复成功: {len(answer)}字")
        return answer
    except Exception as e:
        logger.error(f"大模型调用失败: {e}")
        raise
async def async_chat(
    db,
    user_id: int,
    model_name: str,
    system_prompt: str,
    history: List[Dict[str, str]],
    user_message: str,
    temperature: float = 0.5,
)->str:
    """完整的大模型调用链路：取配置 -> 建Client -> 组装messages -> 调用。

    `db` 是 AsyncSession——所有现存调用方（memory_async_service、rag_eval_service、
    rag/debug_service）传的都是 AsyncSession，之前这里却调同步 `get_api_config`（内部
    `db.query(...)`，AsyncSession 没有这个方法）：只要 `config_cache` 缓存未命中就会
    直接 `AttributeError` 崩掉——不是理论风险，是真实存在过的 bug，改成
    `async_get_api_config` 才是名副其实的"async"。
    """
    api_config = await async_get_api_config(db, user_id, model_name)
    if not api_config:
        logger.warning(f"用户 {user_id} 未配置模型 {model_name} 的 API Key")
        raise ValueError(f"请先在【模型配置】中配置 {model_name} 的 API Key")

    client = LLMFactory.create(model_name, api_config["api_key"], api_config.get("api_url"))
    logger.info(f"用户 {user_id} 调用 {model_name}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        answer = await client.achat(messages, temperature)
        logger.info(f"大模型回复成功: {len(answer)}字")
        return answer
    except Exception as e:
        logger.error(f"大模型调用失败: {e}")
        raise


async def async_chat_with_usage(
    db,
    user_id: int,
    model_name: str,
    system_prompt: str,
    history: List[Dict[str, str]],
    user_message: str,
    temperature: float = 0.5,
) -> Tuple[str, Optional[Dict[str, int]]]:
    """和 async_chat 一样，多返回一份本次调用的 token 用量（拿不到就是 None）。

    给会被计入「一次 Agent 运行总花费」的调用方用（目前是记忆总结）；
    普通只要内容的调用方继续用 async_chat 就行，不用改。

    `db` 是 AsyncSession，原因同 async_chat 的说明——这里以前也是同一个 bug。
    """
    api_config = await async_get_api_config(db, user_id, model_name)
    if not api_config:
        logger.warning(f"用户 {user_id} 未配置模型 {model_name} 的 API Key")
        raise ValueError(f"请先在【模型配置】中配置 {model_name} 的 API Key")

    client = LLMFactory.create(model_name, api_config["api_key"], api_config.get("api_url"))
    logger.info(f"用户 {user_id} 调用 {model_name}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        answer = await client.achat(messages, temperature)
        logger.info(f"大模型回复成功: {len(answer)}字")
        return answer, getattr(client, "last_usage", None)
    except Exception as e:
        logger.error(f"大模型调用失败: {e}")
        raise

def stream_chat(
    db,
    user_id: int,
    model_name: str,
    system_prompt: str,
    history: List[Dict[str, str]],
    user_message: str,
    temperature: float = 0.5,
) -> Generator[str, None, None]:
    api_config = get_api_config(db, user_id, model_name)
    if not api_config:
        logger.warning(f"用户 {user_id} 未配置模型 {model_name} 的 API Key")
        raise ValueError(f"请先在【模型配置】中配置 {model_name} 的 API Key")

    client = LLMFactory.create(model_name, api_config["api_key"], api_config.get("api_url"))
    logger.info(f"用户 {user_id} 调用 {model_name}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        for token in client.stream_chat(messages, temperature):
            yield token
    except Exception as e:
        logger.error(f"大模型流式调用失败: {e}")
        raise
