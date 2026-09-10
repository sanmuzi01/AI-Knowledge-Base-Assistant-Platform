from abc import ABC, abstractmethod
from typing import Dict,List,Generator
class BaseLLM(ABC):
    """大模型抽象基类"""
    def __init__(self,api_key:str,api_url:str=None,model_name:str=None):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name

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
