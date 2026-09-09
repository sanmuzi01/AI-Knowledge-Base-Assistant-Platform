# 同步 / 异步边界

本项目正从「同步 SQLAlchemy」向「异步 SQLAlchemy（asyncmy）」迁移，目前是混合状态。
这份文档记录**当前边界**和**收口计划**，避免继续往里加随手的同步旁路。

## 已收口

### 组件平台 `service/widgets/**`
- runner / scheduler / 所有 connector.fetch / processor 一律 `async`，只接受 `AsyncSession`（`ctx.db`）。
- 禁止 `SessionLocal(` / `get_db` / 同步 `requests`，由 `tests/test_widget_sync_boundary.py` 守卫。
- 跨到同步子系统只经 `asyncio.to_thread` 调它们的单一入口：
  - RAG 检索 → `service/rag/widget_search.py::search_for_widget`（自带同步 Session + 归属校验）
  - 网页抓取 → `service/web_crawler_service.py::crawl_url_to_markdown`
- 后台 Worker 用**进程内常驻事件循环**跑组件调度 tick，不再每轮 `asyncio.run()` 建/拆 loop。

## 未收口

### 高频读取接口的「异步双轨」
`FasdtApi/knowledge.py`、`FasdtApi/agent.py` 等的读接口目前是：

```python
async def handler(db: Session = Depends(get_db), async_db = Depends(get_optional_async_db), ...):
    if async_db is not None:
        return await xxx_async_service...(async_db, ...)     # 主路径
    # 回退：本地未装 asyncmy 时走同步
    return xxx_service...(db, ...)
```

这是刻意的过渡设计（见提交 `7fd82b0 feat(service): 补齐高频读取接口的异步 service 双轨`）：
生产装了 `asyncmy` 走异步，开发没装则回退同步、不崩。代价是每个请求仍申请一条同步连接。

### RAG 检索
`rag_service.search` / `_build_search_results` 依赖同步 Session + 同步 ChromaDB + 同步 rerank。
`async_search` 只把「查询向量化」这一步做成了异步。组件平台已通过线程桥接绕开，
其它调用方（`FasdtApi/knowledge.py::search_knowledge`）仍直接传同步 `db`。

### 写入 / 后台任务链路
知识库入库、重建索引、抓取入库走 `knowledge_service`（同步）+ 后台任务；任务 Worker 主体也是同步循环。

## 收口计划（优先 knowledge、agent）

1. **把 asyncmy 定为硬依赖**：确认 `requirements.txt` 固定 asyncmy 版本、CI 一定安装；
   更新 `docs/deployment.md`（当前承诺「未装 asyncmy 会回退同步」——收口后删掉该承诺）。
2. **删掉读接口的同步回退分支**：`get_optional_async_db` → `get_async_db`，
   移除 `db: Session = Depends(get_db)` 与随之无用的同步 DAO import，一个模块一个模块来
   （knowledge → agent → conversation → …）。以 `tests/test_routes_isolation.py` 式的路由级测试兜底。
3. **RAG 检索异步化**：`_get_client` / 知识 chunk 反查改异步 DAO；ChromaDB / rerank 仍同步，
   统一封在 `asyncio.to_thread` 里（就像 `widget_search.py` 现在的做法），对上层呈现 `async`。
4. **异常统一**：迁移过程中把各模块的 `raise ValueError` / `HTTPException` / 裸 `Exception`
   换成 `service/exceptions.py` 的领域异常（组件平台已完成，作为参考）。
5. **写入链路 / Worker**：最后再评估是否值得异步化——收益低、风险高，可长期保持同步。
