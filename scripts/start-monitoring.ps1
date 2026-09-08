$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..")

if (-not (Test-Path ".env")) {
    throw "未找到 .env。请先复制 .env.production.example 为 .env，并填写 Grafana 密码等配置。"
}

docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.monitoring.yml up -d prometheus grafana
docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.monitoring.yml ps
