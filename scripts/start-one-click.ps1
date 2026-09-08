$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..")

function Require-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Command not found: $Name. Please install Docker Desktop and make sure docker is available."
    }
}

Require-Command "docker"

docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon is not running. Please start Docker Desktop first, then run npm run docker:start again."
}

if (-not (Test-Path ".env.docker")) {
    Copy-Item ".env.docker.example" ".env.docker"
    Write-Host "Created .env.docker from .env.docker.example. Change secrets before production." -ForegroundColor Yellow
}

foreach ($dir in @("knowledge_files", "vector_db", "logs", "skills", "skills_packages", "prompt/prompts")) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

$composeFiles = @(
    "--env-file", ".env.docker",
    "-f", "docker-compose.infra.yml",
    "-f", "docker-compose.app.yml"
)

Write-Host "Building and starting MySQL, Redis, API, worker and frontend..." -ForegroundColor Cyan
docker compose @composeFiles up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed. Please check Docker Desktop and container logs."
}

Write-Host "Waiting for backend health check..." -ForegroundColor Cyan
$healthy = $false
for ($i = 1; $i -le 40; $i++) {
    try {
        $response = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/health" -TimeoutSec 3
        if ($response.ok -eq $true) {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}

docker compose @composeFiles ps

if (-not $healthy) {
    Write-Host "Backend is not healthy yet. Check logs: docker compose --env-file .env.docker -f docker-compose.infra.yml -f docker-compose.app.yml logs -f api" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "Started successfully." -ForegroundColor Green
    Write-Host "Frontend: http://localhost:8080"
    Write-Host "Backend:  http://localhost:8000"
    Write-Host "Health:   http://localhost:8000/health"
}
