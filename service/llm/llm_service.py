from typing import Dict, Generator, List
from service.llm.factory import LLMFactory
from service.llm.llm_config_service import get_api_config
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
        answer = await client.achat(messages, temperature)
        logger.info(f"大模型回复成功: {len(answer)}字")
        return answer
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
