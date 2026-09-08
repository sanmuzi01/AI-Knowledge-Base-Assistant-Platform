# Docker 一键启动

这个项目已经整理成 Docker Compose 一键启动方式，适合本地演示、面试交付和 GitHub README 引导。

## 前置要求

- 已安装 Docker Desktop
- Docker Desktop 已启动
- 命令行可以执行 `docker compose version`

## 一键启动

```powershell
npm run docker:start
```

也可以在 Windows 上直接双击：

```text
start-one-click.bat
```

首次启动会自动做这些事：

- 如果没有 `.env.docker`，从 `.env.docker.example` 自动复制一份
- 创建 `knowledge_files`、`vector_db`、`logs` 等持久化目录
- 构建并启动 MySQL、Redis、后端 API、后台 Worker、前端 Nginx
- 等待后端健康检查，并打印访问地址

## 访问地址

```text
前端：http://localhost:8080
后端：http://localhost:8000
健康检查：http://localhost:8000/health
```

## 停止服务

```powershell
npm run docker:stop
```

也可以双击：

```text
stop-one-click.bat
```

## 常用排查命令

查看容器状态：

```powershell
docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml ps
```

查看后端日志：

```powershell
docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml logs -f api
```

查看前端日志：

```powershell
docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml logs -f frontend
```

## 正式部署前要改

`.env.docker` 里的默认值是本地演示配置。正式部署前至少修改：

- `DB_PASSWORD`
- `JWT_SECRET_KEY`
- `LLM_ENCRYPTION_KEY`
- `TRUSTED_HOSTS`
- `CORS_ALLOW_ORIGINS`
- `SMS_PROVIDER` 相关配置
