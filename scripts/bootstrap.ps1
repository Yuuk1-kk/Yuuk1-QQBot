[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$envPath = Join-Path $repoRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot '.env.example') -Destination $envPath
    Write-Host '[PASS] 已创建本地 .env，占位值尚需用户填写。'
} else {
    Write-Host '[PASS] 已保留现有 .env。'
}

@(
    'data/astrbot/plugins',
    'data/astrbot/config',
    'data/napcat/config',
    'data/napcat/qq',
    'backups'
) | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot $_) | Out-Null
}
Write-Host '[PASS] 本地数据和备份目录已就绪。'

$keyLine = Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^\s*DEEPSEEK_API_KEY\s*=' } | Select-Object -Last 1
$keyConfigured = $false
if ($keyLine -match '^\s*DEEPSEEK_API_KEY\s*=(.*)$') {
    $keyValue = $Matches[1].Trim().Trim('"').Trim("'")
    $keyConfigured = [bool]($keyValue -and $keyValue -notmatch '^(replace-me|your[_-].*|<.*>)$')
}
if ($keyConfigured) {
    Write-Host '[PASS] DEEPSEEK_API_KEY 已设置（内容不显示）。'
} else {
    Write-Host '[MANUAL] 在忽略的 .env 中填写真实 DEEPSEEK_API_KEY。'
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error '[FAIL] 未找到 Docker CLI。请安装 Docker Desktop、启用 Linux containers，重新打开 PowerShell 后运行本脚本。未自动安装系统软件。' -ErrorAction Continue
    exit 2
}
Write-Host '[PASS] Docker CLI 已安装。'

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error '[FAIL] 当前 Docker 未提供 Compose v2。请更新 Docker Desktop。' -ErrorAction Continue
    exit 3
}
Write-Host '[PASS] Docker Compose v2 可用。'

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error '[FAIL] Docker Engine 未运行。请启动 Docker Desktop 并确认已切换到 Linux containers，然后重试。' -ErrorAction Continue
    exit 4
}
Write-Host '[PASS] Docker Engine 正在运行。可运行 .\scripts\start.ps1。'
