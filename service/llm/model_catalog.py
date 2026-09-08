from typing import Dict, List

PROVIDER_DEFAULT_API_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "local": "",
}

PROVIDER_PREFIX_RULES = (
    (("deepseek",), "deepseek"),
    (("gpt", "o1", "o3", "o4", "text-embedding"), "openai"),
    (("baai/",), "local"),
)


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
    for prefixes, provider_name in PROVIDER_PREFIX_RULES:
        if lowered.startswith(prefixes):
            return provider_name
    return "zhipu"


def default_api_url(model_name: str) -> str:
    name = normalize_model_name(model_name)
    meta = EMBEDDING_MODELS.get(name) or CHAT_MODELS.get(name)
    if meta is not None:
        return meta["api_url"]
    return PROVIDER_DEFAULT_API_URLS.get(provider(name), PROVIDER_DEFAULT_API_URLS["zhipu"])


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
