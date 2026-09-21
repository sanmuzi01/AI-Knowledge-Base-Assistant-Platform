# Production Deployment

生产环境按进程部署，用进程管理器（systemd / supervisor / nssm 等）常驻：

- `api`: FastAPI 对外接口 —— `uvicorn FasdtApi.main:app --host 0.0.0.0 --port 8000 --workers 2`
- `worker`: 后台任务 Worker（知识库入库 / 重建索引、自定义组件定时调度）—— `python -m service.background_worker`
- 前端：`npm run frontend:build` 产出 `frontend/dist`，交给 Nginx 做静态托管 + `/api` 反向代理
- `mysql`: 主数据库（自建或云 RDS）
- `redis`: 分布式缓存、限流和并发控制（可选，不配则回退进程内内存）
- `chroma`: 向量库 Server（`pip install chromadb` 自带的 `chroma run` 命令，或用官方镜像单独跑）。
  `api` 用 `--workers 2` 起了多个进程，加上独立的 `worker` 进程，至少 3 个进程会同时碰向量库；
  ChromaDB 内嵌的 `PersistentClient` 不保证多进程并发读写安全，生产必须设置
  `CHROMA_SERVER_HOST`/`CHROMA_SERVER_PORT` 走 Server 模式，不要只填 `VECTOR_DB_PATH`。

  ```bash
  chroma run --path /data/chroma_db --port 8000    # 用 systemd/supervisor 常驻
  ```

## 1. 准备配置

复制生产模板并填写真实密钥：

```powershell
Copy-Item .env.production.example .env
```

必须修改：

- `DB_PASSWORD`
- `JWT_SECRET_KEY`
- `LLM_ENCRYPTION_KEY`
- `ALIBABA_CLOUD_ACCESS_KEY_ID` / `ALIBABA_CLOUD_ACCESS_KEY_SECRET`（使用阿里云短信认证时）
- `SMS_ALIYUN_SIGN_NAME` / `SMS_ALIYUN_TEMPLATE_CODE`（使用阿里云短信认证时）
- `TRUSTED_HOSTS`
- `CORS_ALLOW_ORIGINS`

`LLM_ENCRYPTION_KEY` 需要是 Fernet key，可用下面命令生成：

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

个人账号可使用阿里云号码认证服务的短信认证。选用控制台提供的系统签名和模板，
使用只授予 `dypns:SendSmsVerifyCode` 的 RAM 用户密钥；项目生成并校验验证码：

```env
SMS_PROVIDER=aliyun
ALIBABA_CLOUD_ACCESS_KEY_ID=change-me-ram-access-key-id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=change-me-ram-access-key-secret
SMS_ALIYUN_SIGN_NAME=change-me-system-sign-name
SMS_ALIYUN_TEMPLATE_CODE=change-me-system-template-code
```

已有自建短信网关也可使用通用 Webhook：

```env
SMS_PROVIDER=webhook
SMS_WEBHOOK_URL=https://your-sms-gateway.example.com/send
SMS_WEBHOOK_TOKEN=change-me-sms-webhook-token
```

接口会向 `SMS_WEBHOOK_URL` 发送 `phone`、`code`、`ttl_seconds`、`scene` 四个字段。`SMS_PROVIDER=console` 只适合本地开发，验证码会写入后端日志；只有显式配置 `SMS_EXPOSE_DEV_CODE=1` 时才会把验证码返回给前端，不要在生产环境开启。

## 2. 启动

全新数据库先执行项目初始化入口（建表、补齐字段、创建管理员）：

```powershell
python -m models.init_db
```

Alembic 的基线版本只给已有表打标记，不会在空库建 `user` 表；不要在空库直接运行
`alembic upgrade head`。现有初始化与 Alembic 迁移尚未统一，后续新增迁移需先处理基线。

常驻两个进程（交给 systemd / supervisor / nssm）：

```text
uvicorn FasdtApi.main:app --host 0.0.0.0 --port 8000 --workers 2
python -m service.background_worker
```

前端构建产物由 Nginx 托管，`/api` 反代到 `127.0.0.1:8000`，`/health`、`/metrics` 同样透传。
仓库 `deploy/` 下有可直接改用的模板（均按「与 API 同机」预设，非容器）：

- `deploy/nginx.conf` —— 静态托管 + `/api`、`/health`、`/metrics` 反代（把 `root` 指向 `frontend/dist`）
- `deploy/prometheus.yml` + `deploy/prometheus-rules.yml` —— 抓 `127.0.0.1:8000/metrics`
- `deploy/grafana/provisioning/` —— Grafana 数据源与预置面板

## 3. 健康检查

`/health` 是公开的、不需要登录的探活端点，只回 `{"ok": true/false}`，给 Docker
healthcheck、负载均衡这类不带登录态的场景用：

```text
http://<域名>/health
```

数据库连接池、缓存/限流用的是不是 Redis、后台任务执行模式这些运行细节
**不再从 `/health` 公开**——这些是内部架构信息，之前任何知道这个 URL 的匿名
请求都能看到，属于不必要的踩点信息暴露。完整诊断现在需要登录，走
`/system/diagnose`（同一份数据也能在产品里看：普通用户在「设置」页，
管理员在后台「系统诊断」页）：

- `database` 为正常
- `redis` 为正常（未配置 Redis 时为回退内存模式）
- `tasks.execution_mode` 为 `worker`
- `tasks.worker_required` 为 `true`
- `database.pool.checked_out` 不应长期接近 `DB_POOL_SIZE + DB_MAX_OVERFLOW`

Prometheus 指标端点：`http://<域名>/metrics`（可接入已有的 Prometheus / Grafana）。
`/metrics` 目前也是公开的，生产环境建议在反向代理层限制只允许内网/监控系统访问。

数据库连接池说明：

```env
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_POOL_PRE_PING=true
```

同步数据库链路使用 `mysql+pymysql`，异步读取链路使用 `mysql+asyncmy`。两条链路复用同一组连接池参数。`asyncmy` 是硬依赖（`requirements.txt` 固定版本，`models/async_db.py` 缺驱动会直接启动失败），已不再保留「未装 asyncmy 时回退同步查询」的旧分支；纯读接口全量走 AsyncSession，写入 / RAG 检索链路仍是同步（见 `docs/sync-async-boundary.md`）。

安全相关配置：

```env
TRUSTED_HOSTS=your-domain.com,www.your-domain.com
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

`API_WORKERS`（或 `--workers`）会放大总连接数。例如 2 个 worker 时，API 服务理论最大连接数约为 `(DB_POOL_SIZE + DB_MAX_OVERFLOW) * 2`，再加上后台 Worker 进程自己的连接。生产调大这些值前，要确认 MySQL 的 `max_connections` 足够。

## 4. Worker 扩容

后台任务多时，可以多起几个 `python -m service.background_worker` 进程。Worker 会通过数据库领取 `queued` 任务，多个 Worker 不会重复执行同一个任务；自定义组件的定时调度也用同样的乐观锁抢占。

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

## 5. 数据持久化与备份

需要纳入备份的：

- MySQL：定期导出

  ```powershell
  mysqldump -u root -p --single-transaction --routines --triggers agent_sql > backup/agent_sql_$(Get-Date -Format yyyyMMdd_HHmm).sql
  ```

  恢复：

  ```powershell
  mysql -u root -p agent_sql < backup/agent_sql_20260101_0000.sql
  ```

- 应用文件目录：`knowledge_files`、`vector_db`、`logs`、`skills`、`skills_packages`、`prompt/prompts`。

迁移服务器时，数据库导出文件和上述目录一起打包带走即可。

以上手动步骤已经包装成 `scripts/backup.py`（`npm run backup`），可以直接丢进 cron /
Windows 计划任务定时跑，会在 `backups/` 下生成一份 `db_*.sql` + `data_*.tar.gz`：

```bash
.venv/Scripts/python.exe scripts/backup.py --keep-days 14   # 顺带清理 14 天前的旧备份
```

Docker Compose 部署时，Chroma 数据在 `chroma_data` 具名卷里，不在上面的脚本覆盖范围，
单独备份：

```bash
docker run --rm -v pythonproject1_chroma_data:/data -v "$PWD/backups":/backup \
  alpine tar czf /backup/chroma_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
```

（卷名前缀跟你项目目录名有关，跑 `docker volume ls` 确认实际名字。）

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

## 7. Skill 脚本沙箱（可选，默认关闭）

> 现状、保留的内容和后续扩展路线见 [skill-extension.md](skill-extension.md)。

导入的官方 Skill 常带 `scripts/*.py`。开启沙箱后，助手可以用 `run_skill_script` 工具运行这些 Python 脚本，
用户也能在聊天里上传文件（📎）交给脚本处理，脚本生成的文件会变成下载链接。

**这等于让服务器执行陌生人写的代码**，所以：默认关闭；只有导入了带脚本的 Skill 并且真有需求再开。

### 隔离措施（都已写在 docker-compose.prod.yml 的 `sandbox` 服务里）

- 单独的容器，只挂在 `internal` 网络 `sandbox_net`：**没有外网出口**，也访问不到 db / redis / chroma / **api / worker**。
- **网关**：api / worker 不在 `sandbox_net` 里，它们通过 `sandbox-gw` 间接调用沙箱。网关同时在默认网络和 `sandbox_net` 上，
  但只把 `GET /health` 和 `POST /run` 转发给固定的上游（沙箱本身）。拓扑：
  `api / worker ──▶ sandbox-gw ──▶ sandbox`，沙箱里的脚本看得到的只有网关，而网关只通向沙箱自己。
  （早期版本让 api / worker 直接挂在 `sandbox_net` 上，脚本能访问到 api 容器，所以加了网关。）
- 不加载 `.env`，容器里没有任何业务密钥；调用用一个独立的 `SANDBOX_TOKEN`。
- 根文件系统只读，可写的只有 tmpfs（重启即清空）；非 root 用户；丢弃全部 Linux capability。
- 上限：1 CPU、1GB 内存、128 个进程、单次最长 30 秒（`SANDBOX_TIMEOUT_SECONDS`，最大 60）、同时最多 2 个脚本。
- 只能运行 `.py`；`.sh` / `.js` 等一律不执行。镜像里没有 Node / LibreOffice，只预装 PDF / Excel / Word / pandas 等常用库（见 `sandbox/requirements.txt`）。

### 开启步骤

```bash
# 1. 生成令牌，写进 .env
python3 -c "import secrets; print(secrets.token_hex(32))"
#    .env 里设置：
#      SANDBOX_ENABLED=true
#      SANDBOX_TOKEN=<上面生成的值>

# 2. 构建并启动沙箱（profile 里的服务默认不会随 up -d 启动）
docker compose -f docker-compose.prod.yml --profile sandbox up -d --build sandbox sandbox-gw

# 3. 重启 api 和 worker，让它们读到新的环境变量
docker compose -f docker-compose.prod.yml up -d api worker
```

关闭：把 `SANDBOX_ENABLED` 改回 `false`，重启 api / worker；`docker compose ... stop sandbox sandbox-gw` 停掉容器。
关闭后已导入的 Skill 仍在，只是脚本不再运行，助手会按文字说明工作。

### 部署后必须做的验收（一条命令）

本地开发机测不了容器层面的隔离，所以开启后**必须**在服务器上跑一次：

```bash
docker compose -f docker-compose.prod.yml exec api python scripts/sandbox_acceptance.py
```

它会在真实沙箱里逐项检查并给出 PASS / FAIL：沙箱健康、能运行脚本、**非 root**、**连不出外网**（含解析外部域名）、
**连不到 db / redis / chroma / api / worker**、**根文件系统只读**、**环境里没有业务密钥**、死循环会被终止、
超过内存上限的脚本被拒绝、产出文件能带回来、**镜像里声明装了的依赖真的都能 import**、ffmpeg 可用。
退出码 0 = 没有 FAIL。

**任何隔离类的 FAIL（`no_egress`、`no_internal_access`、`readonly_fs`、`env_clean`）都要立刻关闭沙箱**
（`SANDBOX_ENABLED=false`）并排查网络配置。`memory_limit` 会占用较多内存，服务器内存紧张时先加 `--skip-heavy`。

已知且接受的限制（脚本输出里会以 INFO 列出）：脚本能读到沙箱自己的令牌（同一用户可读 `/proc/1/environ`）。
这个令牌只能调用沙箱本身，而网关只通向沙箱，价值有限。

### 附件文件

用户上传的附件和脚本生成的文件存在 `app_data` 卷的 `/app/data/attachments/`，按用户隔离，
默认保留 7 天（`ATTACHMENT_TTL_DAYS`），过期文件在该用户下次上传时清理。

### 谁能带脚本、上架和额度

- **技能只有管理员能维护**：创建、编辑、删除、导入（含 GitHub 链接）、翻译、导出、上架，全部要求管理员。
  普通用户只能看「能力商店」、在创建/编辑助手时**直接绑定**商店里的技能、上传输入文件、使用。
  商店里的都是管理员上架的，标「官方」。**不开放用户自带脚本**；要开放，须先做到文件隔离、依赖管理、审计和配额都完善。
  代码层面有两道：路由要求管理员，导入策略（`skill_route._import_policy`）再按角色判断一次脚本和上架权限。
- 所有用户绑定的是**同一份**技能配置（不再有各人的副本）：管理员改一次全员生效。
  **有版本和回滚**：每次编辑（提示词 / 工具 / 权限 / 名称 / 说明，含翻译）之前会自动保存一份快照，最多留最近 20 个；
  后台技能卡片上的「历史版本」按钮可以一键恢复，恢复前也会先保存当前状态，恢复错了还能再恢复回来。
  快照存在数据库表 `skill_version`（应用启动时自动建表；也有幂等的 Alembic 迁移 `20260921_0007`）。
  恢复不改变是否公开。把技能设为不公开后，已经绑定它的助手仍能继续用；删除技能才会自动解绑（同时清掉它的历史版本）。
- 每个用户默认 60 秒内最多运行 10 次脚本（`SANDBOX_RATE_LIMIT` / `SANDBOX_RATE_WINDOW_SECONDS`）；
  沙箱同时只跑 2 个脚本（全站共用），超出会提示"沙箱正忙"。
- 每人附件总量默认 100MB、最多 50 个文件（`ATTACHMENT_USER_MAX_MB` / `ATTACHMENT_USER_MAX_FILES`），
  脚本生成的文件也占这份额度，满了会明确告诉用户没保存。
- **审计**：每次脚本运行、被限频、沙箱不可用都会记到 `logs/sandbox_audit_*.log`
  （用户、助手、Skill、脚本、参数个数、退出码、耗时、产出文件数）。

### 脚本能不能跑：导入时的静态检查

导入 Skill 时会读一遍每个 `.py` 的 `import`，对照沙箱镜像里装的库，标出：**缺依赖**、**要联网**、**会调系统命令**。
结果显示在技能卡片上：「脚本可运行」/「部分脚本可运行 x/y」/「脚本暂不支持」/「脚本需管理员启用沙箱」，
助手也只会被告知能跑的那些脚本。这是**静态判断**，不等于实测能跑（动态 import、运行时拼出来的命令查不出来），
所以开启沙箱后仍要挑代表性的 Skill 实际跑一遍。

**改沙箱依赖时，两处必须同步**：`sandbox/requirements.txt` 和 `service/skills_core/script_report.py` 里的
`PACKAGE_MODULES`（测试会校验两边一致）。**沙箱里装了什么、有意没装什么**：装了 PDF / Excel / Word / PPT / pandas / numpy / Pillow 这类文件与数据处理库，
以及图像音频视频处理（opencv-headless、imageio-ffmpeg 自带 ffmpeg、scipy、soundfile、pyloudnorm、matplotlib）。
**有意不装**：`moviepy`（官方 Skill 用的 1.0.3 版和新版 Pillow / NumPy 2 有已知不兼容，能实机验证前不装）、`requests` 等联网库（沙箱没有外网，装了只会让脚本跑一半才报错）、torch / transformers 等深度学习库
（要下载模型权重，同样需要网络，而且镜像会大到几个 GB）、Coze / 浏览器自动化这类平台专属 SDK。
想让更多 Skill 能跑，就是往这两处加库、重建沙箱镜像、
然后在后台「技能管理」点「重新检查脚本」刷新检查结果，不用重新导入。

依赖版本：`sandbox/requirements.txt` 里 `==` 的是本地验证过的版本，`>=` 的几个（pdfplumber、reportlab、
python-pptx、beautifulsoup4）首次构建后请用 `docker compose ... run --rm sandbox pip freeze` 补成精确版本；
镜像里也有一份 `/opt/installed-packages.txt` 记录实际装了什么。

### 内存

沙箱容器上限 1GB，会和 MySQL、向量库、API、Worker 同机运行。开启前先确认服务器可用内存足够
（2 核 4G 的机器建议把沙箱内存上限降到 512MB，并观察一段时间）。
