"""GLMClient / OpenAICompatibleClient 的 SSRF 校验回归测试。

审计发现：LLMConfig.api_url（用户在「模型连接」里自填的自定义端点）是这个项目里
唯一一处用户可控的出站 URL，却没有走其它所有同类功能（Webhook、企业接口连接器、
组件 HTTP 数据源）都在用的 web_crawler_service.validate_crawl_url 校验——模型的
回答会把内网/云元数据接口的响应原样"读"给用户，是一条真实的数据泄露通道。
校验放在 __init__ 里而不是每次 chat() 前：这两个客户端在全项目里都是"每次用
都新建一个实例"（LLMFactory.create() 每次调用都建新对象），构造时校验一次
和每次请求前校验，安全性等价，代码量小得多。
"""
import unittest

from service.llm.glm_client import GLMClient
from service.llm.openai_compatible_client import OpenAICompatibleClient


class GLMClientSsrfGuardTest(unittest.TestCase):
    def test_public_url_is_accepted(self):
        client = GLMClient(api_key="k", api_url="https://open.bigmodel.cn/api/paas/v4/chat/completions")
        self.assertTrue(client.api_url.startswith("https://open.bigmodel.cn"))

    def test_default_url_is_accepted(self):
        client = GLMClient(api_key="k")
        self.assertEqual(client.api_url, GLMClient.DEFAULT_API_URL)

    def test_localhost_url_is_rejected(self):
        with self.assertRaises(ValueError):
            GLMClient(api_key="k", api_url="http://localhost:11434/v1/chat/completions")

    def test_cloud_metadata_url_is_rejected(self):
        with self.assertRaises(ValueError):
            GLMClient(api_key="k", api_url="http://169.254.169.254/latest/meta-data/")

    def test_private_ip_is_rejected(self):
        with self.assertRaises(ValueError):
            GLMClient(api_key="k", api_url="http://10.0.0.5/chat/completions")


class OpenAICompatibleClientSsrfGuardTest(unittest.TestCase):
    def test_public_url_is_accepted(self):
        client = OpenAICompatibleClient(api_key="k", api_url="https://api.openai.com/v1", model_name="gpt-4o-mini")
        self.assertTrue(client.api_url.startswith("https://api.openai.com"))
        self.assertTrue(client.api_url.endswith("/chat/completions"))

    def test_default_url_for_known_provider_is_accepted(self):
        client = OpenAICompatibleClient(api_key="k", model_name="deepseek-chat")
        self.assertTrue(client.api_url.startswith("https://api.deepseek.com"))

    def test_localhost_url_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleClient(api_key="k", api_url="http://127.0.0.1:8080/v1", model_name="deepseek-chat")

    def test_link_local_metadata_url_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleClient(api_key="k", api_url="http://169.254.169.254/", model_name="gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
