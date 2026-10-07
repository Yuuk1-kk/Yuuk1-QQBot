[CmdletBinding()]
param([switch]$AllowQRRelogin)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.env'))) {
    throw '缺少 .env。请先运行 .\scripts\bootstrap.ps1。'
}
$qqDataPath = Join-Path $repoRoot 'data/napcat/qq'
if (-not (Test-Path -LiteralPath $qqDataPath -PathType Container)) {
    throw 'NapCat QQ 持久化目录不存在；请先运行 .\scripts\bootstrap.ps1。'
}
$qqClientDataPath = Join-Path $qqDataPath 'nt_qq'
$qqClientDataPresent = (Test-Path -LiteralPath $qqClientDataPath -PathType Container) -and
    [bool](Get-ChildItem -LiteralPath $qqClientDataPath -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)
$quickAccountSelected = $false
try {
    $webUiConfig = Get-Content -LiteralPath (Join-Path $repoRoot 'data/napcat/config/webui.json') -Raw | ConvertFrom-Json
    $quickAccountSelected = -not [string]::IsNullOrWhiteSpace([string]$webUiConfig.autoLoginAccount)
} catch { }
if (-not $AllowQRRelogin -and (-not $quickAccountSelected -or -not $qqClientDataPresent)) {
    throw 'NapCat 自动登录账号或 QQ 持久化数据尚未就绪。重建可能要求再次扫码；请先完成 NapCat WebUI 登录与自动登录账号选择，或明确使用 -AllowQRRelogin。'
}
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'compose.yml 校验失败；请检查配置和 .env。' }
docker compose up -d --force-recreate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'AstrBot 与 NapCat 已重新创建并启动；请运行 .\scripts\doctor.ps1 确认 QQ 自动恢复登录。'
