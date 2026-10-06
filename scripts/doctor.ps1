[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$failures = 0

function Write-Check([bool]$Passed, [string]$Name, [string]$Detail) {
    if ($Passed) {
        Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green
    } else {
        $script:failures++
        Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red
    }
}

function Get-DotEnvValue([string]$Name, [string]$Default) {
    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if ($null -ne $processValue) { return $processValue }
    $path = Join-Path $repoRoot '.env'
    if (Test-Path -LiteralPath $path) {
        foreach ($line in Get-Content -LiteralPath $path) {
            if ($line -match "^\s*$([regex]::Escape($Name))\s*=(.*)$") {
                return $Matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }
    return $Default
}

function Test-TcpPort([string]$HostName, [int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        return $task.Wait(1500) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Check $false 'Docker CLI' '未安装或不在 PATH。'
    exit 1
}
docker info *> $null
Write-Check ($LASTEXITCODE -eq 0) 'Docker Engine' '检查本机 Docker 服务状态。'

docker compose version *> $null
$composeAvailable = $LASTEXITCODE -eq 0
Write-Check $composeAvailable 'Docker Compose v2' '需要 docker compose 子命令。'
if (-not $composeAvailable) { exit 1 }

$envPath = Join-Path $repoRoot '.env'
Write-Check (Test-Path -LiteralPath $envPath) '.env' '本地配置文件存在。'
if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Host '[MANUAL REQUIRED] 先运行 .\scripts\bootstrap.ps1 创建 .env。' -ForegroundColor Yellow
    exit 1
}

$key = Get-DotEnvValue 'DEEPSEEK_API_KEY' ''
$keyPresent = $key.Length -gt 0 -and $key -notmatch '^(replace-me|your[_-].*|<.*>)$'
Write-Check $keyPresent 'DEEPSEEK_API_KEY' '仅报告是否已设置，不显示 Secret。'
if (-not $keyPresent) {
    Write-Host '[MANUAL REQUIRED] 在 .env 中填入 DeepSeek API Key，然后在 AstrBot Provider 中使用 $DEEPSEEK_API_KEY。' -ForegroundColor Yellow
}

docker compose config --quiet *> $null
$composeValid = $LASTEXITCODE -eq 0
Write-Check $composeValid 'Compose 配置' 'docker compose config。'
if (-not $composeValid) { exit 1 }

$running = @(docker compose ps --services --filter 'status=running' 2>$null)
Write-Check ($running -contains 'astrbot') 'AstrBot 容器' 'Compose 服务处于 running 状态。'
Write-Check ($running -contains 'napcat') 'NapCat 容器' 'Compose 服务处于 running 状态。'

$astrbotPort = [int](Get-DotEnvValue 'ASTRBOT_WEBUI_PORT' '6185')
$napcatPort = [int](Get-DotEnvValue 'NAPCAT_WEBUI_PORT' '6099')
$bindHost = Get-DotEnvValue 'ASTRBOT_WEBUI_BIND' '127.0.0.1'
if ($bindHost -eq '0.0.0.0' -or $bindHost -eq '::') { $bindHost = '127.0.0.1' }
Write-Check (Test-TcpPort $bindHost $astrbotPort) 'AstrBot WebUI 端口' "$bindHost`:$astrbotPort 可连接。"
$bindHost = Get-DotEnvValue 'NAPCAT_WEBUI_BIND' '127.0.0.1'
if ($bindHost -eq '0.0.0.0' -or $bindHost -eq '::') { $bindHost = '127.0.0.1' }
Write-Check (Test-TcpPort $bindHost $napcatPort) 'NapCat WebUI 端口' "$bindHost`:$napcatPort 可连接。"

$oneBotProbe = 'const s=require("net").connect(6199,"astrbot",()=>{s.end();process.exit(0)});s.setTimeout(3000,()=>process.exit(1));s.on("error",()=>process.exit(1));'
docker compose exec -T napcat node -e $oneBotProbe *> $null
$oneBotReachable = $LASTEXITCODE -eq 0
Write-Check $oneBotReachable 'OneBot Reverse WS 网络端口' 'NapCat 容器可通过服务名 astrbot 连接 TCP 6199。'
if (-not $oneBotReachable) {
    Write-Host '[MANUAL REQUIRED] 在 AstrBot WebUI 启用 OneBot v11 适配器，并监听 0.0.0.0:6199。' -ForegroundColor Yellow
}

Write-Host "Doctor 完成：$failures 项检查失败。"
if ($failures -gt 0) { exit 1 }
