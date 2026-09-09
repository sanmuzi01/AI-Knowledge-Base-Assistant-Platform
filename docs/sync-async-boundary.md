# 同步 / 异步边界

本项目正从「同步 SQLAlchemy」向「异步 SQLAlchemy（asyncmy）」迁移，目前是混合状态。
这份文档记录**当前边界**和**收口计划**，避免继续往里加随手的同步旁路。

## 已收口

### 组件平台 `service/widgets/**`
- runner / scheduler / 所有 connector.fetch / processor 一律 `async`，只接受 `AsyncSession`（`ctx.db`）。
- 禁止 `SessionLocal(` / `get_db` / 同步 `requests`，由 `tests/test_widget_sync_boundary.py` 守卫。
- 跨到同步子系统只经 `asyncio.to_thread` 调它们的单一入口：
  - RAG 检索 → `service/rag/search_entry.py::search_for_widget`（自带同步 Session + 归属校验）
  - 网页抓取 → `service/web_crawler_service.py::crawl_url_to_markdown`
- 后台 Worker 用**进程内常驻事件循环**跑组件调度 tick，不再每轮 `asyncio.run()` 建/拆 loop。

## 未收口

### ~~高频读取接口的「异步双轨」~~ —— 已收口

`asyncmy` 早已是硬依赖（`models/async_db.py` 缺驱动直接 `raise`，`get_optional_async_db = get_async_db`），
所以旧的 `if async_db is not None: ... else: <同步回退>` 分支其实是死代码。已删除：

- `FasdtApi/knowledge.py`：`list_my_documents` / `{agent}/list` / `{agent}/{kid}` / `{agent}/{kid}/chunks`
  改为只依赖 `get_async_db`，去掉同步回退分支与随之无用的同步 DAO import（`_doc_to_dict`、
  `list_knowledge_*`、`list_chunks_by_knowledge`）。
- `FasdtApi/agent.py`：读接口本来就只用 `get_async_db`，无需改；`get_agent` 404 改抛 `NotFound`。
- `FasdtApi/skill_route.py`：`/`、`/public`、`/{id}`、`/{id}/validate`、`/agent/{id}` 五个读接口
  收敛为纯 `get_async_db`，删同步回退分支与随之无用的 `list_user_skills` / `list_public_skills` /
  `validate_skill` / `list_agent_skills` / `get_skill` / `get_skill_config` import；404 改抛 `NotFound`。
- `FasdtApi/conversation_route.py`：早已全量 `get_async_db`，无死分支。

回归由 `tests/test_routes_isolation.py` 兜底（本人 200 / 别人 404 / 不存在 404）。

### RAG 检索
`rag_service.search` / `_build_search_results` 依赖同步 Session + 同步 ChromaDB + 同步 rerank。
`async_search` 只把「查询向量化」这一步做成了异步。组件平台已通过线程桥接绕开，
其它调用方（`FasdtApi/knowledge.py::search_knowledge`）仍直接传同步 `db`。

### 写入 / 后台任务链路
知识库入库、重建索引、抓取入库走 `knowledge_service`（同步）+ 后台任务；任务 Worker 主体也是同步循环。

## 收口计划（优先 knowledge、agent）

1. ~~**把 asyncmy 定为硬依赖**~~ —— 早已是（`requirements.txt` 固定 `asyncmy==0.2.10`，
   `models/async_db.py` 缺驱动直接 `raise`）。`docs/deployment.md` 的「回退同步」表述已订正。
2. ~~**删掉读接口的同步回退分支**~~ —— 已完成：knowledge / agent / skill_route 清理完毕，
   conversation / 其余路由核查无死分支；`models/async_db.py` 的 `get_optional_async_db` 别名已删除
   （`grep -rn get_optional_async_db FasdtApi` 为空）。
3. **RAG 检索走线程桥接**（进行中）：
   - ✅ `service/rag/search_entry.py::search_scoped`（自带同步 Session + 归属/文档校验）+
     `FasdtApi/knowledge.py::search_knowledge` 改为 `await asyncio.to_thread(search_scoped, ...)`，
     处理器不再持有同步 `Session`。`PermissionError→NotFound`、`ValueError→InvalidInput`。
   - ⏳ `rag_service.async_search` 仍保留（`rag_eval_service`、`agent_runtime` 在用），
     内部依旧是「向量化 async + 检索 sync」的半异步。
   - ⏳ 知识库上传 / 入库 / 重建 / 诊断仍走同步 `knowledge_service` + 后台任务。
   - 更彻底的做法（`_get_client` / chunk 反查改异步 DAO，ChromaDB/rerank 仍同步）留待评估。
4. ~~**异常统一**~~ —— 路由层已全覆盖。`service/exceptions.py` 领域异常 + `main.py` 统一处理器：
   - `FasdtApi/*.py` 里所有 `raise HTTPException(4xx)` → `NotFound` / `InvalidInput` / `PermissionDenied`；
     `grep -rn 'HTTPException(status.HTTP_4' FasdtApi` 为空。
   - 仅保留：`_limit_error`（429 + `Retry-After` 头）与少数 500 兜底 `HTTPException`。
   - 处理器按 `[code] METHOD PATH -> msg` 记一行日志（<500 warning / ≥500 error），返回体带 `code` 字段。
   - service 层内部的 `raise ValueError` 等按需在后续迁移中逐步替换（路由层已在 except 里翻译）。
5. **写入链路 / Worker**：最后再评估是否值得异步化——收益低、风险高，可长期保持同步。
