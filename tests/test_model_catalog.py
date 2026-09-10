import unittest

from service.llm.model_catalog import default_api_url, provider


class ModelCatalogTest(unittest.TestCase):
    def test_provider_inference(self):
        self.assertEqual(provider("deepseek-chat"), "deepseek")
        self.assertEqual(provider("gpt-4o-mini"), "openai")
        self.assertEqual(provider("BAAI/bge-small-zh-v1.5"), "local")
        self.assertEqual(provider("glm-4"), "zhipu")

    def test_default_api_url(self):
        self.assertEqual(default_api_url("deepseek-chat"), "https://api.deepseek.com/v1")
        self.assertEqual(default_api_url("gpt-4o-mini"), "https://api.openai.com/v1")
        self.assertEqual(default_api_url("BAAI/bge-small-zh-v1.5"), "")


if __name__ == "__main__":
    unittest.main()
