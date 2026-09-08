$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..")

$composeFiles = @(
    "--env-file", ".env.docker",
    "-f", "docker-compose.infra.yml",
    "-f", "docker-compose.app.yml"
)

docker compose @composeFiles down
Write-Host "Docker runtime stopped. Data volumes are kept. Remove Docker volumes manually if you need a clean database." -ForegroundColor Green
