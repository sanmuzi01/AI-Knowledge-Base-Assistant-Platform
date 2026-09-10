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

### 阶段 0：清障 ✅

- ✅ `run()` / `run_stream()`（旧 Chat 表路径）已确认无调用方并删除（`agent_runtime.py` 843 → 483 行），
  连同不再使用的 `from models.chat_dao import create_chat, list_chats_by_agent`。当前只剩
  `run_with_history` / `run_stream_with_history` 两个入口。
- ✅ 「查 AgentRun 收尾」那段重复代码（两个入口失败分支各一处 `db.query(AgentRun).filter(...).first()`）
  抽成 `_finalize_run(db, run_id, status, *, error_msg=None)` helper（`agent_runtime.py`）。纯去重，无行为变化。
- ✅ 回归基线：`tests/test_agent_runtime.py`（真实 DB + stub `ToolExecutor` 注入 FakeLLM + 真实
  `ReActEngine`）。9 条：无工具对话（同步 / 流式）、一次工具调用往返、RAG on（上下文入 prompt +
  `retrieval` 步 + citations 透传）、RAG 失败降级、memory on（记忆入 prompt + 触发总结）、
  memory 总结失败、LLM 失败（同步 re-raise / 流式 error 事件）。全量 261 通过。

**阶段 0 暴露的两个事务边界怪癖**（当前同步实现，阶段 2/3 迁移时必须处理，测试已按现状锚定）：

1. **失败运行不落库**：`run_with_history` 成功路径只 `db.flush()`，AgentRun 的 commit 由 `chat_service`
   收尾统一做。引擎抛异常时 `except` 里先 `db.rollback()`，把**尚未提交的 `create_run` 行一起回滚**，
   随后 `_finalize_run` 查不到该行 → 失败运行**不留 AgentRun 记录**（仅异常 / error 事件对外可见）。
   → 迁移目标：`create_run` 独立事务提交，失败时单独 `UPDATE ... status='failed'`。
2. **记忆总结失败连累整笔事务**：第 8 步 `summarize_and_save` 抛异常时 `except` 里的 `db.rollback()`
   会把**整笔未提交事务（含已 `finished` 的 run）回滚**；调用方仍拿到 answer，但 AgentRun 不落库。
   → 迁移目标：记忆总结走独立 `AsyncSession` / 独立事务，失败只吞自己那段。

### 阶段 1：DAO / 下游服务的 async 版本 ✅

不动 `agent_runtime`，先把它依赖的东西补出 async 双胞胎。**已完成**：

| 同步 | 新增 async | 落点 |
| --- | --- | --- |
| `models/agent_run_dao.py` `create_run` / `create_step` / `update_run_status` / `count_finished_runs_by_agent` / `list_finished_runs_by_agent` | `*_async` | `models/agent_run_async_dao.py`（原本只有读 helper，补了 5 个写/统计函数） |
| `service/conversation_service.py` `save_message` / `load_history_for_llm` / `maybe_update_title_by_first_message` | `*_async` | `service/conversation_async_service.py` + `models/conversation_async_dao.py`（`create_message_async` / `touch_conversation_async` / `list_messages_for_history_async`） |
| `service/memory/memory_service.py` `load_memory` / `should_summarize` | `load_memory_async` / `should_summarize_async` | `service/memory_async_service.py`；纯文本/阈值逻辑抽成 `render_memory_text` / `summary_due` 供同步异步共用 |
| `service/memory/memory_service.py` `summarize_and_save` | `summarize_and_save_async` | `service/memory_async_service.py`；LLM 走 `llm_service.async_chat`，不在函数内 commit（同同步版，由调用方提交） |
| `service/user_profile_service.py` `format_user_profile_for_prompt` / `infer_user_profile_from_summary` | `*_async` | `service/user_profile_async_service.py`；prompt 渲染抽成 `render_profile_prompt` 共用 |
| `prompt.prompt_manager.build_prompt` | 不变（读文件，无 db） | 保持同步 |

- 共用纯函数（同步 / 异步都调，保证输出逐字一致）：`memory_service.render_memory_text` /
  `memory_service.summary_due` / `user_profile_service.render_profile_prompt`。
- 回归：`tests/test_agent_runtime_async_deps.py`（11 条，真实 DB）—— 每个 async 版与同步版在同一批
  数据上断言输出一致（含空数据、阈值边界、`summarize_and_save` patch LLM 后的落库对照）。全量 272 通过。
- 此阶段**不改任何路由 / `agent_runtime` 行为**。

### 阶段 2：非流式 `run_with_history` 异步化 ✅

已完成：

- `service/runtime/agent_runtime.py` 新增 `run_with_history_async(db: AsyncSession, ...)`：
  - `_compose_system_prompt_async`：画像 / 记忆走阶段 1 的 `*_async`。
  - RAG：`_kb_retrieve`（`search_entry.search_for_agent`）经 `asyncio.to_thread`，同步 RAG 链路不进主协程。
  - ReAct 引擎：`_execute_react_sync` 在**独立同步 Session** 里装配 `ToolExecutor` + 跑 `engine.invoke`，
    整段 `await asyncio.to_thread(...)`；轨迹先由 `step_callback` 收集，引擎跑完后主协程用
    `create_step_async` 统一落库（步号规则抽成纯函数 `_plan_react_steps`，与同步版 `_record_react_step` 一致）。
  - `create_run_async` 后**立即 `await db.commit()`** → 修阶段 0 怪癖 1：LLM/引擎失败也留下
    `status='failed'` 的 AgentRun（`_finalize_run_async` 在 rollback 后按 id 重新 `UPDATE`）。
    ⚠️ `run.id` 在异常路径 `rollback()` 后会 expire，函数开头就固化成局部 `run_id`。
  - 记忆总结走 `_summarize_memory_async`：**独立 `AsyncSessionLocal()` + 独立事务** → 修怪癖 2：
    总结失败只吞自己，不回滚已 finished 的 run。
- `service/chat_service.py::chat_with_agent` 全量 async：`get_owned_agent_async` /
  `get_owned_conversation_async` / `conversation_async_service.*` / `run_with_history_async`；
  用户消息在 `run_with_history_async` 首个 commit 时一并落库（顺带改善「存了用户消息但 LLM 失败」）。
- `FasdtApi/chat.py::chat`：`Depends(get_db)` → `Depends(get_async_db)`。SSE 流式端点不动。
- 旧同步 `run_with_history` 暂留（阶段 2 后无运行时调用方，仅 `tests/test_agent_runtime.py`
  基线在用），阶段 4 删。
- 回归：`tests/test_agent_runtime_async.py`（8 条）—— 与同步基线一致的 5 条 + 两处行为改进各 1 条
  （失败留 failed run / 总结失败保 finished run）+ 路由级 `POST /chat/{id}` happy path & 跨用户拒绝。
  全量 280 通过。

### 阶段 3：流式 `run_stream_with_history` 异步化 ✅

已完成：

- `agent_runtime.run_stream_with_history_async` → `AsyncGenerator[str, None]`：
  - LangGraph 同步 `engine.invoke_stream()` 整段跑在 worker 线程（`_worker` + 自带同步 Session），
    产出的 SSE 事件串经 `loop.call_soon_threadsafe(queue.put_nowait, ev)` 桥回；主协程
    `while` 拉 `asyncio.Queue` 逐条 `yield`，读到 `_SENTINEL` 结束，再 `await worker`。
    （没上「LLM 逐 token async 流式」——现引擎就是整段 `invoke_stream` 出事件，保持一致。）
  - 线程内不碰 DB；轨迹 `step_callback` 收进 `step_infos`，流结束后主协程 `create_step_async` 统一落库。
  - 事务边界同阶段 2：run 建好即 `await db.commit()`（失败留 failed）；`update_run_status_async`
    后 `await db.commit()`；记忆总结走 `_summarize_memory_async` 独立事务（成功才发
    `memory:summarized` 事件；失败静默——与同步版发 `memory:error` 的小差异，可接受）。
  - `run_id` 同样在函数开头固化（异常路径 rollback 会 expire ORM 对象）。
- `chat_service.chat_with_agent_stream_async`（`async def` + `async for`）：会话/消息全 async；
  转发 runtime 事件、从 `answer` 事件抠 `final_answer`，收尾存 AI 消息 + `await db.commit()`，
  末尾补一个带 `conversation_id` 的 done（`run_id=None, steps=0`，与同步版一致——前端用 runtime 的 done）。
- `FasdtApi/chat.py::chat_stream` → `async def` + `db=Depends(get_async_db)` +
  `get_current_user_async` + `async def limited_generator()`；`concurrency_guard`（同步 CM）
  仍在生成器外 `__enter__` / `finally __exit__`（非阻塞，保持不变）。
- `FasdtApi/chat.py` 清掉不再用的 `get_db` / `Session` / `get_current_user` import。
- 回归：`tests/test_agent_runtime_stream_async.py`（7 条）——基线一致 4 条（纯流式 / 工具 / RAG /
  记忆）+ 行为改进 2 条 + 路由级 `POST /chat/{id}/stream` SSE 冒烟。全量 287 通过。

### 阶段 4：收尾 ✅

- `service/runtime/agent_runtime.py`：删掉 `run_with_history` / `run_stream_with_history`（同步）
  及只服务它们的 `_compose_system_prompt` / `_record_react_step` / `_finalize_run`；
  清掉 `create_run` / `create_step` / `update_run_status`（同步 DAO）、`get_owned_agent`（同步）、
  `service.memory.memory_service` 的 `load_memory` / `should_summarize` / `summarize_and_save`、
  `format_user_profile_for_prompt`（同步）、`datetime` / `Generator` import。
  剩下的入口：`run_with_history_async` / `run_stream_with_history_async`（+ 共用纯函数
  `_short_text` / `_format_rag_audit` / `_kb_retrieve` / `_compose_kb_prompt` / `_plan_react_steps` /
  `_compose_system_prompt_async` / `_execute_react_sync`）。
- `service/chat_service.py`：删掉同步 `chat_with_agent_stream` 及 `conv_service` / `conv_dao` /
  `get_owned_agent`（同步）/ `Generator` import。只剩 `chat_with_agent` /
  `chat_with_agent_stream_async`，全量 AsyncSession。
- `FasdtApi/chat.py`：`get_db` / `Session` / `get_current_user`（同步）import 已移除，
  整个路由收口到 `get_async_db` + `get_current_user_async`。
- 测试：stage-0 的同步基线 `tests/test_agent_runtime.py` 删除（行为已被
  `test_agent_runtime_async.py` + `test_agent_runtime_stream_async.py` 覆盖）；共用替身抽到
  `tests/_runtime_fakes.py`。全量 278 通过。
- 注：`service/memory/memory_service.py`（`load_memory` 等）与 `conversation_service` /
  `user_profile_service` 的同步版仍在——它们服务其它同步调用方（管理端、后台任务），
  只是 `agent_runtime` / `chat_service` 不再用。

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
