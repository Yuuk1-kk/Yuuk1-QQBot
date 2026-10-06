[CmdletBinding()]
param(
    [switch]$IncludeQQSession
)

$ErrorActionPreference = 'Stop'
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
Set-Location -LiteralPath $repoRoot

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        docker compose version *> $null
        if ($LASTEXITCODE -ne 0) {
            throw 'Docker Engine 正在运行，但 Compose v2 不可用；无法确认服务已停止。'
        }
        $running = @(docker compose ps --services --filter 'status=running' 2>$null)
        if ($LASTEXITCODE -ne 0) {
            throw '无法确认 Compose 服务是否已停止；备份已取消。'
        }
        if ($running.Count -gt 0) {
            throw '请先运行 .\scripts\stop.ps1 停止服务，再创建一致的备份。'
        }
    }
}

$sourceDirs = @('data/astrbot', 'data/napcat/config')
if ($IncludeQQSession) { $sourceDirs += 'data/napcat/qq' }

$files = foreach ($relativeDir in $sourceDirs) {
    $sourcePath = Join-Path $repoRoot $relativeDir
    if (Test-Path -LiteralPath $sourcePath -PathType Container) {
        Get-ChildItem -LiteralPath $sourcePath -File -Recurse -Force | Where-Object {
            $relativeFile = [System.IO.Path]::GetRelativePath($repoRoot, $_.FullName)
            (($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) -and
            $relativeFile -notmatch '(^|[/\\])(logs?|cache|tmp|temp|__pycache__)([/\\]|$)' -and
            $_.Extension -notin @('.log', '.tmp')
        }
    }
}

if (-not $files) {
    Write-Warning '没有可备份的持久化文件；尚未启动的部署无需生成空备份。'
    exit 1
}

$backupDir = Join-Path $repoRoot 'backups'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archivePath = Join-Path $backupDir "yuuk1-data-$stamp.zip"
$partialPath = "$archivePath.partial"
if ((Test-Path -LiteralPath $archivePath) -or (Test-Path -LiteralPath $partialPath)) {
    throw '该时间戳的备份文件已存在；请稍后重试，现有文件未被覆盖。'
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($partialPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($file in $files) {
        $entryName = [System.IO.Path]::GetRelativePath($repoRoot, $file.FullName).Replace('\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $file.FullName,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
} finally {
    $archive.Dispose()
}

$resolvedBackupDir = [System.IO.Path]::GetFullPath($backupDir)
$resolvedPartial = [System.IO.Path]::GetFullPath($partialPath)
$resolvedArchive = [System.IO.Path]::GetFullPath($archivePath)
foreach ($path in @($resolvedPartial, $resolvedArchive)) {
    if (-not $path.StartsWith($resolvedBackupDir + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw '备份输出路径超出本仓库 backups 目录。'
    }
}
[System.IO.File]::Move($resolvedPartial, $resolvedArchive)

Write-Host "[PASS] 已创建备份：$archivePath"
Write-Host "[PASS] 已包含 $(@($files).Count) 个持久化文件；备份包含敏感配置，请离线妥善保管。"
if (-not $IncludeQQSession) {
    Write-Host '[WARN] 未包含 QQ 登录态。若需要同时保留登录态，使用 -IncludeQQSession。'
}
