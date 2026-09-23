"""知识库上传入库链路（创建资料记录 -> 创建后台任务 -> 调度执行）的回归测试。

真正的解析/切片/Embedding 发生在 service.background_worker 里，属于慢链路，
这里只覆盖 service.knowledge_service 这一层的编排契约：
  - 是否正确调用 rag_service.prepare_upload / background_task_service
  - 事务是否按预期只提交一次（尤其是批量上传场景）
  - 返回给路由层的响应结构是否符合前端约定
和现有测试一致，用 mock 隔离 DAO / rag_service / background_task_service，不连真实数据库。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from service import knowledge_service


class _FakeDb:
    def __init__(self):
        self.commit_count = 0

    def commit(self):
        self.commit_count += 1


def _fake_knowledge(knowledge_id=1, file_name="report.pdf"):
    return SimpleNamespace(id=knowledge_id, file_name=file_name)


def _fake_task(task_id=100, **extra):
    task = {"id": task_id, "task_type": "knowledge_index", "user_id": 1, "agent_id": 1, "target_id": 1}
    task.update(extra)
    return task


class CreateUploadTaskTest(unittest.TestCase):
    def test_creates_single_task_and_commits_once(self):
        db = _FakeDb()
        knowledge = _fake_knowledge()
        task = _fake_task()
        with patch("service.knowledge_service.rag_service.prepare_upload", return_value=knowledge) as mock_prepare, \
             patch("service.knowledge_service.background_task_service.create_background_task", return_value=task) as mock_create_task, \
             patch("service.knowledge_service.background_task_service.schedule_task") as mock_schedule:
            result = knowledge_service.create_upload_task(
                db, background_tasks=None, user_id=1, agent_id=1,
                file_name="report.pdf", content=b"hello", file_type="pdf",
            )

        mock_prepare.assert_called_once()
        _, kw = mock_prepare.call_args
        self.assertEqual(
            {kw["user_id"], kw["file_name"], kw["file_content"], kw["file_type"]},
            {1, "report.pdf", b"hello", "pdf"},
        )
        # 未指定空间时 agent_id 走旧路径（这里 space_id=None）
        self.assertIsNone(kw.get("space_id"))
        self.assertEqual(kw["agent_id"], 1)
        mock_create_task.assert_called_once()
        mock_schedule.assert_called_once_with(task, None)
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(result, {
            "file_name": "report.pdf",
            "knowledge_id": 1,
            "task_id": 100,
            "status": "queued",
        })

    def test_upload_failure_does_not_commit(self):
        db = _FakeDb()
        with patch("service.knowledge_service.rag_service.prepare_upload", side_effect=ValueError("坏文件")):
            with self.assertRaises(ValueError):
                knowledge_service.create_upload_task(
                    db, background_tasks=None, user_id=1, agent_id=1,
                    file_name="broken.pdf", content=b"", file_type="pdf",
                )
        self.assertEqual(db.commit_count, 0)


class CreateUploadTasksBatchTest(unittest.TestCase):
    def test_batch_upload_commits_once_for_all_files(self):
        db = _FakeDb()
        knowledges = [_fake_knowledge(1, "a.txt"), _fake_knowledge(2, "b.txt")]
        tasks = [_fake_task(101), _fake_task(102)]
        files = [
            {"file_name": "a.txt", "content": b"a", "file_type": "txt"},
            {"file_name": "b.txt", "content": b"b", "file_type": "txt"},
        ]
        with patch("service.knowledge_service.rag_service.prepare_upload", side_effect=knowledges), \
             patch("service.knowledge_service.background_task_service.create_background_task", side_effect=tasks), \
             patch("service.knowledge_service.background_task_service.schedule_task") as mock_schedule:
            result = knowledge_service.create_upload_tasks(db, background_tasks=None, user_id=1, agent_id=1, files=files)

        self.assertEqual(db.commit_count, 1, "批量上传应当只提交一次事务，不能一个文件提交一次")
        self.assertEqual(mock_schedule.call_count, 2)
        self.assertEqual([item["task_id"] for item in result], [101, 102])
        self.assertEqual([item["file_name"] for item in result], ["a.txt", "b.txt"])


class ReindexAndLifecycleTest(unittest.TestCase):
    def test_create_reindex_task(self):
        db = _FakeDb()
        task = _fake_task(200, task_type="knowledge_reindex")
        with patch("service.knowledge_service.background_task_service.create_background_task", return_value=task) as mock_create_task, \
             patch("service.knowledge_service.background_task_service.schedule_task") as mock_schedule:
            result = knowledge_service.create_reindex_task(
                db, background_tasks=None, user_id=1, agent_id=1,
                knowledge_id=5, file_name="report.pdf",
            )

        mock_create_task.assert_called_once_with(
            db=db, user_id=1, agent_id=1, task_type="knowledge_reindex",
            title="重建索引: report.pdf", target_type="knowledge", target_id=5,
        )
        mock_schedule.assert_called_once_with(task, None)
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["task_id"], 200)

    def test_set_document_enabled_toggles_and_commits(self):
        db = _FakeDb()
        doc = SimpleNamespace(id=9, is_enabled=0)
        updated = SimpleNamespace(id=9, is_enabled=1)
        with patch("service.knowledge_service.update_knowledge_enabled", return_value=updated) as mock_update:
            result = knowledge_service.set_document_enabled(db, doc, 1)

        mock_update.assert_called_once_with(db, doc, 1)
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(result, {"message": "更新成功", "knowledge_id": 9, "is_enabled": 1})

    def test_delete_document_completely_commits(self):
        db = _FakeDb()
        with patch("service.knowledge_service.rag_service.delete_knowledge_completely") as mock_delete:
            result = knowledge_service.delete_document_completely(db, agent_id=1, knowledge_id=7)

        mock_delete.assert_called_once_with(db, 1, 7)
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(result, {"message": "删除成功", "knowledge_id": 7})


if __name__ == "__main__":
    unittest.main()
