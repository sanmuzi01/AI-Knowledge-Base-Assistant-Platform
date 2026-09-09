# `agent_runtime` 异步迁移设计

聊天执行（ReAct 循环）是目前最大的一块同步代码。这份文档给出**分阶段、可回滚**的迁移
方案，目标：`chat` / `chat_stream` 路由处理器不再持有同步 `Session`，整条执行链走 `AsyncSession`；
过程中聊天功能始终可用。

> 前置阅读：`docs/sync-async-boundary.md`。

## 1. 现状盘点

### 调用链

```
FasdtApi/chat.py
  POST /chat/{agent_id}          -> chat_service.chat_with_agent            (async def, 同步 db)
  POST /chat/{agent_id}/stream   -> chat_service.chat_with_agent_stream     (sync Generator, 同步 db)
        |
        v
service/chat_service.py
  - get_owned_agent / get_owned_conversation      (同步 DAO)
  - conv_service.save_message / load_history_for_llm / maybe_update_title  (同步, 内部 commit)
  - agent_runtime.run_with_history / run_stream_with_history
        |
        v
service/runtime/agent_runtime.py   (843 行, 4 个入口)
  run() / run_stream() / run_with_history() / run_stream_with_history()
  - create_run / create_step / update_run_status   (agent_run_dao, 同步)
  - db.query(AgentRun) / db.commit() / db.rollback() / db.flush()   (循环里散落 ~30 处)
  - _compose_system_prompt: build_prompt + load_memory + format_user_profile_for_prompt
  - RAG: rag_service.search / async_search          (同步 / 半异步)
  - ToolExecutor.execute(...)                       (工具内部可能碰 db / 外呼)
  - memory_service.should_summarize / summarize_and_save   (同步, 内部 commit + LLM 调用)
  - LLM 客户端 achat / stream_chat
```

### 关键难点

1. **4 个入口重复**：`run` / `run_stream` 是旧 Chat 表路径，`*_with_history` 是当前 Message 表路径。
   旧路径（`run` / `run_stream`）是否还有调用方？迁移前先确认，能删就删，少迁一半。
2. **散落的事务控制**：ReAct 循环里每步 `db.flush()`，工具调用后 `db.commit()`，异常 `db.rollback()`，
   收尾再 `db.commit()`。要逐处换成 `await db.flush()` / `await db.commit()`。
3. **流式 = 同步生成器**：`run_stream_with_history` 是 `Generator[str]`，`chat.py` 用
   `StreamingResponse(sync_gen)`。异步化后要变成 `AsyncGenerator[str]` +
   `StreamingResponse(async_gen)`，且生成器内部的 `await` 不能持有跨 `yield` 的事务。
4. **下游同步服务**：`conv_service`、`memory_service`、`ToolExecutor`、`prompt_manager` 都要有
   async 版本或线程封装。`memory_service.summarize_and_save` 自己 `commit` 且调 LLM——最麻烦。
5. **工具执行**：`ToolExecutor` 跑用户配置的工具，部分工具查 db（如知识库检索工具）。
   工具接口是同步的，短期用 `asyncio.to_thread` 封装单次 `execute`，长期再定 async 工具协议。

## 2. 分阶段方案

每个阶段独立可发布、可回滚，做完跑全量单测 + `tests/test_routes_isolation.py` +（手动）真机聊天冒烟。

### 阶段 0：清障

- ✅ `run()` / `run_stream()`（旧 Chat 表路径）已确认无调用方并删除（`agent_runtime.py` 843 → 483 行），
  连同不再使用的 `from models.chat_dao import create_chat, list_chats_by_agent`。当前只剩
  `run_with_history` / `run_stream_with_history` 两个入口。
- ⏳ 把「查 AgentRun 收尾」那段重复代码（两个入口各一处 `db.query(AgentRun).filter(...).first()`）
  抽成 `_finalize_run(db, run_id, status, ...)` helper，为后面单点改造。
- ⏳ 给 `chat_service` / `agent_runtime` 现有行为补**集成测试**（真实 DB，mock LLM 客户端）：
  一轮不带工具的对话、一轮带一次工具调用、RAG on、memory on。作为迁移回归基线。

### 阶段 1：DAO / 下游服务的 async 版本（2~3 天）

不动 `agent_runtime`，先把它依赖的东西补出 async 双胞胎：

| 同步 | 新增 async | 说明 |
| --- | --- | --- |
| `models/agent_run_dao.py` `create_run` / `create_step` / `update_run_status` | `*_async` | 纯 INSERT/UPDATE，直接翻译 |
| `service/conversation_service.py` `save_message` / `load_history_for_llm` / `maybe_update_title_by_first_message` | `*_async`（复用已有 `conversation_async_service`） | 已部分有 async 版，补齐缺的 |
| `service/memory/memory_service.py` `load_memory` / `should_summarize` | `*_async` | 只读，翻译 DAO 调用 |
| `service/memory/memory_service.py` `summarize_and_save` | `summarize_and_save_async` | 内部 LLM 调用改 `await client.achat`；`commit` 改 `await db.commit()` |
| `service/user_profile_service.py` `format_user_profile_for_prompt` | `*_async` | 只读 |
| `prompt.prompt_manager.build_prompt` | 不变（读文件，无 db） | 保持同步 |

每个 async 版补单测（对照同步版输出一致）。此阶段**不改任何路由行为**。

### 阶段 2：非流式 `run_with_history` 异步化（2 天）

- 复制 `run_with_history` → `run_with_history_async(db: AsyncSession, ...)`：
  - 所有 `db.flush()` / `db.commit()` / `db.rollback()` → `await ...`
  - `db.query(AgentRun).filter(...)` → `await db.execute(select(AgentRun).where(...))`
  - `create_run` 等 → 阶段 1 的 `*_async`
  - `_compose_system_prompt` → `_compose_system_prompt_async`（memory / profile 走 async）
  - RAG：调 `service/rag/search_entry.py::search_scoped` 经 `asyncio.to_thread`（已有模式），
    去掉对 `rag_service.async_search(db=同步)` 的依赖
  - `ToolExecutor.execute(...)` → `await asyncio.to_thread(executor.execute, ...)`（单次工具调用整体入线程）
  - `memory_service.summarize_and_save` → `summarize_and_save_async`
- `chat_service.chat_with_agent` 改 `db: AsyncSession`（`get_async_db`），ownership / 会话 / 存消息
  全走 async；调 `run_with_history_async`。
- `FasdtApi/chat.py::chat` 处理器把 `Depends(get_db)` → `Depends(get_async_db)`。
- 旧 `run_with_history`（同步）暂留，等流式也迁完再删。
- 回归：阶段 0 的集成测试改跑 async 路径 + 路由级 `POST /chat/{id}`（mock LLM）。

### 阶段 3：流式 `run_stream_with_history` 异步化（2~3 天）

- `run_stream_with_history` → `run_stream_with_history_async` 返回 `AsyncGenerator[str, None]`：
  - 逐 `yield` 之间**不持有事务**：每步产出后 `await db.commit()`（现同步版已是「每步 flush，
    存完 AI 消息 commit」的思路，照搬）
  - 工具调用 `await asyncio.to_thread(...)`；LLM 流式 `async for chunk in client.astream_chat(...)`
    （需确认 LLM 客户端有 async 流式；没有则 `to_thread` 包同步生成器 + `asyncio.Queue` 桥接）
  - 并发闸 `concurrency_guard`（同步 CM）改成 `async with` 或在生成器外层管理
- `FasdtApi/chat.py::chat_stream` 改 `async def`，`StreamingResponse(async_gen())`，
  `db: AsyncSession = Depends(get_async_db)`
- 回归：路由级 SSE 冒烟（读前几个 event）；手动真机流式对话。

### 阶段 4：收尾（0.5 天）

- 删同步 `run_with_history` / `run_stream_with_history` 及 `chat_service` 的同步分支
- `FasdtApi/chat.py` 移除 `get_db` import；`agent_run` 路由若还引用同步 runtime 一并处理
- `docs/sync-async-boundary.md` / `docs/backend-map.md` 标记 chat 链路收口完成
- `tests/test_widget_sync_boundary.py` 式的守卫可选：`service/runtime/` 下不得出现 `Session(` / `get_db`

## 3. 风险与回滚

| 风险 | 缓解 |
| --- | --- |
| 事务边界改错导致消息 / 运行记录丢失 | 阶段 0 集成测试覆盖「存了用户消息但 LLM 失败」「工具失败」「中途异常」三条路径；每阶段跑 |
| 流式 `await` 阻塞事件循环（工具 / 同步 LLM） | 一切阻塞调用走 `asyncio.to_thread`；上线后看 `/metrics` 的请求耗时分布 |
| `AsyncSession` 跨 `yield` 生命周期问题 | 生成器内每步提交、不跨 yield 持有未提交状态；`expire_on_commit=False` 已配置 |
| 下游 async 服务与同步版行为漂移 | 阶段 1 每个 async 版配「与同步版输出一致」的对照单测 |
| 回滚 | 每阶段是独立提交；`*_async` 与同步版并存到阶段 4 才删，任一阶段可 `git revert` 单个提交 |

## 4. 预估

约 **8~11 人日**，分 5 个可独立发布的提交批次。阶段 1 可与阶段 0 并行。
建议一个人连续做，避免 async/同步双版本长期并存。
