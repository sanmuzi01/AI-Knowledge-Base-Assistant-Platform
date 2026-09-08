param(
    [string]$OutputDir = "backups",
    [string]$ProjectName = "agent-platform"
)

$ErrorActionPreference = "Stop"

function Require-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "缺少命令：$Name"
    }
}

Require-Command "docker"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $OutputDir "$ProjectName-$timestamp"
$archivePath = "$backupRoot.zip"

New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

Write-Host "备份 MySQL..."
docker compose exec -T mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE"' > (Join-Path $backupRoot "mysql.sql")

Write-Host "备份应用文件..."
$paths = @(
    "knowledge_files",
    "vector_db",
    "logs",
    "skills",
    "skills_packages",
    "prompt\prompts"
)

foreach ($path in $paths) {
    if (Test-Path $path) {
        $target = Join-Path $backupRoot $path
        New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
        Copy-Item -Path $path -Destination $target -Recurse -Force
    }
}

@{
    project = $ProjectName
    created_at = (Get-Date).ToString("o")
    includes = $paths
} | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $backupRoot "manifest.json") -Encoding UTF8

Write-Host "压缩备份包..."
if (Test-Path $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
Compress-Archive -Path (Join-Path $backupRoot "*") -DestinationPath $archivePath

Write-Host "备份完成：$archivePath"
