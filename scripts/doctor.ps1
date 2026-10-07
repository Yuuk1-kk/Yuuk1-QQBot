[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$failures = 0
. (Join-Path $PSScriptRoot 'doctor-status.ps1')

# Docker Desktop's per-user installer may not update an already-running terminal PATH.
if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and $env:LOCALAPPDATA) {
    $dockerBin = Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin'
    if (Test-Path -LiteralPath (Join-Path $dockerBin 'docker.exe') -PathType Leaf) {
        $env:PATH = "$dockerBin;$env:PATH"
    }
}

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
$key = $null
$dockerAvailable = [bool](Get-Command docker -ErrorAction SilentlyContinue)
if (-not $dockerAvailable) {
    Write-Check 'MANUAL' 'DEEPSEEK_API_KEY' '无法检查 AstrBot 当前进程的密钥环境变量。'
    Write-Check 'FAIL' 'Docker CLI' '未安装或不在 PATH；请安装并启动 Docker Desktop。'
    Write-Check 'WARN' 'Compose/runtime' '缺少 Docker CLI，无法检查配置与容器。'
    exit 1
}
Write-Check 'PASS' 'Docker CLI' '已找到 docker 命令。'

docker compose version *> $null
$composeAvailable = $LASTEXITCODE -eq 0
if (-not $composeAvailable) {
    Write-Check 'MANUAL' 'DEEPSEEK_API_KEY' '无法检查 AstrBot 当前进程的密钥环境变量。'
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
    Write-Check 'MANUAL' 'DEEPSEEK_API_KEY' '无法检查 AstrBot 当前进程的密钥环境变量。'
    Write-Check 'MANUAL' 'DeepSeek Provider/Profile' 'AstrBot Runtime 不可用，无法读取静态配置。'
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

    $astrbotState = $null
    try {
        $probeSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'astrbot-runtime-status.py') -Raw
        $probeOutput = $probeSource | docker compose exec -T astrbot python - 2>$null
        if ($LASTEXITCODE -eq 0) {
            $astrbotState = ($probeOutput -join "`n") | ConvertFrom-Json -AsHashtable
        }
    } catch {
        $astrbotState = $null
    }

    if ($null -eq $astrbotState) {
        Write-Check 'MANUAL' 'DEEPSEEK_API_KEY' '无法检查 AstrBot 当前进程的密钥环境变量。'
        Write-Check 'WARN' 'Yuuk1 Core mount' '无法读取 AstrBot 容器状态。'
        Write-Check 'WARN' 'Yuuk1 Core plugin load' '无法读取当前插件状态。'
        Write-Check 'MANUAL' 'DeepSeek Provider/Profile' '无法读取 AstrBot 静态配置；未发起模型请求。'
        Write-Check 'WARN' 'OneBot Adapter' '无法读取 AstrBot Adapter 状态。'
        Write-Check 'WARN' 'OneBot listener 6199' '无法读取 AstrBot 监听状态。'
    } else {
        $runtimeKeyPresent = [bool]$astrbotState.runtime_key_present
        if ($keyPresent -and $runtimeKeyPresent) {
            Write-Check 'PASS' 'DEEPSEEK_API_KEY' '本地变量及 AstrBot 当前进程环境均已设置，内容已隐藏。'
        } elseif (-not $keyPresent) {
            Write-Check 'MANUAL' 'DEEPSEEK_API_KEY' '在本地 .env 填写真实密钥。'
        } else {
            Write-Check 'FAIL' 'DEEPSEEK_API_KEY' 'AstrBot 当前进程未取得密钥变量；需重建 AstrBot 容器。'
        }
        Write-Check $(if ($astrbotState.mounted) { 'PASS' } else { 'FAIL' }) 'Yuuk1 Core mount' '容器内 main.py 与 metadata.yaml 可读。'
        $pluginStatus = Get-DoctorPluginState -State $astrbotState
        Write-Check $pluginStatus.Level 'Yuuk1 Core plugin load' $pluginStatus.Detail
        $deepSeekStatus = Get-DoctorDeepSeekState -State $astrbotState
        Write-Check $deepSeekStatus.Level 'DeepSeek Provider/Profile' $deepSeekStatus.Detail
        Write-Check $(if ($astrbotState.adapter_enabled) { 'PASS' } else { 'WARN' }) 'OneBot Adapter' $(if ($astrbotState.adapter_enabled) { 'AstrBot aiocqhttp Reverse WebSocket 配置已启用。' } else { 'AstrBot aiocqhttp Reverse WebSocket 配置未启用。' })
        Write-Check $(if ($astrbotState.listening) { 'PASS' } else { 'WARN' }) 'OneBot listener 6199' $(if ($astrbotState.listening) { '当前进程正在监听 6199。' } else { '当前进程未监听 6199。' })
    }
} else {
    $astrbotState = $null
    Write-Check 'MANUAL' 'DEEPSEEK_API_KEY' 'AstrBot 未运行，无法检查当前进程的密钥环境变量。'
    Write-Check 'MANUAL' 'DeepSeek Provider/Profile' 'AstrBot 未运行，无法读取静态配置。'
    Write-Check 'WARN' 'AstrBot WebUI / Yuuk1 Core / OneBot' 'AstrBot 未运行，无法检查。'
}

$napcatLoginStatus = $null
$oneBotReachable = $false
$reverseWsConfigured = $false
if ($napcatRunning) {
    $napcatPort = [int](Get-DotEnvValue 'NAPCAT_WEBUI_PORT' '6099')
    $napcatBind = Get-DotEnvValue 'NAPCAT_WEBUI_BIND' '127.0.0.1'
    $webuiReady = Test-WebUi $napcatBind $napcatPort
    Write-Check $(if ($webuiReady) { 'PASS' } else { 'FAIL' }) 'NapCat WebUI' '检查 HTTP 响应，不读取页面内容。'
    $loginProbe = & (Join-Path $PSScriptRoot 'napcat-login-status.ps1') -WebUiPort $napcatPort
    $napcatLoginStatus = $loginProbe.Status
    Write-Check $loginProbe.Status 'NapCat QQ login' $loginProbe.Message

    $napcatConfigDir = Join-Path $repoRoot 'data/napcat/config'
    $webUiConfigPath = Join-Path $napcatConfigDir 'webui.json'
    $quickAccountSelected = $false
    try {
        $webUiConfig = Get-Content -LiteralPath $webUiConfigPath -Raw | ConvertFrom-Json -AsHashtable
        $quickAccountSelected = -not [string]::IsNullOrWhiteSpace([string]$webUiConfig.autoLoginAccount)
    } catch { }
    Write-Check $(if ($quickAccountSelected) { 'PASS' } else { 'WARN' }) 'NapCat quick login' $(if ($quickAccountSelected) { 'WebUI 已选择自动登录账号；不显示账号。' } else { 'WebUI 尚未选择自动登录账号；重建后可能要求再次扫码。' })

    foreach ($configFile in @(Get-ChildItem -LiteralPath $napcatConfigDir -Filter 'onebot11_*.json' -File -ErrorAction SilentlyContinue)) {
        try {
            $oneBotConfig = Get-Content -LiteralPath $configFile.FullName -Raw | ConvertFrom-Json -AsHashtable
            if (@($oneBotConfig.network.websocketClients | Where-Object {
                $_.enable -eq $true -and $_.url -eq 'ws://astrbot:6199/ws'
            }).Count -gt 0) {
                $reverseWsConfigured = $true
                break
            }
        } catch { }
    }
    Write-Check $(if ($reverseWsConfigured) { 'PASS' } else { 'WARN' }) 'NapCat Reverse WS config' $(if ($reverseWsConfigured) { '已启用 ws://astrbot:6199/ws 客户端配置。' } else { '未发现已启用的目标 Reverse WebSocket 客户端配置。' })

    $qqDataPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'data/napcat/qq'))
    $napcatContainerId = @(docker compose ps -q napcat 2>$null) | Select-Object -First 1
    $qqMountPresent = $false
    if ($napcatContainerId) {
        try {
            $mounts = docker inspect $napcatContainerId --format '{{json .Mounts}}' 2>$null | ConvertFrom-Json
            $qqMountPresent = @($mounts | Where-Object {
                $_.Type -eq 'bind' -and $_.RW -eq $true -and
                $_.Destination -eq '/app/.config/QQ' -and
                [System.IO.Path]::GetFullPath($_.Source).TrimEnd('\', '/') -eq $qqDataPath.TrimEnd('\', '/')
            }).Count -eq 1
        } catch { }
    }
    Write-Check $(if ($qqMountPresent) { 'PASS' } else { 'FAIL' }) 'NapCat QQ data mount' $(if ($qqMountPresent) { '当前容器的 QQ 数据目录使用项目内可写 bind mount。' } else { '当前容器未使用预期的 QQ 数据 bind mount。' })
    docker compose exec -T napcat bash -c 'gosu napcat test -r /app/.config/QQ && gosu napcat test -w /app/.config/QQ' *> $null
    $qqDataWritable = $LASTEXITCODE -eq 0
    Write-Check $(if ($qqDataWritable) { 'PASS' } else { 'FAIL' }) 'NapCat QQ data permissions' $(if ($qqDataWritable) { '运行 QQ 的 napcat 用户可读写持久化目录。' } else { '运行 QQ 的 napcat 用户无法读写持久化目录。' })

    if ($astrbotRunning) {
        $oneBotProbe = 'timeout 3 bash -c "echo >/dev/tcp/astrbot/6199"'
        docker compose exec -T napcat bash -c $oneBotProbe *> $null
        $oneBotReachable = $LASTEXITCODE -eq 0
        Write-Check $(if ($oneBotReachable) { 'PASS' } else { 'WARN' }) 'OneBot TCP 6199' 'NapCat 到 astrbot:6199 的网络探测；TCP 可达不等于 WebSocket 已连接。'
    }
} else {
    Write-Check 'WARN' 'NapCat WebUI / QQ login' 'NapCat 未运行，无法检查。'
}

if ($null -ne $astrbotState -and $napcatRunning) {
    $oneBotState = @{
        adapter_enabled = [bool]$astrbotState.adapter_enabled
        listening = [bool]$astrbotState.listening
        tcp_reachable = $oneBotReachable
        reverse_configured = $reverseWsConfigured
        qq_online = $napcatLoginStatus -eq 'PASS'
        socket_established = [bool]$astrbotState.websocket_socket
        websocket_connected = [bool]$astrbotState.websocket_registry_connected
    }
    $oneBotStatus = Get-DoctorOneBotState -State $oneBotState
    Write-Check $oneBotStatus.Level 'OneBot connection' $oneBotStatus.Detail
} else {
    Write-Check 'WARN' 'OneBot connection' 'AstrBot 或 NapCat 状态不可用，无法确认当前连接。'
}

Write-Host "Doctor 完成：$failures 项失败；WARN 和 MANUAL 不计为代码失败。"
if ($failures -gt 0) { exit 1 }
exit 0
