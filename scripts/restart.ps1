[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.env'))) {
    throw '缺少 .env。请先运行 .\scripts\bootstrap.ps1。'
}
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'compose.yml 校验失败；请检查配置和 .env。' }
docker compose up -d --force-recreate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'AstrBot 与 NapCat 已重新创建并启动；持久化数据保留。'
