# Project Architecture

本文档用于说明当前项目的整体结构、技术栈和主要业务链路。后续新增功能时，优先保持这里定义的分层方式。

## 1. 项目定位

本项目是一个私人 AI Agent 平台，核心能力包括：

- 用户注册、登录、管理员后台
- 模型配置和 API Key 管理
- Agent 创建、调试、运行
- Skill 创建、导入、绑定
- 个人知识库、网页抓取、RAG 检索
- 长期记忆和用户画像
- 后台任务、操作日志、系统诊断
- Redis 缓存（内存兜底）、Prometheus `/metrics` 指标

## 2. 技术栈

| 层级 | 技术 | 作用 |
| --- | --- | --- |
| 前端 | Vue 3 + Vite + TypeScript | 用户界面、管理后台、任务中心 |
| 样式 | Tailwind CSS + lucide icons | 页面布局、图标和交互状态 |
| 后端 | FastAPI | HTTP API、认证、业务路由 |
| 数据库 | MySQL | 持久化用户、Agent、知识库、任务、日志 |
| ORM | SQLAlchemy | 同步数据库访问 |
| 异步 ORM | SQLAlchemy Async + asyncmy | 高频读取接口异步化 |
| 缓存 | Redis，内存兜底 | 配置缓存、验证码、限流、并发控制 |
| 向量库 | Chroma | 知识库向量检索 |
| 后台任务 | 独立 Worker | 文档入库、重建索引、组件定时调度等 |
| 部署 | 进程管理器 + Nginx | uvicorn / worker 常驻，Nginx 托管前端 + 反代 |
| 监控 | Prometheus `/metrics` | 指标端点，可接入已有 Prometheus/Grafana |

## 3. 后端分层

后端代码按以下职责划分：

| 目录 | 职责 |
| --- | --- |
| `FasdtApi/` | 路由层，接收请求、校验参数、调用 Service |
| `service/` | 业务层，处理业务规则、任务编排、缓存、外部服务 |
| `models/` | ORM 模型和 DAO，负责数据库访问 |
| `utils/` | 通用工具，例如缓存、限流、日志 |
| `migrations/` | Alembic 数据库迁移入口 |
| `scripts/` | 启动、测试、备份、压测、发布检查脚本 |
| `tests/` | 单元测试和基础回归测试 |

推荐调用方向：

```text
FasdtApi 路由
  -> service 业务服务
    -> models DAO
      -> MySQL / Redis / Chroma / 外部模型 API
```

路由层不直接写复杂 SQL，不直接拼业务流程。Service 负责业务语义，DAO 负责数据访问。

## 4. 异步设计

当前策略是“高频读取优先异步化，写入链路保持事务稳定”。

已经异步优先的典型接口：

- 用户登录、注册、当前用户信息、用户面板
- 模型配置列表和连通性测试
- Agent 列表和详情
- 会话列表、消息列表
- 知识库列表、详情、切片
- 后台任务列表和详情
- 管理员统计、任务、日志
- 长期记忆读取、旧聊天历史读取、用户画像读取

异步数据库入口在：

```text
models/async_db.py
```

如果安装了 `asyncmy`，接口优先走异步连接池；如果本地缺少驱动，会自动回退同步数据库访问，避免开发环境崩溃。

## 5. 后台任务流程

上传文档、网页抓取、重建索引等耗时操作不会在 API 请求里直接做完，而是进入后台任务队列。

```text
用户提交任务
  -> API 写入 background_task 表
  -> 前端立即显示任务状态
  -> Worker 领取 queued 任务
  -> Worker 执行解析、Embedding、向量入库
  -> 更新任务进度和结果
```

关键文件：

```text
FasdtApi/background_task.py
service/background_task_service.py
service/background_worker.py
models/background_task_dao.py
```

Worker 已支持：

- 多 Worker 数据库行锁领取任务
- running 超时任务自动重新排队
- 失败任务自动延迟重试
- 最大自动重试次数
- 手动取消和手动重试

## 6. Redis 和缓存

Redis 用于跨进程共享状态：

- 模型配置缓存
- Skill 配置缓存
- 手机验证码缓存
- 请求限流
- 用户并发任务控制

关键文件：

```text
utils/redis_client.py
utils/cache.py
utils/rate_limit.py
service/phone_verification_service.py
```

Redis 不可用时会回退到内存；达到 `REDIS_RECONNECT_INTERVAL_SECONDS` 后自动尝试恢复连接。

## 7. RAG 知识库流程

```text
上传文档或抓取网页
  -> 创建 Knowledge 记录
  -> 创建 background_task
  -> Worker 解析文件
  -> 文本切片
  -> 调用 Embedding 模型
  -> 写入 Chroma 向量库
  -> 用户检索时召回相关片段
  -> 拼入大模型上下文生成回答
```

关键文件：

```text
FasdtApi/knowledge.py
service/rag/rag_service.py
service/rag/embedding_service.py
service/rag/vector_store_service.py
service/web_crawler_service.py
```

## 8. 管理后台

管理员后台用于上线后的系统管控：

- 用户管理
- 用户状态和角色
- 后台任务查看
- 操作日志
- 使用统计
- 系统诊断

关键文件：

```text
FasdtApi/admin.py
service/admin_service.py
service/admin_async_service.py
service/operation_log_middleware.py
service/operation_log_service.py
frontend/src/views/admin/
```

内置管理员：

```text
用户名：ADMIN_USERNAME（默认 admin）
密码：ADMIN_PASSWORD（未配置时首次启动会随机生成，仅在启动日志打印一次）
```

账号只在不存在时创建，已存在的管理员账号不会在每次启动时被静默重置密码；
如需找回密码，临时设置 `ADMIN_PASSWORD_RESET=true` 并配合 `ADMIN_PASSWORD` 启动一次即可覆盖，用完记得改回 `false`。
生产环境（`APP_ENV=production`）启动校验会强制要求 `ADMIN_PASSWORD` 已配置且不是弱密码，否则拒绝启动。
详见 `models/init_db.py` 的 `_ensure_builtin_admin()` 和 `service/config_validation.py`。

## 9. 启动方式

本地开发常用：

```powershell
npm run backend:dev
npm run frontend:dev
npm run backend:worker
```

依赖与部署说明见：

```text
docs/startup-guide.md
docs/deployment.md
```

## 10. 后续开发约定

新增功能建议遵守：

- 路由只做参数、权限、响应，不堆复杂业务
- 业务规则放 `service/`
- 数据库查询放 `models/*_dao.py`
- 高频读取如果需要异步，新增 `*_async_dao.py` 和 `*_async_service.py`
- 耗时任务进入 Worker，不阻塞 API 请求
- 涉及用户频率、并发、验证码、缓存，优先使用 Redis 工具
- 每次重要修改后运行 `npm run test:unit` 和 `npm run release:check`
