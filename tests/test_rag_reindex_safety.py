"""重建索引（reindex_knowledge）的安全性回归测试。

之前的实现是「先删旧向量+旧chunks，再解析/切块/向量化」——解析或向量化失败时
旧数据已经没了，文档变成完全检索不到内容的空文档。现在改成「先把新内容全部
生成好，再删旧写新」，这组测试锁定这个安全属性：新内容生成阶段任何一步失败，
一律不能碰旧数据（不删向量、不删chunk行）。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from service.rag import rag_service


def _fake_knowledge(**overrides):
    defaults = dict(
        id=1, user_id=1, agent_id=1, space_id=None,
        file_path="/tmp/fake.txt", file_type="txt", chunk_size=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class ReindexSafetyTest(unittest.TestCase):
    def setUp(self):
        self.knowledge = _fake_knowledge()
        self._patch("service.rag.rag_service.get_knowledge_by_id", return_value=self.knowledge)
        self._patch("os.path.exists", return_value=True)

        self.mock_parse = self._patch("service.rag.rag_service.parse_document", return_value="有效内容 " * 20)
        self.mock_embed = self._patch("service.rag.rag_service.embed_texts", return_value=[[0.1, 0.2]])
        self.mock_delete_vec = self._patch("service.rag.rag_service.delete_vectors_by_knowledge")
        self.mock_delete_chunks = self._patch("service.rag.rag_service.delete_chunks_by_knowledge")
        self.mock_add_vectors = self._patch("service.rag.rag_service.add_vectors")
        self.mock_create_chunks = self._patch("service.rag.rag_service.create_chunks_batch")
        self.mock_update_status = self._patch("service.rag.rag_service.update_knowledge_status")

    def _patch(self, target, **kwargs):
        patcher = patch(target, **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _assert_old_data_untouched(self):
        self.mock_delete_vec.assert_not_called()
        self.mock_delete_chunks.assert_not_called()
        self.mock_add_vectors.assert_not_called()
        self.mock_create_chunks.assert_not_called()
        self.assertEqual(self.mock_update_status.call_args_list[-1].args[2], "failed")

    def test_happy_path_deletes_old_then_writes_new(self):
        result = rag_service.reindex_knowledge(db=MagicMock(), user_id=1, agent_id=1, knowledge_id=1)

        self.mock_delete_vec.assert_called_once()
        self.mock_delete_chunks.assert_called_once()
        self.mock_add_vectors.assert_called_once()
        self.mock_create_chunks.assert_called_once()
        self.assertEqual(result["message"], "重新入库成功")
        self.assertEqual(self.mock_update_status.call_args_list[-1].args[2], "done")

    def test_parse_failure_never_touches_old_data(self):
        self.mock_parse.return_value = "   "  # 空白内容 → parse 后触发 ValueError

        with self.assertRaises(ValueError):
            rag_service.reindex_knowledge(db=MagicMock(), user_id=1, agent_id=1, knowledge_id=1)

        self._assert_old_data_untouched()

    def test_embedding_failure_never_touches_old_data(self):
        self.mock_embed.side_effect = RuntimeError("embedding API 超限")

        with self.assertRaises(RuntimeError):
            rag_service.reindex_knowledge(db=MagicMock(), user_id=1, agent_id=1, knowledge_id=1)

        self._assert_old_data_untouched()

    def test_chunking_produces_nothing_never_touches_old_data(self):
        # 全是短碎片（<=10 字符会被 split_text 过滤掉），parse 有内容但切完没有有效块
        self.mock_parse.return_value = "短"

        with self.assertRaises(ValueError):
            rag_service.reindex_knowledge(db=MagicMock(), user_id=1, agent_id=1, knowledge_id=1)

        self._assert_old_data_untouched()


if __name__ == "__main__":
    unittest.main()
