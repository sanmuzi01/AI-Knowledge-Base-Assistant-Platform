# 同步 / 异步边界

本项目正从「同步 SQLAlchemy」向「异步 SQLAlchemy（asyncmy）」迁移，目前是混合状态。
这份文档记录**当前边界**和**剩余计划**，避免继续往里加随手的同步旁路。

`asyncmy` 是硬依赖：`requirements.txt` 固定 `asyncmy==0.2.10`，`models/async_db.py` 缺驱动会
直接 `raise` 启动失败。因此不存在「未装 asyncmy 时回退同步」的运行时分支。

## 已收口

### 组件平台 `service/widgets/**`
- runner / scheduler / 所有 connector.fetch / processor 一律 `async`，只接受 `AsyncSession`（`ctx.db`）。
- 禁止 `SessionLocal(` / `get_db` / 同步 `requests`，由 `tests/test_widget_sync_boundary.py` 守卫。
- 跨到同步子系统只经 `asyncio.to_thread` 调它们的单一入口：
  - RAG 检索 → `service/rag/search_entry.py::search_scoped`（自带同步 Session + 归属校验；
    `search_for_widget` 是它的薄封装）
  - 网页抓取 → `service/web_crawler_service.py::crawl_url_to_markdown`
- 后台 Worker 用**进程内常驻事件循环**跑组件调度 tick，不再每轮 `asyncio.run()` 建/拆 loop。

### 路由层读接口
knowledge / agent / skill_route 的纯读接口已全量 `get_async_db` + `*_async_service`，
删掉了历史遗留的「异步双轨」死分支（`if async_db is not None: ... else: <同步>`）与随之无用的
同步 DAO import；`models/async_db.py` 的 `get_optional_async_db` 别名已删除。
conversation / agent_run / memory / web_monitor / background_task 路由早已全量 async。

### 知识库检索
`service/rag/search_entry.py::search_scoped`（同步，自带 Session + agent/文档归属 + 启用校验）
封在 `asyncio.to_thread` 里；`FasdtApi/knowledge.py::search_knowledge` 是 `async def` 且不再持有
同步 Session。`PermissionError → NotFound`、`ValueError → InvalidInput`。

### 领域异常
`service/exceptions.py`（`AppError` + `InvalidInput` / `NotFound` / `PermissionDenied` /
`Conflict` / `RateLimited` / `UpstreamError`）+ `FasdtApi/main.py` 统一处理器：按
`[code] METHOD PATH -> msg` 记一行日志（<500 warning / ≥500 error），返回体带 `code` 字段。
`FasdtApi/*.py` 里所有 `raise HTTPException(4xx)` 已换成领域异常（`grep 'HTTPException(status.HTTP_4' FasdtApi` 为空），
仅保留 `_limit_error`（429 + `Retry-After` 头）与少数 500 兜底。

回归由 `tests/test_routes_isolation.py` 兜底（TestClient + 真实 JWT + 真实 DB，
覆盖 widgets / knowledge / agent / skill / conversation / task 的跨用户 404、管理员 403、
同步 def 端点也走统一处理器）。

## 仍未收口

| 位置 | 现状 | 备注 |
| --- | --- | --- |
| `rag_service.async_search` / `_build_search_results` | 半异步：向量化 async，ChromaDB + DAO 反查 + rerank 同步 | `rag_eval_service`、`agent_runtime` 仍在用，直接传同步 `db` |
| 知识库上传 / 入库 / 重建 / 诊断 | `async def` 端点 + 同步 `knowledge_service` + 后台任务 | 重活在同步 Worker，端点只做 ownership + 建任务行 |
| `agent_runtime`（聊天 ReAct 执行） | `chat_service.chat_with_agent` 是 `async def` 但全程同步 `db`：建会话 / 存消息 / 工具执行 / 记忆 | 最大的一块，需先出迁移设计 |
| 任务 Worker 主体 | 同步循环（`service/background_worker.py::run_once`） | 组件调度 tick 已是常驻 async loop |
| service 层内部 `raise ValueError` 等 | 路由层已在 `except` 里翻译成领域异常 | 可随各模块迁移逐步替换为直接抛领域异常 |

## 剩余计划

1. **`agent_runtime` async 化**：独立课题。先出分阶段、可回滚的迁移设计（runtime → 工具执行 →
   `conv_service` / `conv_dao` → 记忆），每层配集成测试，全程保证聊天可用。
2. **RAG 检索彻底 async**：`embedding_service._get_client` / 知识 chunk 反查改异步 DAO，
   ChromaDB / rerank 仍同步但统一封 `to_thread`；届时 `async_search` 可退役。
3. **写入链路 / Worker**：收益低、风险高，除非有明确性能需求，长期保持同步。
