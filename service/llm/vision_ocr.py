"""用用户已配置的视觉模型（GLM-4V / GPT-4o 系列）识别扫描件/图片里的文字。

同步版本——文档解析整条流水线（service/rag/rag_service.py）都是同步代码，跑在
后台任务的 worker 线程里，不走 AsyncSession。复用 BaseLLM.chat()：GLMClient /
OpenAICompatibleClient 的 chat() 把 messages 原样塞进请求体，content 字段本来就
没限制必须是字符串，OpenAI 兼容的 image_url content part 直接能用，不需要改任何
客户端代码——这里只是第一次真的传了多模态 content。
"""
from typing import Optional, Tuple

from service.llm.model_catalog import normalize_model_name

# 目前已知支持图片输入的聊天模型。新增供应商的视觉模型时在这里加一行即可。
_VISION_MODELS = {"glm-4v", "gpt-4o", "gpt-4o-mini"}

_OCR_PROMPT = (
    "请识别图片中的所有文字内容，按原文的排版顺序输出。"
    "只输出识别到的文字本身，不要翻译、不要总结、不要添加任何解释或标注。"
    "如果图片里确实没有可识别的文字，只输出：无文字内容"
)


def supports_vision(model_name: str) -> bool:
    return normalize_model_name(model_name) in _VISION_MODELS


def resolve_vision_model(db, user_id: int) -> Optional[Tuple[str, str, Optional[str]]]:
    """在用户已配置的聊天模型里挑一个支持视觉识别的，返回 (model_name, api_key, api_url)。

    没有任何视觉模型时返回 None——调用方（PDF 扫描页解析）应该把这当成
    "OCR 用不了，按原样跳过这页"，而不是让整个文档处理失败。
    """
    from models.llm_config_dao import list_configs_by_user
    from service.llm.llm_config_service import get_api_config

    configs = list_configs_by_user(db, user_id) or []
    for config in configs:
        if not config.is_active or not supports_vision(config.model_name):
            continue
        cfg = get_api_config(db, user_id, config.model_name)
        if cfg and cfg.get("api_key"):
            return cfg["model_name"], cfg["api_key"], cfg.get("api_url")
    return None


def ocr_image(model_name: str, api_key: str, api_url: Optional[str], image_base64: str,
              mime_type: str = "image/png") -> str:
    """调用视觉模型识别一张图片里的文字，返回识别出的纯文本。

    失败直接抛异常——调用方决定怎么兜底（PDF 扫描页：跳过这一页，不影响其它页；
    纯图片上传：整个文档处理失败，因为图片上传的全部意义就是里面的文字）。
    """
    from service.llm.factory import LLMFactory

    client = LLMFactory.create(model_name, api_key=api_key, api_url=api_url)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": _OCR_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
        ],
    }]
    text = (client.chat(messages, temperature=0.1) or "").strip()
    return "" if text == "无文字内容" else text
