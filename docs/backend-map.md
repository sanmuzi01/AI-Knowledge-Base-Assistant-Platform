# Backend Map

这份文档按业务模块列出后端入口，方便你以后快速定位代码。

## 1. 用户与权限

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| 登录、注册、当前用户 | `FasdtApi/login.py` | `service/auth_service.py`、`service/auth_async_service.py` | `models/user_dao.py`、`models/user_async_dao.py` |
| 用户画像 | `FasdtApi/login.py` | `service/user_profile_service.py`、`service/user_profile_async_service.py` | `models/user_profile_dao.py`、`models/user_profile_async_dao.py` |
| 权限依赖 | `service/dependencies.py` | - | - |
| 管理员后台 | `FasdtApi/admin.py` | `service/admin_service.py`、`service/admin_async_service.py` | 多个业务 DAO |

## 2. Agent

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| Agent 增删改查 | `FasdtApi/agent.py` | `service/agent_service.py`、`service/agent_async_service.py` | `models/agent_dao.py`、`models/agent_async_dao.py` |
| 运行轨迹 | `FasdtApi/agent_run.py` | `service/agent_run_async_service.py` | `models/agent_run_dao.py`、`models/agent_run_async_dao.py` |
| Runtime | - | `service/runtime/agent_runtime.py` | `models/agent_run_dao.py` |

## 3. 对话和记忆

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| 新版会话 | `FasdtApi/conversation_route.py` | `service/conversation_service.py`、`service/conversation_async_service.py` | `models/conversation_dao.py`、`models/conversation_async_dao.py` |
| 聊天接口 | `FasdtApi/chat.py` | `service/chat_service.py`、`service/chat_async_service.py` | `models/chat_dao.py`、`models/chat_async_dao.py` |
| 长期记忆 | `FasdtApi/memory.py` | `service/memory/memory_service.py`、`service/memory_async_service.py` | `models/memory_dao.py`、`models/memory_async_dao.py` |

## 4. 知识库和 RAG

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| 知识库接口 | `FasdtApi/knowledge.py` | `service/knowledge_async_service.py`、`service/rag/rag_service.py` | `models/knowledge_dao.py`、`models/knowledge_async_dao.py` |
| 文档切片 | - | `service/rag/rag_service.py` | `models/knowledge_chunk_dao.py` |
| Embedding | - | `service/rag/embedding_service.py` | - |
| 向量库 | - | `service/rag/vector_store_service.py` | Chroma |
| 网页抓取 | `FasdtApi/knowledge.py` | `service/web_crawler_service.py` | - |

## 4b. 自定义工作台组件（自然语言驱动）

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| 组件 design / CRUD / run | `FasdtApi/user_widget.py` | `service/widget_async_service.py`、`service/widgets/*` | `models/user_widget_async_dao.py` |
| 数据源连接器 / 处理器 / 校验 / 运行引擎 / 保留策略 | - | `service/widgets/{connectors,processors,validator,designer,runner,scheduler,retention,schema}` | `user_widgets`、`widget_data_points` |
| 到点自动调度 | 后台 Worker（`service/background_worker.py` 的 `_run_widget_scheduler_tick`） | `service/widgets/scheduler.py`（默认开启，`WIDGET_SCHEDULER_ENABLED=0` 关） | 乐观锁抢占 `user_widgets.next_run_at` |
| 外部数据源 | - | `service/widgets/connectors/{http_api,web_page,knowledge_base}.py`（复用 `web_crawler_service` 的 SSRF 校验 + `http_resilience` 的重试/熔断） | - |

详见 `docs/widget-platform.md`。

## 4c. 知识库空间（Knowledge Space，阶段1-3）

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| 空间 CRUD（用户级隔离） | `FasdtApi/knowledge_space.py`（`/knowledge-spaces`） | `service/knowledge_space/space_async_service.py` | `models/knowledge_space_async_dao.py` |
| 空间内文档 上传/抓取/列表/元数据/启停/重建/删除 | `FasdtApi/knowledge_space.py`（`/knowledge-spaces/{id}/documents`） | `service/knowledge_space/document_service.py` → `service/knowledge_service.py` + 后台任务 | `models/knowledge_dao.py`（+`by_space`），`knowledge`(`space_id`) |
| 迁移 / 兜底 / 统计 | - | `service/knowledge_space/{space_service,binding_service,membership}.py` | `models/{knowledge_space_dao,agent_knowledge_space_dao}.py` |
| 隔离唯一入口 | - | `service.access_control.get_owned_space[_async]`（owner 或任意角色成员）/ `user_space_ids[_async]`（owned ∪ member）/ `get_space_role[_async]`（owner/admin/editor/viewer/None） | `knowledge_spaces`、`space_members` |
| **成员 / 角色 / 审计（阶段6）** | `FasdtApi/knowledge_space.py`（`/{id}/members` GET·PUT·DELETE、`/{id}/audit` GET） | `service/knowledge_space/space_async_service.py`（`list_members` / `set_member` / `remove_member` / `list_audit`，`_require_manage` 走 `membership.can_manage_members`）、`membership.can_*` 分级 | `models/space_member_dao.py`、`models/kb_audit_dao.py`、`space_members` / `kb_audit_log` 表 |
| **企业视角（阶段6）** | `FasdtApi/admin.py`（`GET /admin/knowledge-spaces`，`get_current_admin_user_async`） | `service/admin_async_service.list_knowledge_spaces` | `knowledge_spaces` / `space_members` / `agent_knowledge_space` |
| 存量迁移 | - | `scripts/migrate_agent_kb_to_space.py`（dry-run / `--apply`） | `knowledge.space_id` 回填 |
| 向量集合键 | - | `service/rag/vector_store_service.py`：`agent_{id}` / `space_{id}` 双制式 | ChromaDB |
| **多空间联合检索 + 引用（阶段3）** | - | `service/rag/space_search.py::search_spaces`（同步入口，自带 Session；逐 space 归属校验 + 多集合合并 + rerank + `【来源N】` context + citations + 拒答） | `knowledge_chunk`、`knowledge`、`knowledge_spaces` |
| **Agent 检索统一入口（阶段3）** | - | `service/rag/search_entry.py::search_for_agent`（绑定 space → `space_search`；未绑定 → 旧 `search_scoped`）；`agent_runtime` 经 `to_thread` 调用，`_compose_kb_prompt` 注入引用/拒答规则 | `agent_knowledge_space` |
| **Agent 绑定 space + `kb_*` 配置（阶段3）** | `FasdtApi/agent.py`（`AgentCreate`/`AgentUpdate` 加 `space_ids` / `kb_top_k` / `kb_rerank_enabled` / `kb_force_citation` / `kb_refuse_when_empty`） | `service/agent_service.py`（`_validate_space_ids` + `set_agent_spaces` 同事务收尾）、`agent_async_service`（读回 `space_ids`） | `models/agent_knowledge_space_dao.py`、`agent.kb_*` 列 |
| **知识库调试台（阶段4）** | `FasdtApi/rag_debug.py`（`/rag-debug`：`/run` 跑检索快照 + 可选 LLM 回答；`/samples` CRUD + `/samples/export` → `rag_eval` cases） | `service/rag/debug_service.py`（`run_retrieval` 经 `to_thread`；`attach_answer` 调 `llm_service.async_chat` + `evaluate_faithfulness`；样例存取按 `user_space_ids` / `get_owned_space_async` 隔离） | `models/rag_debug_dao.py`（异步）、`rag_debug_samples` 表 |
| **健康分（阶段5）** | `GET /knowledge-spaces/{id}/health`（实时算并回写 `health_*`） | `service/knowledge_space/health_service.py`（只读 DB 算文档侧 + 检索侧指标 → 加权 0~100；`health_snapshot` 自带 Session + `get_owned_space` 校验；`space_health` 后台 runner 走 `compute_and_persist`） | `knowledge` / `rag_debug_samples` / `knowledge_spaces.health_*` |
| **按空间评估（阶段5）** | `POST /evaluation/space/{space_id}/rag` | `service/evaluation/rag_eval_service.run_for_space`（检索走 `space_search.search_spaces`，逐条 `to_thread`；复用 `evaluate_retrieval_case` + `_summarize_case_reports`） | - |
| **Widget 知识库健康 connector（阶段5）** | Widget 平台（`data_source.kind=knowledge_space`，`config.space_id`） | `service/widgets/connectors/knowledge_space.py`（`to_thread(health_snapshot)`；`schema` 白名单 + `designer` 提示） | 同健康分 |

聊天回答的引用来源经 SSE `citations` 事件下发（`service/runtime/sse_events.make_citations`），
前端 `Chat.vue` 用 `components/knowledge/CitationList.vue` 展示。

阶段6：写权限分级只在 service 层（`space_async_service` / `document_service`），
viewer 只读、editor 增删文档、admin 改空间·管成员、owner 删空间；越权 404（不泄露存在性），
有读权限无写权限则 403。`teams` / `organizations` 表已建但暂不参与 `user_space_ids` 计算。
细节见 `docs/knowledge-space-plan.md`。

## 5. Skill

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| Skill 增删改查 | `FasdtApi/skill_route.py` | `service/skill_service.py`、`service/skill_async_service.py` | `models/skill_dao.py`、`models/skill_async_dao.py` |
| Skill 配置加载 | - | `service/skills/loader.py` | YAML 文件 |
| Agent 绑定 Skill | `FasdtApi/skill_route.py` | `service/skill_service.py` | `models/skill_dao.py` |

## 6. 模型配置

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| 模型配置 | `FasdtApi/llm_config.py` | `service/llm/llm_config_service.py` | `models/llm_config_dao.py`、`models/llm_config_async_dao.py` |
| 模型目录 | - | `service/llm/model_catalog.py` | - |
| LLM 调用 | - | `service/llm/llm_service.py` | - |

## 7. 后台任务与运维

| 功能 | 路由 | Service | DAO |
| --- | --- | --- | --- |
| 任务中心 | `FasdtApi/background_task.py` | `service/background_task_service.py`、`service/background_task_async_service.py` | `models/background_task_dao.py`、`models/background_task_async_dao.py` |
| Worker | - | `service/background_worker.py` | `models/background_task_dao.py` |
| 操作日志 | `FasdtApi/admin.py` | `service/operation_log_service.py`、`service/operation_log_async_service.py` | `models/init_db.py` 的 `OperationLog` |
| 请求日志中间件 | - | `service/operation_log_middleware.py` | - |
| 安全中间件 | - | `service/security_middleware.py` | - |
| 请求 ID 中间件 | - | `service/request_context_middleware.py` | - |
| 指标 | `FasdtApi/main.py` | `service/metrics_service.py` | Prometheus |

## 8. 调试入口

常用命令：

```powershell
npm run test:unit
npm run release:check
npm run backend:dev
npm run frontend:dev
npm run backend:worker
```

常用页面：

```text
/health
/metrics
前端设置页
管理员后台 / 系统诊断
任务中心
```

## 同步 / 异步路由现状

路由层正在从同步 `Session`（`get_db`）迁到 `AsyncSession`（`get_async_db`），
按「先读后写、跟着底层管线走」的节奏推进。

| 路由文件 | 状态 |
| --- | --- |
| `login.py` `admin.py` `background_task.py` `conversation_route.py` `agent_run.py` `memory.py` `llm_config.py` `web_monitor.py` | 已全量 async |
| `agent.py` | 读接口 async；写接口（create/update/delete/clone/select）+ debug/dry-run 仍同步，`agent_service` 把 db/user 当同会话 ORM 对象改写 |
| `chat.py` | history 等读接口 async；同步/流式对话走 `agent_runtime`（同步 ORM + 生成器），暂留同步。RAG 检索经 `search_entry.search_for_agent`（自带 Session，async 路径 `to_thread` 调用），不把同步 Session 带进流程。迁移方案见 `docs/agent-runtime-async-migration.md` |
| `evaluation.py` | 端点 async；`/{agent}/rag` 的 db 同步走旧 `rag_service.async_search`；`/space/{id}/rag` 用 `run_for_space` —— 逐条 `to_thread(space_search.search_spaces)`，不带同步 Session 进端点 |
| `knowledge.py` | 列表 / 文档详情 / 片段 全量 async；检索 `async def` + `to_thread(search_entry.search_scoped)`，处理器不持有同步 Session；诊断 / 上传 / 入库 / 重建 仍走同步 RAG 管线 |
| `knowledge_space.py` | 空间 CRUD 全量 async；`/health` `async def` + `to_thread(health_service.health_snapshot)`；文档上传/抓取/重建/启停/删除沿用 `knowledge_service` 同步 + 后台任务 |
| `rag_debug.py` | 样例 CRUD / 导出全量 async；`/run` 端点 async + `to_thread(debug_service.run_retrieval)`（RAG 管线同步，不带同步 Session 进路由），可选 LLM 回答走 `llm_service.async_chat` |
| `skill_route.py` | 读接口（我的/公开/单个、校验、Agent 绑定列表）全量 async（已删同步回退分支）；创建/绑定/导入导出走 `skills_core`（文件系统 + 同步 ORM） |

同步 `def` 端点由 FastAPI 放线程池执行，不阻塞事件循环。彻底收口的前置条件是
把 `agent_runtime`、RAG 管线、`skills_core` 迁到 AsyncSession，并补接口级集成测试。

边界规则、组件平台的收口做法、以及 knowledge/agent 的下一步计划见 `docs/sync-async-boundary.md`。
