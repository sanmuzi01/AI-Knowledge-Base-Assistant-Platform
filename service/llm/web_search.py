"""让「用户已配置的聊天模型」开启联网检索。

多数厂商的联网是同一个 key、请求里加个开关就能用，机制各不相同：
  - 智谱 GLM   : payload.tools = [{"type": "web_search", ...}]
  - 通义千问   : payload.enable_search = true
  - Kimi/月之暗面: payload.tools = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
  - Perplexity : sonar 系列模型本身就是搜索式，无需开关
  - OpenAI     : 同一个 key，但要换成 *-search-preview 模型名
  - DeepSeek / 本地模型: 不支持

这里只描述「怎么开」，实际注入在 GLMClient / OpenAICompatibleClient.achat(web_search=True)。
"""

from typing import Any, Dict, Optional, Tuple

from service.llm.model_catalog import default_api_url, model_type, normalize_model_name, provider

# provider -> 联网检索是否可用（deepseek / local 不在其中即不支持）
_SEARCH_PROVIDERS = {"zhipu", "qwen", "moonshot", "openai", "perplexity"}

# OpenAI：普通模型要换成搜索预览模型名（同一个 key）
_OPENAI_SEARCH_MODEL = {
    "gpt-4o": "gpt-4o-search-preview",
    "gpt-4o-mini": "gpt-4o-mini-search-preview",
}


def supports_web_search(model_name: str) -> bool:
    return provider(model_name) in _SEARCH_PROVIDERS


def web_search_model(model_name: str) -> str:
    """联网检索实际要用的模型名。OpenAI 普通模型 -> 对应的 *-search-preview；其它原样。"""
    name = normalize_model_name(model_name)
    if provider(name) == "openai":
        return _OPENAI_SEARCH_MODEL.get(name, name if name.endswith("-search-preview") else "gpt-4o-mini-search-preview")
    return name


def search_payload_extras(model_name: str) -> Dict[str, Any]:
    """开启联网检索时要并进 chat completions payload 的额外字段。不支持的 provider 返回空。"""
    p = provider(model_name)
    if p == "zhipu":
        return {"tools": [{"type": "web_search",
                           "web_search": {"enable": True, "search_result": True}}]}
    if p == "qwen":
        return {"enable_search": True}
    if p == "moonshot":
        return {"tools": [{"type": "builtin_function",
                           "function": {"name": "$web_search"}}]}
    # perplexity sonar / openai *-search-preview 无需额外字段
    return {}


async def resolve_search_model_async(
    db, user_id: int, preferred: Optional[str] = None,
) -> Optional[Tuple[str, str, Optional[str]]]:
    """在用户已配置的聊天模型里挑一个「能联网」的。

    返回 (实际要用的模型名, api_key, api_url)；用户没有任何支持联网的模型时返回 None。
    key 沿用用户为原模型配的那把（OpenAI 换 *-search-preview 也用同一个 key）。
    """
    from models.llm_config_async_dao import list_configs_by_user_async
    from service.llm.llm_config_service import async_get_api_config

    configs = await list_configs_by_user_async(db, user_id)
    active_chat = [c.model_name for c in configs if c.is_active and model_type(c.model_name) == "chat"]

    ordered = []
    if preferred and preferred in active_chat:
        ordered.append(preferred)
    ordered += [m for m in active_chat if m not in ordered]

    for name in ordered:
        if not supports_web_search(name):
            continue
        cfg = await async_get_api_config(db, user_id, name)
        if not cfg or not cfg.get("api_key"):
            continue
        search_name = web_search_model(name)
        api_url = default_api_url(search_name) or cfg.get("api_url")
        return search_name, cfg["api_key"], api_url
    return None
