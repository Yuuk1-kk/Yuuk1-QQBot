[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

docker compose down
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host '服务已停止；持久化数据保留在 data\。'
