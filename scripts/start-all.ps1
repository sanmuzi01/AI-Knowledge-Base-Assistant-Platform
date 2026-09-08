$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..")

if (-not (Test-Path ".env.docker")) {
    throw "未找到 .env.docker。请先运行 npm run docker:start 自动生成，或复制 .env.docker.example 为 .env.docker。"
}

docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.monitoring.yml up -d --build
docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.monitoring.yml ps
