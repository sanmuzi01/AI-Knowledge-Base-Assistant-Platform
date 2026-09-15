"""统一的 token 用量提取/归一化。

两套调用栈各自的原始格式不一样：
- LangChain（react_engine 的主循环、工具里注入的 ctx.llm_client）：AIMessage.usage_metadata
  或 response_metadata["token_usage"]，字段名 input_tokens/output_tokens。
- 项目自己的轻量 HTTP 客户端（glm_client/openai_compatible_client，给记忆总结这类
  一次性调用用）：OpenAI 风格响应体里的 usage 字段，字段名 prompt_tokens/completion_tokens。

都归一化成同一个形状：{"input_tokens", "output_tokens", "total_tokens"}，方便汇总。
"""
from typing import Any, Dict, Optional


def extract_usage(response: Any) -> Optional[Dict[str, int]]:
    """从 LangChain 的 AIMessage / AIMessageChunk 提取用量。"""
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        usage = (getattr(response, "response_metadata", None) or {}).get("token_usage")
    if not usage:
        return None
    incoming = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    outgoing = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    total = int(usage.get("total_tokens", incoming + outgoing) or 0)
    return {"input_tokens": incoming, "output_tokens": outgoing, "total_tokens": total}


def from_openai_usage(usage: Optional[Dict[str, Any]]) -> Optional[Dict[str, int]]:
    """从 OpenAI 风格响应体的 `usage` 字段提取用量。"""
    if not usage:
        return None
    incoming = int(usage.get("prompt_tokens", 0) or 0)
    outgoing = int(usage.get("completion_tokens", 0) or 0)
    total = int(usage.get("total_tokens", incoming + outgoing) or 0)
    return {"input_tokens": incoming, "output_tokens": outgoing, "total_tokens": total}
