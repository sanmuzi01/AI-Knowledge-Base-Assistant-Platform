from typing import Dict, List


CHAT_MODELS: Dict[str, Dict[str, str]] = {
    "glm-4": {"provider": "zhipu", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions"},
    "glm-4-flash": {"provider": "zhipu", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions"},
    "glm-4-plus": {"provider": "zhipu", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions"},
    "glm-4v": {"provider": "zhipu", "api_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions"},
    "deepseek-chat": {"provider": "deepseek", "api_url": "https://api.deepseek.com"},
    "deepseek-reasoner": {"provider": "deepseek", "api_url": "https://api.deepseek.com"},
    "deepseek-coder": {"provider": "deepseek", "api_url": "https://api.deepseek.com"},
    "gpt-4o": {"provider": "openai", "api_url": "https://api.openai.com/v1"},
    "gpt-4o-mini": {"provider": "openai", "api_url": "https://api.openai.com/v1"},
}

EMBEDDING_MODELS: Dict[str, Dict[str, str]] = {
    "embedding-3": {"provider": "zhipu", "api_url": "https://open.bigmodel.cn/api/paas/v4/embeddings"},
    "embedding-2": {"provider": "zhipu", "api_url": "https://open.bigmodel.cn/api/paas/v4/embeddings"},
    "text-embedding-3-small": {"provider": "openai", "api_url": "https://api.openai.com/v1/embeddings"},
    "text-embedding-3-large": {"provider": "openai", "api_url": "https://api.openai.com/v1/embeddings"},
    "text-embedding-ada-002": {"provider": "openai", "api_url": "https://api.openai.com/v1/embeddings"},
    "BAAI/bge-small-zh-v1.5": {"provider": "local", "api_url": ""},
    "BAAI/bge-base-zh-v1.5": {"provider": "local", "api_url": ""},
    "BAAI/bge-large-zh-v1.5": {"provider": "local", "api_url": ""},
}


def normalize_model_name(model_name: str) -> str:
    value = (model_name or "").strip()
    for known in list(CHAT_MODELS.keys()) + list(EMBEDDING_MODELS.keys()):
        if known.lower() == value.lower():
            return known
    return value


def model_type(model_name: str) -> str:
    name = normalize_model_name(model_name)
    return "embedding" if name in EMBEDDING_MODELS else "chat"


def provider(model_name: str) -> str:
    name = normalize_model_name(model_name)
    meta = EMBEDDING_MODELS.get(name) or CHAT_MODELS.get(name) or {}
    if meta.get("provider"):
        return meta["provider"]
    lowered = name.lower()
    if lowered.startswith("deepseek"):
        return "deepseek"
    if lowered.startswith(("gpt", "o1", "o3", "o4", "text-embedding")):
        return "openai"
    if lowered.startswith("baai/"):
        return "local"
    return "zhipu"


def default_api_url(model_name: str) -> str:
    name = normalize_model_name(model_name)
    meta = EMBEDDING_MODELS.get(name) or CHAT_MODELS.get(name)
    if meta is not None:
        return meta["api_url"]
    if provider(name) == "deepseek":
        return "https://api.deepseek.com"
    if provider(name) == "openai":
        return "https://api.openai.com/v1"
    return "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def supported_models() -> Dict[str, List[Dict[str, str]]]:
    def rows(source: Dict[str, Dict[str, str]], kind: str):
        return [
            {"model_name": name, "provider": meta["provider"], "kind": kind}
            for name, meta in source.items()
        ]

    return {
        "chat": rows(CHAT_MODELS, "chat"),
        "embedding": rows(EMBEDDING_MODELS, "embedding"),
    }
