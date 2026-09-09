# Project Status

本项目当前处于功能完善后的上线前工程化阶段。核心业务链路已经具备，但还需要继续补齐生产安全、测试、部署验证和可观测性。

## 已完成能力

- 用户系统：注册、登录、当前用户、修改密码、账号禁用。
- 管理员后台：用户管理、任务管理、使用统计、操作日志、系统诊断。
- Agent 管理：创建、编辑、复制、选择、删除预检、调试。
- 聊天系统：同步聊天、SSE 流式聊天、会话管理、消息历史、会话导出。
- 模型配置：用户级 API Key、模型列表、自动适配模型 URL、配置测试。
- Skill 系统：创建、编辑、模板、导入、导出、校验、绑定 Agent。
- 知识库：上传、批量上传、切块、Embedding、检索、片段查看、启停、重建、删除。
- 知识库空间（阶段1-6，完整）：`/knowledge-spaces` 空间 CRUD + 空间内文档管理，
  `knowledge.space_id` / `agent.kb_*` 字段，向量集合键 `agent_{id}` / `space_{id}` 双制式，存量迁移脚本。
  Agent 可绑定多个空间做联合检索，回答带 `【来源N】` 引用来源，`kb_refuse_when_empty` 无命中拒答，
  未绑定空间的旧 Agent 回退原私有库路径。知识库调试台（`/knowledge-spaces/:id/debug`）：
  跑一次检索看命中片段/上下文/回答/忠诚度，存为测试样例并勾进评估集、导出成 `rag_eval` 用例。
  健康报告（`/knowledge-spaces/:id/health`）：文档失败/过期/未入库率 + 检索命中/拒答/引用率 → 健康分 0~100，
  可按评估集跑一次 RAG 评估；Widget 平台新增「知识库健康」数据源。
  **企业权限**：`space_members` 角色（owner/admin/editor/viewer）分级写权限，`kb_audit_log` 审计，
  `/admin/knowledge-spaces` 管理员企业视角；隔离全部收敛在 `access_control` 的三个函数里。
  前端「知识库中心」/「空间详情（含成员与权限、操作日志）」/「调试台」/「健康报告」页 +
  Agent 编辑「知识库」区块 + 聊天页「参考来源」+ 管理员「企业知识库」。
- 网页抓取：支持输入公开 URL 抓取正文，保存为 Markdown 后进入知识库后台入库流程，并带基础 SSRF 防护。
- 自定义工作台组件平台：自然语言 → 结构化组件配置（不落前端代码），统一运行引擎取数/处理/存快照 + 前端统一渲染器。
  - 数据源：内置示例、平台数据服务、我的运行统计、外部 HTTP、网页正文/更新监控、我的知识库。
  - 处理器：归一时序、字段挑选、聚合、JSON 取值、AI 摘要、阈值告警。
  - 到点自动调度：后台 Worker 乐观锁抢占，默认开启；失败指数退避、连续失败自动暂停；数据点保留策略。
  - 展示增强：时序/类目数据自动升级图表，创建前试运行，导出/导入配置，需关注标记。
- 长期记忆：按 Agent 管理长期记忆。
- 缓存：Redis 优先、内存兜底。
- 访问管控：聊天限流、知识库限流、并发控制、后台任务配额。
- 后台任务：独立 Worker 模式，支持任务领取、执行、失败记录、超时重新排队。
- 数据库连接池：已配置池大小、溢出连接、等待超时、连接回收和断线探测。
- 数据库索引：已按主要查询路径补首轮组合索引和幂等迁移。
- 压力测试：已提供轻量 HTTP 压测脚本和使用文档。
- 监控基础：已提供 Prometheus `/metrics`、请求耗时/状态码指标、连接池/缓存状态指标（可接入现有 Prometheus/Grafana）。
- 安全边界：已配置 CORS、Trusted Host、安全响应头、请求体大小限制和 Nginx 安全响应头。
- 熔断/降级：LLM 与 Embedding HTTP 调用已统一超时、重试、指数退避和进程内熔断。
- 配置校验：生产环境启动时会拦截占位密钥、缺 Redis、短信误配置、CORS/Host 未收紧等问题。
- 自动化测试：单元测试覆盖缓存、验证码、模型 URL 适配、HTTP 重试熔断、生产配置校验，组件平台
  全链路（连接器 / 处理器 / 调度 / 退避 / 保留 / 形态识别 / 导出导入 / 同步异步边界守卫）；
  真实路由级测试（`tests/test_routes_isolation.py`：TestClient + 真实 JWT + 真实 DB）覆盖登录鉴权、
  widgets / knowledge / agent / skill / conversation 的跨用户 404 隔离、后台任务管理员 403。
- 发布自检：`npm run release:check` 检查上线关键文件、组件平台核心模块、`deploy/` 监控配置可解析、
  `deploy/` 无残留容器主机名、组件调度已接入 Worker，再跑编译 + 单元测试 + 前端构建。
- 备份恢复：部署文档给出本地 MySQL `mysqldump` 导出 / 恢复命令与应用文件目录清单。
- 数据库迁移：已加入 Alembic 迁移骨架、基线版本和迁移文档，当前处于兼容过渡期。
- 部署基础：不再使用 Docker/compose；进程管理器（systemd / nssm 等）常驻 uvicorn + worker，
  Nginx 托管前端并反代 `/api`、`/health`、`/metrics`，`deploy/` 提供 nginx / prometheus / grafana 模板。

## 当前验证结果

- `python -m compileall` 通过。
- 前端 `npm run build`（含 vue-tsc 类型检查）通过。
- FastAPI 应用导入与路由生成通过。
- `python -m unittest`：195 通过（含真实路由级测试，需本地 / CI MySQL）。
- `npm run release:check` 静态检查通过。

## 当前主要风险

- 同步 / 异步边界部分收口：路由层读接口 + 知识库检索已 async / 线程桥接，`service/widgets` 100% async；
  但 `agent_runtime`（聊天 ReAct 执行）、知识库上传/入库/重建/诊断、任务 Worker 主体仍是同步实现。
  详见 `docs/sync-async-boundary.md`。
- service 层内部零散的 `raise ValueError` / 裸 `Exception` 尚未全部换成领域异常（路由层已在 `except` 里翻译）。
- 压力测试还未在真实服务器上形成基准报告；`/metrics` 缺生产压测基线和告警规则。
- 外部服务熔断目前是进程内状态，多 API/Worker 实例不共享全局熔断。
- 备份命令已给出，但还需在真实部署环境做恢复演练。
- 数据库迁移已建立骨架，但模型定义和数据库初始化尚未拆分，暂不适合直接开启 Alembic 自动生成。

## 下一步建议

1. `agent_runtime` async 迁移：先出分阶段、可回滚的设计文档，逐层换 + 每层配集成测试。
2. RAG 检索彻底 async（`embedding_service._get_client` / chunk 反查改异步 DAO），退役 `async_search`。
3. service 层内部异常逐模块换成 `service/exceptions.py` 领域异常。
4. 真实服务器压力测试基准报告；告警规则接入。
5. 拆分 ORM 模型定义与数据库启动初始化，完成 Alembic 全量接管。
6. 多实例共享熔断状态（接 Redis）。
