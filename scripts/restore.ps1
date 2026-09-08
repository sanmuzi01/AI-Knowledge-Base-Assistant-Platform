param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [switch]$RestoreFiles
)

$ErrorActionPreference = "Stop"

function Require-Command($Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "缺少命令：$Name"
    }
}

function Ensure-ChildPath($Base, $Path) {
    $baseFull = [System.IO.Path]::GetFullPath($Base)
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($baseFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "路径越界，拒绝恢复：$Path"
    }
}

Require-Command "docker"

if (-not (Test-Path $BackupDir)) {
    throw "备份目录不存在：$BackupDir"
}

$backupFull = [System.IO.Path]::GetFullPath($BackupDir)
$mysqlDump = Join-Path $backupFull "mysql.sql"
if (-not (Test-Path $mysqlDump)) {
    throw "备份目录缺少 mysql.sql：$mysqlDump"
}

Write-Host "恢复 MySQL..."
Get-Content -Path $mysqlDump -Raw | docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'

if ($RestoreFiles) {
    Write-Host "恢复应用文件..."
    $paths = @(
        "knowledge_files",
        "vector_db",
        "logs",
        "skills",
        "skills_packages",
        "prompt\prompts"
    )

    $workspace = [System.IO.Path]::GetFullPath((Get-Location).Path)
    foreach ($path in $paths) {
        $source = Join-Path $backupFull $path
        if (-not (Test-Path $source)) {
            continue
        }
        $target = Join-Path $workspace $path
        Ensure-ChildPath $workspace $target
        if (Test-Path $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        New-Item -ItemType Directory -Path (Split-Path $target -Parent) -Force | Out-Null
        Copy-Item -Path $source -Destination $target -Recurse -Force
    }
}

Write-Host "恢复完成"
