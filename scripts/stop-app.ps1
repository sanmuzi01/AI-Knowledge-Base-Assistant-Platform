$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..")

docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.monitoring.yml stop frontend api worker prometheus grafana
docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml -f docker-compose.monitoring.yml ps
