import json
from typing import Dict, Generator, List

import requests

from service.llm.base import BaseLLM
from utils.logger_handler import get_logger

logger = get_logger("openai_compatible_client")


class OpenAICompatibleClient(BaseLLM):
    """通用 OpenAI-compatible Chat Completions 客户端。"""

    DEFAULT_BASE_URLS = {
        "deepseek": "https://api.deepseek.com/v1",
        "openai": "https://api.openai.com/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "moonshot": "https://api.moonshot.cn/v1",
    }

    def __init__(self, api_key: str, api_url: str = None, model_name: str = None):
        super().__init__(api_key, api_url, model_name)
        self.api_url = self._normalize_chat_url(api_url or self._default_base_url(model_name))

    def _default_base_url(self, model_name: str) -> str:
        model = (model_name or "").lower()
        if model.startswith("deepseek"):
            return self.DEFAULT_BASE_URLS["deepseek"]
        if model.startswith(("gpt", "o1", "o3", "o4")):
            return self.DEFAULT_BASE_URLS["openai"]
        if model.startswith("kimi"):
            return self.DEFAULT_BASE_URLS["moonshot"]
        return self.DEFAULT_BASE_URLS["zhipu"]

    def _normalize_chat_url(self, api_url: str) -> str:
        url = (api_url or "").rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1") or url.endswith("/paas/v4"):
            return f"{url}/chat/completions"
        return f"{url}/chat/completions"

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.5) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        try:
            logger.info(f"[OpenAI-compatible] 请求: model={self.model_name}, url={self.api_url}")
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"] or ""
        except requests.exceptions.RequestException as e:
            detail = getattr(e.response, "text", "")[:500] if getattr(e, "response", None) else str(e)
            logger.error(f"[OpenAI-compatible] 请求失败: {detail}")
            raise Exception(f"大模型请求失败: {detail}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"[OpenAI-compatible] 响应解析失败: {e}")
            raise Exception("大模型响应解析失败")

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
    ) -> Generator[str, None, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        try:
            logger.info(f"[OpenAI-compatible] 流式请求: model={self.model_name}, url={self.api_url}")
            with requests.post(self.api_url, headers=headers, json=payload, stream=True, timeout=60) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content") or ""
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
        except requests.exceptions.RequestException as e:
            detail = getattr(e.response, "text", "")[:500] if getattr(e, "response", None) else str(e)
            logger.error(f"[OpenAI-compatible] 流式请求失败: {detail}")
            raise Exception(f"大模型流式请求失败: {detail}")
