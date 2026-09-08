# Production Deployment

项目生产环境由七个服务组成：

- `frontend`: Nginx 静态前端和 `/api` 反向代理
- `api`: FastAPI 对外接口
- `worker`: 后台任务 Worker，处理知识库入库和重建索引
- `mysql`: 主数据库
- `redis`: 分布式缓存、限流和并发控制
- `prometheus`: 指标采集
- `grafana`: 指标看板

## 1. 准备配置

复制生产模板并填写真实密钥：

```powershell
Copy-Item .env.production.example .env
```

必须修改：

- `DB_PASSWORD`
- `JWT_SECRET_KEY`
- `LLM_ENCRYPTION_KEY`
- `SMS_WEBHOOK_URL`
- `SMS_WEBHOOK_TOKEN`
- `GRAFANA_ADMIN_PASSWORD`
- `TRUSTED_HOSTS`
- `CORS_ALLOW_ORIGINS`

`LLM_ENCRYPTION_KEY` 需要是 Fernet key，可用下面命令生成：

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

短信验证码生产环境使用通用 Webhook：

```env
SMS_PROVIDER=webhook
SMS_WEBHOOK_URL=https://your-sms-gateway.example.com/send
SMS_WEBHOOK_TOKEN=change-me-sms-webhook-token
```

接口会向 `SMS_WEBHOOK_URL` 发送 `phone`、`code`、`ttl_seconds`、`scene` 四个字段。`SMS_PROVIDER=console` 只适合本地开发，验证码会写入后端日志；只有显式配置 `SMS_EXPOSE_DEV_CODE=1` 时才会把验证码返回给前端，不要在生产环境开启。

## 2. 启动

```powershell
docker compose up -d --build
```

查看状态：

```powershell
docker compose ps
```

查看日志：

```powershell
docker compose logs -f api
docker compose logs -f worker
```

## 3. 健康检查

浏览器访问：

```text
http://localhost/health
```

正常情况下：

- `database` 为正常
- `redis` 为正常
- `tasks.execution_mode` 为 `worker`
- `tasks.worker_required` 为 `true`
- `database.pool.checked_out` 不应长期接近 `DB_POOL_SIZE + DB_MAX_OVERFLOW`

Prometheus 指标端点：

```text
http://localhost/metrics
```

Prometheus 控制台：

```text
http://localhost:9090
```

Grafana 控制台：

```text
http://localhost:3000
```

Grafana 默认数据源会自动指向 Prometheus。生产环境必须修改 `GRAFANA_ADMIN_PASSWORD`。
内置 `Agent Platform Overview` 看板会展示 HTTP 吞吐、P95/P99 延迟、5xx 错误、数据库连接池和缓存后端状态。
Prometheus 已内置基础告警规则：API 不可用、5xx 增多、P95 延迟过高、数据库连接池接近打满。

数据库连接池说明：

```env
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_POOL_PRE_PING=true
```

同步数据库链路使用 `mysql+pymysql`，异步读取链路使用 `mysql+asyncmy`。两条链路复用同一组连接池参数，生产环境安装 `requirements.txt` 后会自动启用异步读取；本地未安装 `asyncmy` 时接口会回退到原同步查询，避免开发环境直接崩溃。

安全相关配置：

```env
TRUSTED_HOSTS=your-domain.com,www.your-domain.com,api
CORS_ALLOW_ORIGINS=https://your-domain.com,https://www.your-domain.com
MAX_REQUEST_BODY_BYTES=52428800
ENABLE_HSTS=1
```

`TRUSTED_HOSTS` 控制允许访问后端的 Host，`CORS_ALLOW_ORIGINS` 控制浏览器跨域来源。生产环境不要配置成 `*`。只有站点已经启用 HTTPS 时才开启 `ENABLE_HSTS=1`。

外部服务韧性配置：

```env
HTTP_CLIENT_MAX_RETRIES=2
HTTP_CLIENT_RETRY_BASE_SECONDS=0.3
HTTP_CIRCUIT_FAILURE_THRESHOLD=5
HTTP_CIRCUIT_COOLDOWN_SECONDS=30
LLM_REQUEST_TIMEOUT_SECONDS=60
LLM_STREAM_TIMEOUT_SECONDS=60
EMBEDDING_REQUEST_TIMEOUT_SECONDS=30
```

普通 LLM/Embedding 请求会在超时、连接失败或 429/5xx 时重试；流式输出不会自动重试，避免用户已经收到部分内容后重复输出。连续失败达到阈值后会短暂熔断，熔断状态可在 `/health` 的 `resilience.circuits` 中查看。

数据库连接池默认配置：

```env
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_POOL_PRE_PING=true
```

`API_WORKERS` 会放大总连接数。例如 `API_WORKERS=2` 时，API 服务理论最大连接数约为 `(DB_POOL_SIZE + DB_MAX_OVERFLOW) * 2`，再加上 Worker 进程自己的连接。生产调大这些值前，要确认 MySQL 的 `max_connections` 足够。

## 4. Worker 扩容

后台任务多时，可以增加 Worker 数量：

```powershell
docker compose up -d --scale worker=2
```

Worker 会通过数据库领取 `queued` 任务，避免多个 Worker 重复执行同一个任务。

Worker 失败重试配置：

```env
TASK_MAX_AUTO_RETRIES=2
TASK_RETRY_BASE_SECONDS=30
TASK_RETRY_MAX_SECONDS=300
```

任务失败后不会立刻反复执行，而是按退避时间写入 `next_run_at`，到时间后再由 Worker 领取。超过 `TASK_MAX_AUTO_RETRIES` 后任务进入 `failed` 终态，管理员或用户可以在任务中心手动重试。

Redis 连接恢复配置：

```env
REDIS_RECONNECT_INTERVAL_SECONDS=5
```

缓存、验证码、限流和并发控制都会优先使用 Redis。Redis 短暂不可用时接口会回退到进程内内存；到达重连间隔后会自动尝试恢复 Redis，不需要重启 API。

## 5. 数据持久化

数据库和 Redis 使用 Docker volume：

- `mysql_data`
- `redis_data`

应用文件使用项目目录挂载：

- `knowledge_files`
- `vector_db`
- `logs`
- `skills`
- `skills_packages`
- `prompt/prompts`

上线迁移服务器时，这些目录和 Docker volume 都需要备份。

手动备份：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1
```

恢复说明见 `docs/backup-restore.md`。

## 6. 开发临时模式

生产推荐：

```env
TASK_EXECUTION_MODE=worker
```

如果只是本地快速测试，不想单独启动 Worker，可以临时改为：

```env
TASK_EXECUTION_MODE=fastapi
```

不要在生产环境使用 `fastapi` 模式执行重任务。
