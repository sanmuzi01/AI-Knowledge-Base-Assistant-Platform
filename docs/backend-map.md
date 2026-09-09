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
| `chat.py` | history 等读接口 async；同步/流式对话走 `agent_runtime`（同步 ORM + 生成器），暂留同步 |
| `evaluation.py` | 端点 async，但 db 同步 —— RAG 检索管线（`rag_service`、ChromaDB、DAO）仍同步 |
| `knowledge.py` | 列表/诊断 async；上传/入库/重建/检索走同步 RAG 管线 |
| `skill_route.py` | 部分读接口 async；创建/绑定/导入导出走 `skills_core`（文件系统 + 同步 ORM） |

同步 `def` 端点由 FastAPI 放线程池执行，不阻塞事件循环。彻底收口的前置条件是
把 `agent_runtime`、RAG 管线、`skills_core` 迁到 AsyncSession，并补接口级集成测试。
