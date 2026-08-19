from typing import Dict, Optional

from langchain_openai import ChatOpenAI

from service.llm.llm_config_service import get_api_config
from utils.logger_handler import get_logger

logger = get_logger("llm_adapter")

PROVIDER_BASE_URLS = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "deepseek": "https://api.deepseek.com/v1",
    "openai": None,
    "moonshot": "https://api.moonshot.cn/v1",
}

MODEL_PROVIDER_REGISTRY = {
    "glm": "zhipu",
    "deepseek": "deepseek",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "kimi": "moonshot",
}


def _detect_provider(model_name: str) -> str:
    model = model_name.lower()
    for prefix, provider in MODEL_PROVIDER_REGISTRY.items():
        if model.startswith(prefix):
            return provider
    return "zhipu"


def create_langchain_llm(
    db,
    user_id: int,
    model_name: str,
    temperature: float = 0.7,
    api_url: Optional[str] = None,
) -> ChatOpenAI:
    """创建支持用户隔离配置的 OpenAI-compatible LangChain LLM。"""
    api_config = get_api_config(db, user_id, model_name)
    if not api_config:
        raise ValueError(f"请先在【模型配置】中配置 {model_name} 的 API Key")

    provider = _detect_provider(model_name)
    base_url = api_url or api_config.get("api_url") or PROVIDER_BASE_URLS.get(provider)
    llm_kwargs = {
        "model": model_name,
        "api_key": api_config["api_key"],
        "temperature": temperature,
    }
    if base_url:
        llm_kwargs["base_url"] = base_url
    logger.info(f"创建 LangChain LLM: model={model_name}, provider={provider}, base_url={base_url or 'default'}")
    return ChatOpenAI(**llm_kwargs)


def get_provider_info(model_name: str) -> Dict[str, str]:
    provider = _detect_provider(model_name)
    return {
        "model_name": model_name,
        "provider": provider,
        "base_url": PROVIDER_BASE_URLS.get(provider, "default"),
    }
