# Startup Guide

本文档说明项目的本地开发启动、Docker 一键启动和分步式微服务启动。

## 1. 本地开发启动

在项目根目录执行：

```powershell
cd D:\PyCharm\PythonProject1
```

启动后端 API：

```powershell
npm run backend:dev
```

启动前端：

```powershell
npm run frontend:dev
```

启动后台 Worker：

```powershell
npm run backend:worker
```

访问地址：

```text
前端：http://localhost:5173
后端：http://127.0.0.1:8000
健康检查：http://127.0.0.1:8000/health
```

## 2. Docker 一键启动

如果只想快速启动全部服务：

```powershell
docker compose up -d --build
```

查看状态：

```powershell
docker compose ps
```

停止全部服务：

```powershell
docker compose down
```

## 3. 分步式启动

分步式启动适合上线排查和逐层验证。

### 3.1 启动基础设施

启动 MySQL 和 Redis：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-infra.ps1
```

对应 Compose 文件：

```text
docker-compose.infra.yml
```

### 3.2 启动应用服务

启动 API、Worker、Frontend：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-app.ps1
```

对应 Compose 文件：

```text
docker-compose.app.yml
```

### 3.3 启动监控服务

启动 Prometheus 和 Grafana：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-monitoring.ps1
```

对应 Compose 文件：

```text
docker-compose.monitoring.yml
```

### 3.4 启动全部分步服务

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
```

### 3.5 停止应用但保留数据库

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-app.ps1
```

这会停止：

```text
frontend
api
worker
prometheus
grafana
```

不会停止 MySQL 和 Redis。

### 3.6 停止全部服务

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-all.ps1
```

这会停止并移除容器，但保留 Docker volume 数据。

## 4. 推荐上线启动顺序

```text
1. start-infra.ps1
2. 等待 MySQL / Redis 健康
3. start-app.ps1
4. 打开 /health 检查 API、Redis、数据库、Worker 配置
5. start-monitoring.ps1
6. 打开 Grafana 查看指标
```

## 5. 常见问题

### npm run dev 报 package.json 不存在

原因通常是命令不在项目根目录或前端目录执行。

正确方式：

```powershell
cd D:\PyCharm\PythonProject1
npm run frontend:dev
```

### Vite 提示 ECONNREFUSED 127.0.0.1:8000

说明前端启动了，但后端 API 没启动。

先启动：

```powershell
npm run backend:dev
```

### 8000 端口被占用

查看占用：

```powershell
netstat -ano | findstr :8000
```

结束对应进程前，请确认不是你正在使用的服务。

### 文档一直显示处理中

检查：

```powershell
npm run backend:worker
```

或者打开管理后台的系统诊断页，看 Worker 模式、Redis、数据库连接是否正常。
