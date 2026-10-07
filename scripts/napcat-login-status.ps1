[CmdletBinding()]
param(
    [switch]$ImportOnly,
    [ValidateRange(1, 65535)]
    [int]$WebUiPort = 6099,
    [ValidateRange(1, 60)]
    [int]$TimeoutSec = 5,
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'

function Get-NapCatField {
    param([object]$Value, [string]$Name)

    if ($null -eq $Value) { return $null }
    if ($Value -is [System.Collections.IDictionary]) { return $Value[$Name] }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function New-NapCatLoginResult {
    param([string]$Status, [string]$Message)

    # Keep all output independent of HTTP responses, account IDs, and secrets.
    return [pscustomobject]@{ Status = $Status; Message = $Message }
}

function Resolve-NapCatLoginStatus {
    param(
        [object]$AuthResponse,
        [object]$StatusResponse,
        [bool]$TwoFactorEnabled = $false
    )

    if ($TwoFactorEnabled) {
        return New-NapCatLoginResult 'MANUAL' 'NapCat WebUI 启用了双重验证，请在 WebUI 中确认 QQ 登录。'
    }

    $authData = Get-NapCatField $AuthResponse 'data'
    $credential = Get-NapCatField $authData 'Credential'
    if ((Get-NapCatField $AuthResponse 'code') -ne 0 -or
        -not ($credential -is [string]) -or
        [string]::IsNullOrWhiteSpace($credential)) {
        return New-NapCatLoginResult 'MANUAL' '无法鉴权 NapCat 状态接口；若刚多次运行 doctor，请等待一分钟再试。'
    }

    if ((Get-NapCatField $StatusResponse 'code') -ne 0) {
        return New-NapCatLoginResult 'MANUAL' 'NapCat 状态接口不可用，请在 WebUI 中确认 QQ 登录。'
    }

    $statusData = Get-NapCatField $StatusResponse 'data'
    $isLogin = Get-NapCatField $statusData 'isLogin'
    $coreReady = Get-NapCatField $statusData 'coreReady'
    if (-not ($isLogin -is [bool]) -or -not ($coreReady -is [bool])) {
        return New-NapCatLoginResult 'MANUAL' 'NapCat 状态接口返回了未知格式，请在 WebUI 中确认 QQ 登录。'
    }

    if ($isLogin -and $coreReady) {
        return New-NapCatLoginResult 'PASS' 'NapCat 已确认 QQ 登录且 Core 在线。'
    }

    return New-NapCatLoginResult 'FAIL' 'NapCat 报告 QQ 未登录或 Core 离线。'
}

if ($ImportOnly) { return }

# NapCat v4.18.33: /api/QQLogin/CheckLoginStatus checks both the runtime login
# flag and core.selfInfo.online. The endpoint requires a one-hour WebUI bearer
# credential obtained from /api/auth/login with SHA256(token + '.napcat').
# All requests stay on loopback; redirects and proxies are disabled to keep the
# credential local. No request or raw response is ever written to output.
$configPath = Join-Path $RepoRoot 'data\napcat\config\webui.json'
$config = $null
$token = $null
$tokenHash = $null
$credential = $null
$authResponse = $null
$statusResponse = $null

try {
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        return New-NapCatLoginResult 'MANUAL' 'NapCat WebUI 配置不存在，请在 WebUI 中确认 QQ 登录。'
    }

    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    if ((Get-NapCatField $config 'enable2FA') -eq $true) {
        return Resolve-NapCatLoginStatus -TwoFactorEnabled $true
    }

    $token = Get-NapCatField $config 'token'
    if (-not ($token -is [string]) -or [string]::IsNullOrWhiteSpace($token)) {
        return New-NapCatLoginResult 'MANUAL' 'NapCat WebUI 凭据不可用，请在 WebUI 中确认 QQ 登录。'
    }

    $tokenBytes = [System.Text.Encoding]::UTF8.GetBytes($token + '.napcat')
    $tokenHash = [Convert]::ToHexString(
        [System.Security.Cryptography.SHA256]::HashData($tokenBytes)
    ).ToLowerInvariant()
    $baseUri = "http://127.0.0.1:$WebUiPort/api"
    $authResponse = Invoke-RestMethod `
        -Uri "$baseUri/auth/login" `
        -Method Post `
        -ContentType 'application/json' `
        -Body (@{ hash = $tokenHash } | ConvertTo-Json -Compress) `
        -NoProxy `
        -MaximumRedirection 0 `
        -TimeoutSec $TimeoutSec

    $authData = Get-NapCatField $authResponse 'data'
    $credential = Get-NapCatField $authData 'Credential'
    if ((Get-NapCatField $authResponse 'code') -ne 0 -or
        -not ($credential -is [string]) -or
        [string]::IsNullOrWhiteSpace($credential)) {
        return Resolve-NapCatLoginStatus -AuthResponse $authResponse
    }

    $statusResponse = Invoke-RestMethod `
        -Uri "$baseUri/QQLogin/CheckLoginStatus" `
        -Method Post `
        -ContentType 'application/json' `
        -Headers @{ Authorization = "Bearer $credential" } `
        -Body '{}' `
        -NoProxy `
        -MaximumRedirection 0 `
        -TimeoutSec $TimeoutSec
    return Resolve-NapCatLoginStatus -AuthResponse $authResponse -StatusResponse $statusResponse
} catch {
    # Exception details can contain request headers, URLs, and response bodies.
    return New-NapCatLoginResult 'MANUAL' '无法安全读取 NapCat 登录状态；若刚多次运行 doctor，请等待一分钟再试。'
} finally {
    $config = $null
    $token = $null
    $tokenBytes = $null
    $tokenHash = $null
    $credential = $null
    $authResponse = $null
    $statusResponse = $null
}
