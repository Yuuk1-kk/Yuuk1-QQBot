[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$failures = 0

function Write-Check([string]$Level, [string]$Name, [string]$Detail) {
    $color = switch ($Level) {
        'PASS' { 'Green' }
        'FAIL' { 'Red' }
        default { 'Yellow' }
    }
    if ($Level -eq 'FAIL') { $script:failures++ }
    Write-Host "[$Level] $Name - $Detail" -ForegroundColor $color
}

function Get-DotEnvValue([string]$Name, [string]$Default = '') {
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

function Test-WebUi([string]$Bind, [int]$Port) {
    $hostName = if ($Bind -in @('0.0.0.0', '::')) { '127.0.0.1' } else { $Bind }
    try {
        $response = Invoke-WebRequest -Uri "http://$($hostName):$Port/" -Method Get -SkipHttpErrorCheck -TimeoutSec 4
        return [int]$response.StatusCode -lt 500
    } catch {
        return $false
    }
}

if (Get-Command git -ErrorAction SilentlyContinue) {
    git rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Check 'PASS' 'Git' '当前目录属于 Git 仓库。'
    } else {
        Write-Check 'FAIL' 'Git' '当前目录不是 Git 仓库。'
    }
} else {
    Write-Check 'WARN' 'Git' '未找到 Git；不影响已部署容器。'
}

$envExists = Test-Path -LiteralPath (Join-Path $repoRoot '.env')
if ($envExists) {
    Write-Check 'PASS' '.env' '本地配置文件存在。'
} else {
    Write-Check 'FAIL' '.env' '缺少本地配置；先运行 .\scripts\bootstrap.ps1。'
}

foreach ($name in @('ASTRBOT_IMAGE', 'NAPCAT_IMAGE')) {
    $image = Get-DotEnvValue $name
    if (-not $image) {
        Write-Check 'WARN' $name '未在 .env 显式设置，将使用 Compose 内置固定镜像。'
    } elseif ($image -match ':(latest|master|nightly|.*beta.*)(@|$)') {
        Write-Check 'WARN' $name '当前镜像引用可能是浮动或测试版；请核对 docs/UPSTREAM.md。'
    } elseif ($image -match '@sha256:[0-9a-f]{64}$') {
        Write-Check 'PASS' $name '镜像包含不可变 digest。'
    } else {
        Write-Check 'WARN' $name '镜像未包含 digest；请核对固定版本策略。'
    }
}

$key = Get-DotEnvValue 'DEEPSEEK_API_KEY'
$keyPresent = [bool]($key -and $key -notmatch '^(replace-me|your[_-].*|<.*>)$')
if ($keyPresent) {
    Write-Check 'PASS' 'DEEPSEEK_API_KEY' '变量已设置，内容已隐藏。'
} else {
    Write-Check 'MANUAL' 'DEEPSEEK_API_KEY' '在本地 .env 填写真实密钥。'
}
Write-Check 'MANUAL' 'DeepSeek Provider/Profile' '需在 AstrBot WebUI 配置并选择；此检查不发起计费请求。'

$dockerAvailable = [bool](Get-Command docker -ErrorAction SilentlyContinue)
if (-not $dockerAvailable) {
    Write-Check 'FAIL' 'Docker CLI' '未安装或不在 PATH；请安装并启动 Docker Desktop。'
    Write-Check 'WARN' 'Compose/runtime' '缺少 Docker CLI，无法检查配置与容器。'
    exit 1
}
Write-Check 'PASS' 'Docker CLI' '已找到 docker 命令。'

docker compose version *> $null
$composeAvailable = $LASTEXITCODE -eq 0
if (-not $composeAvailable) {
    Write-Check 'FAIL' 'Docker Compose' '需要 docker compose v2。'
    exit 1
}
Write-Check 'PASS' 'Docker Compose' 'docker compose v2 可用。'

docker info *> $null
$engineAvailable = $LASTEXITCODE -eq 0
if ($engineAvailable) {
    Write-Check 'PASS' 'Docker Engine' '正在运行。'
} else {
    Write-Check 'FAIL' 'Docker Engine' '未运行；请启动 Docker Desktop 的 Linux containers。'
}

if ($envExists) {
    docker compose config --quiet *> $null
    $composeValid = $LASTEXITCODE -eq 0
    if ($composeValid) {
        Write-Check 'PASS' 'Compose config' '配置可解析。'
    } else {
        Write-Check 'FAIL' 'Compose config' '配置无法解析；请检查 .env 与 compose.yml。'
    }
} else {
    $composeValid = $false
    Write-Check 'WARN' 'Compose config' '缺少 .env，跳过运行配置解析。'
}

if (-not ($engineAvailable -and $composeValid)) {
    Write-Check 'WARN' 'Runtime' 'Docker Engine 或 Compose 尚未就绪，跳过容器检查。'
    exit 1
}

$running = @(docker compose ps --services --filter 'status=running' 2>$null)
$astrbotRunning = $running -contains 'astrbot'
$napcatRunning = $running -contains 'napcat'
Write-Check $(if ($astrbotRunning) { 'PASS' } else { 'FAIL' }) 'AstrBot container' '需要 running 状态。'
Write-Check $(if ($napcatRunning) { 'PASS' } else { 'FAIL' }) 'NapCat container' '需要 running 状态；等待扫码时仍可运行。'

if ($astrbotRunning) {
    $astrbotPort = [int](Get-DotEnvValue 'ASTRBOT_WEBUI_PORT' '6185')
    $astrbotBind = Get-DotEnvValue 'ASTRBOT_WEBUI_BIND' '127.0.0.1'
    $webuiReady = Test-WebUi $astrbotBind $astrbotPort
    Write-Check $(if ($webuiReady) { 'PASS' } else { 'FAIL' }) 'AstrBot WebUI' '检查 HTTP 响应，不读取页面内容。'

    $pluginProbe = 'from pathlib import Path; p=Path("/AstrBot/data/plugins/astrbot_plugin_yuuk1_core"); assert (p/"main.py").is_file() and (p/"metadata.yaml").is_file()'
    docker compose exec -T astrbot python -c $pluginProbe *> $null
    $pluginMounted = $LASTEXITCODE -eq 0
    Write-Check $(if ($pluginMounted) { 'PASS' } else { 'FAIL' }) 'Yuuk1 Core mount' '容器内 main.py 与 metadata.yaml 可读。'

    $astrbotLogs = @(docker compose logs --no-color --tail 2000 astrbot 2>$null) -join "`n"
    $readyIndex = $astrbotLogs.LastIndexOf('Yuuk1 Core ready', [System.StringComparison]::Ordinal)
    $loadFailures = [regex]::Matches($astrbotLogs, 'Failed to (?:load|import) plugin astrbot_plugin_yuuk1_core')
    $failureIndex = if ($loadFailures.Count -gt 0) { $loadFailures[$loadFailures.Count - 1].Index } else { -1 }
    if ($readyIndex -ge 0 -and $readyIndex -gt $failureIndex) {
        Write-Check 'PASS' 'Yuuk1 Core plugin load' '插件 initialize 完成日志已出现。'
    } elseif ($failureIndex -ge 0) {
        Write-Check 'FAIL' 'Yuuk1 Core plugin load' 'AstrBot 日志报告插件加载失败；请在本机检查日志。'
    } else {
        Write-Check 'WARN' 'Yuuk1 Core plugin load' '当前日志缺少 initialize 完成证据；请在 AstrBot Plugins 页面核对启用状态。'
    }

    if ($astrbotLogs -match 'aiocqhttp\(OneBot v11\).*(适配器已连接|adapter connected)') {
        Write-Check 'PASS' 'OneBot connection' 'AstrBot 日志记录 adapter connected。'
    } else {
        Write-Check 'MANUAL' 'OneBot connection' '尚无连接日志；在 WebUI 启用 Adapter，NapCat 扫码后核对。'
    }
} else {
    Write-Check 'WARN' 'AstrBot WebUI / Yuuk1 Core / OneBot' 'AstrBot 未运行，无法检查。'
}

if ($napcatRunning) {
    $napcatPort = [int](Get-DotEnvValue 'NAPCAT_WEBUI_PORT' '6099')
    $napcatBind = Get-DotEnvValue 'NAPCAT_WEBUI_BIND' '127.0.0.1'
    $webuiReady = Test-WebUi $napcatBind $napcatPort
    Write-Check $(if ($webuiReady) { 'PASS' } else { 'FAIL' }) 'NapCat WebUI' '检查 HTTP 响应，不读取页面内容。'
    Write-Check 'MANUAL' 'NapCat QQ login' 'QQ 首次登录/扫码状态请在 NapCat WebUI 核对。'

    if ($astrbotRunning) {
        $oneBotProbe = 'const s=require("net").connect(6199,"astrbot",()=>{s.end();process.exit(0)});s.setTimeout(3000,()=>process.exit(1));s.on("error",()=>process.exit(1));'
        docker compose exec -T napcat node -e $oneBotProbe *> $null
        $oneBotReachable = $LASTEXITCODE -eq 0
        Write-Check $(if ($oneBotReachable) { 'PASS' } else { 'MANUAL' }) 'OneBot TCP 6199' 'NapCat 到 astrbot:6199 的网络探测；连接确认以 AstrBot 日志为准。'
    }
} else {
    Write-Check 'WARN' 'NapCat WebUI / QQ login' 'NapCat 未运行，无法检查。'
}

Write-Host "Doctor 完成：$failures 项失败；WARN 和 MANUAL 不计为代码失败。"
if ($failures -gt 0) { exit 1 }
