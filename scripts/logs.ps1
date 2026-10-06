[CmdletBinding()]
param(
    [ValidateSet('all', 'astrbot', 'napcat')]
    [string]$Service = 'all',
    [ValidateRange(1, 10000)]
    [int]$Tail = 100
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

if ($Service -eq 'all') {
    docker compose logs --follow --tail $Tail
} else {
    docker compose logs --follow --tail $Tail $Service
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
