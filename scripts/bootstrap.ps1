[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw '未找到 Docker CLI。请先安装并启动 Docker Desktop。'
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw '当前 Docker 未提供 Compose v2。请更新 Docker Desktop。'
}

$envPath = Join-Path $repoRoot '.env'
if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $repoRoot '.env.example') -Destination $envPath
    Write-Host '已从 .env.example 创建本地 .env（其中只有占位符，不含真实 Secret）。'
} else {
    Write-Host '已找到本地 .env；未读取或显示其中的 Secret。'
}

@(
    'data/astrbot/plugins',
    'data/astrbot/config',
    'data/napcat/config',
    'data/napcat/qq'
) | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot $_) | Out-Null
}

$keyConfigured = $false
$keyValue = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY')
if ($null -eq $keyValue) {
    $keyLine = Get-Content -LiteralPath $envPath | Where-Object { $_ -match '^\s*DEEPSEEK_API_KEY\s*=' } | Select-Object -Last 1
    if ($keyLine -match '^\s*DEEPSEEK_API_KEY\s*=(.*)$') {
        $keyValue = $Matches[1].Trim().Trim('"').Trim("'")
    }
}
if ($keyValue) {
    $keyConfigured = $keyValue.Length -gt 0 -and $keyValue -notmatch '^(replace-me|your[_-].*|<.*>)$'
}
if ($keyConfigured) {
    Write-Host 'DEEPSEEK_API_KEY 已配置（值已隐藏）。'
} else {
    Write-Warning 'DEEPSEEK_API_KEY 尚未设置。请在 .env 中填入真实密钥；当前不会生成密钥。'
}

docker info *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host 'Docker Engine 正在运行。'
} else {
    Write-Warning 'Docker CLI 和 Compose 已就绪，但 Docker Engine 当前未运行。'
}
Write-Host '本地数据目录已就绪。下一步运行 .\scripts\start.ps1。'
