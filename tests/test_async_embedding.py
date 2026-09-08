import asyncio
import time
import unittest

from service.rag.embedding.base import BaseEmbedding


class SlowEmbedding(BaseEmbedding):
    def embed_texts(self, texts):
        time.sleep(0.01)
        return [[float(len(text))] for text in texts]

    def embed_query(self, query):
        return self.embed_texts([query])[0]

    def get_dimension(self):
        return 1


class AsyncEmbeddingTestCase(unittest.TestCase):
    def test_default_async_methods_delegate_to_sync_implementation(self):
        client = SlowEmbedding(api_key="", model_name="unit")

        async def run():
            texts_result, query_result = await asyncio.gather(
                client.aembed_texts(["abc", "hello"]),
                client.aembed_query("query"),
            )
            return texts_result, query_result

        texts_result, query_result = asyncio.run(run())

        self.assertEqual(texts_result, [[3.0], [5.0]])
        self.assertEqual(query_result, [5.0])


if __name__ == "__main__":
    unittest.main()
