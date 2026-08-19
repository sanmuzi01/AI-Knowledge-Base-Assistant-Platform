import requests
import json
from typing import Dict,List,Generator
from service.llm.base import BaseLLM
from utils.logger_handler import get_logger
logger = get_logger("glm_client")

class GLMClient(BaseLLM):
    DEFAULT_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    def __init__(self,api_key,api_url=None,model_name="glm-4"):
        super().__init__(api_key, api_url, model_name)
        self.api_url = api_url or self.DEFAULT_API_URL

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.5) -> str:
        headers = {
        "Authorization": f"Bearer {self.api_key}",   # API Key 认证
        "Content-Type": "application/json"
        }
        payload = {
                "model": self.model_name,      # 模型名：glm-4 / glm-4-flash 等
                "messages": messages,          # 对话历史：system + user + assistant
                "temperature": temperature,    # 创造性：0=保守, 1=天马行空
                "stream": False                # False = 一次性返回
        }
        try:
            logger.info(f"[GLM] 请求: model={self.model_name}, messages={len(messages)}条, temp={temperature}")
            response = requests.post(#向服务器后端发送请求
                self.api_url,
                headers = headers,
                json = payload,
                timeout =60
            )
        # HTTP 状态码异常（4xx/5xx）直接抛
            response.raise_for_status()
        # 解析响应
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"[GLM] 响应成功: {len(content)}字")
            return content
        except requests.exceptions.RequestException as e:
            logger.error(f"[GLM] 请求失败: {e}")
            raise Exception(f"大模型请求失败{e}")
        except(KeyError,IndexError,json.JSONDecodeError) as e:
            logger.error(f"[GLM] 响应解析失败: {e}, 原始响应: {response.text[:500]}")
            raise Exception(f"大模型响应解析失败")

    #流式对话
    def stream_chat(
            self,messages:List[Dict[str,str]],
            temperature:float=0.5) ->Generator[str,None,None]:
        """流式对话：逐字 yield 返回，适用于打字机效果:return: 生成器，每次产出一段文字（可能是字、词或片段）"""
        headers = {
            "Authorization":f"Bearer {self.api_key}",
            "Content-Type": "application/json"
            }
        payload ={
            "model": self.model_name,
            "messages":messages,
            "temperature":temperature,
            "stream":True
        }
        try:
            logger.info(f"[GLM] 流式请求: model={self.model_name}")
            with requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=60
            ) as response:
                response.raise_for_status()
        # SSE 格式：每行以 "data: " 开头，最后一行为 "data: [DONE]"
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip()=="[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices",[{}])[0].get("delta",{})
                            content = delta.get("content","")
                            if content:
                                yield content
                        except json.JSONDecodeError as e:
                            continue
            logger.info("[GLM] 流式响应完成")
        except requests.exceptions.RequestException as e:
            logger.error(f"[GLM] 流式请求失败: {e}")
            raise Exception(f"大模型流式请求失败: {e}")
