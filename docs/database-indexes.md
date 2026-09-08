# Database Index Notes

本项目的索引按实际查询路径设计，重点优化用户侧列表、聊天历史、知识库、后台任务、运行记录和管理员日志。

## 核心原则

- 优先覆盖 `WHERE + ORDER BY` 同时出现的查询。
- 避免给 `Text` 大字段加索引，例如消息内容、错误详情、文档切块内容。
- 低区分度字段不单独滥加索引，例如只按 `status` 查询时，通常需要搭配时间或用户维度。
- 新库由 SQLAlchemy `Index` 自动创建；已有库由 `models/init_db.py` 的幂等迁移补齐缺失索引。

## 主要索引

- `agent(user_id, id)`：用户 Agent 列表。
- `llm_config(user_id, model_name)`：用户模型配置查询。
- `knowledge(user_id, created_at)`：用户知识库列表。
- `knowledge(agent_id, created_at)`：Agent 下文档列表。
- `knowledge(agent_id, is_enabled, status)`：RAG 检索前筛选可用文档。
- `knowledge_chunk(knowledge_id, chunk_index)`：文档切块顺序读取。
- `knowledge_chunk(vector_id)`：向量库返回 ID 后反查切块内容。
- `conversation(user_id, agent_id, is_archived, is_pinned, update_time)`：会话列表。
- `message(conversation_id, create_time)`：聊天历史读取。
- `agent_run(user_id, started_at)`：用户运行记录。
- `agent_run(agent_id, conversation_id, started_at)`：会话隔离下的运行记录。
- `agent_step(run_id, step_no)`：运行步骤详情。
- `background_task(user_id, status, created_at)`：用户任务列表。
- `background_task(status, task_type, created_at, id)`：Worker 领取排队任务。
- `background_task(status, started_at)`：超时 running 任务重排。
- `operation_log(user_id, created_at)`：管理员按用户筛日志。
- `operation_log(method, created_at)`：管理员按方法筛日志。
- `operation_log(status_code, created_at)`：管理员按状态码筛日志。
- `operation_log(latency_ms, created_at)`：管理员筛慢请求。

## 后续压测检查

上线前建议对以下接口执行 `EXPLAIN`：

- `GET /agent/`
- `GET /conversation/{agent_id}`
- `GET /knowledge/agent/{agent_id}`
- `GET /agent_run/`
- `GET /background-task/`
- `GET /admin/users`
- `GET /admin/logs`
- Worker 领取任务查询

如果 `EXPLAIN` 出现全表扫描，需要结合真实数据量、筛选条件和排序字段再调整组合索引。
