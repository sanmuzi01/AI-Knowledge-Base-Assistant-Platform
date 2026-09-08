# Background Worker

后台任务用于执行耗时操作，例如知识库入库和重建索引。生产环境不要让这些任务运行在 FastAPI 请求进程里，否则 PDF 解析、Embedding 或向量库写入会占住 API 进程。

## 推荐生产模式

`.env`:

```env
TASK_EXECUTION_MODE=worker
TASK_WORKER_POLL_SECONDS=2
TASK_RUNNING_TIMEOUT_SECONDS=1800
```

启动 API:

```powershell
npm run backend:dev
```

启动 Worker:

```powershell
npm run backend:worker
```

API 只负责创建 `queued` 任务，Worker 负责领取任务并执行。任务状态会从 `queued` 变为 `running`，执行成功后变为 `finished`，失败后变为 `failed`。

## 开发临时模式

如果本地不想单独启动 Worker，可以临时使用:

```env
TASK_EXECUTION_MODE=fastapi
```

该模式会在请求返回后由 FastAPI `BackgroundTasks` 执行任务，只适合本地开发，不建议生产使用。

## 任务超时恢复

如果 Worker 异常退出，可能留下 `running` 状态任务。Worker 每轮会检查超过 `TASK_RUNNING_TIMEOUT_SECONDS` 的任务，并自动重新排队。

## 当前支持的任务类型

- `knowledge_index`: 文档入库、切块、Embedding、写入向量库
- `knowledge_reindex`: 删除旧索引后重新入库
