from abc import ABC, abstractmethod
from typing import Dict,List,Generator,Optional
class BaseLLM(ABC):
    """大模型抽象基类"""
    def __init__(self,api_key:str,api_url:str=None,model_name:str=None):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        # 最近一次 chat()/achat() 调用的用量（{input_tokens, output_tokens, total_tokens}）。
        # chat/achat 本身仍然只返回内容字符串（避免动所有既有调用方），
        # 需要用量的调用方（比如记忆总结）调用后读这个字段。
        self.last_usage: Optional[Dict[str, int]] = None

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.5) -> str:
        """与大模型进行对话，返回生成的内容流"""
        pass
    async def achat(self, messages: List[Dict[str, str]], temperature: float = 0.5,
                    web_search: bool = False) -> str:
        return self.chat(messages, temperature)

    @abstractmethod
    def stream_chat(self,messages:List[Dict[str,str]],temperature:float=0.5)->Generator[str,None,None]:
        """与大模型进行对话，返回生成的内容流（默认调用 chat 方法）"""
        pass
