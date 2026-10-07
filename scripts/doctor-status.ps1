# Pure status rules shared by doctor.ps1 and its fixture tests. Never return
# values taken from runtime configuration: those may contain credentials.

function Get-DoctorPluginState {
    param([Parameter(Mandatory)][hashtable]$State)

    if (-not $State.mounted) {
        return [pscustomobject]@{ Level = 'FAIL'; Detail = '容器内插件入口或 metadata 不可读。' }
    }
    if (-not $State.discovered) {
        return [pscustomobject]@{ Level = 'FAIL'; Detail = '插件未出现在 AstrBot 插件目录。' }
    }
    if (-not $State.enabled) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = '插件已被 AstrBot 禁用。' }
    }
    if (-not $State.ready_current) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = '当前 AstrBot 进程没有插件初始化完成状态。' }
    }
    return [pscustomobject]@{ Level = 'PASS'; Detail = '插件入口可读、已启用，当前进程完成 initialize。' }
}

function Get-DoctorIdentitySecretState {
    param([Parameter(Mandatory)][hashtable]$State)

    if (-not $State.identity_enabled) {
        return [pscustomobject]@{ Level = 'MANUAL'; Detail = '群成员身份上下文已关闭。' }
    }
    if (-not $State.identity_persistence_enabled) {
        return [pscustomobject]@{ Level = 'MANUAL'; Detail = '身份持久化已关闭；重启后将使用临时身份。' }
    }
    if (-not $State.identity_secret_available) {
        return [pscustomobject]@{ Level = 'FAIL'; Detail = '匿名身份密钥不可用；为避免身份静默重置，持久化已停用。' }
    }
    return [pscustomobject]@{ Level = 'PASS'; Detail = '匿名身份密钥已加载；内容已隐藏。' }
}

function Get-DoctorIdentityStoreState {
    param([Parameter(Mandatory)][hashtable]$State)

    if (-not $State.identity_enabled) {
        return [pscustomobject]@{ Level = 'MANUAL'; Detail = '群成员身份上下文已关闭。' }
    }
    if (-not $State.identity_persistence_enabled) {
        return [pscustomobject]@{ Level = 'MANUAL'; Detail = '身份持久化已关闭；当前仅保留进程内上下文。' }
    }
    if (-not $State.identity_loaded) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = '当前 AstrBot 进程尚未加载身份库。' }
    }
    if (-not $State.identity_healthy) {
        return [pscustomobject]@{ Level = 'FAIL'; Detail = '身份库不可用；数据未自动覆盖。' }
    }
    $count = 0
    $parsedCount = 0
    if ([int]::TryParse([string]$State.identity_known_members, [ref]$parsedCount) -and $parsedCount -ge 0 -and $parsedCount -le 100000) {
        $count = $parsedCount
    }
    return [pscustomobject]@{ Level = 'PASS'; Detail = "身份库已加载；known_members=$count；不显示成员姓名或标识。" }
}

function Get-DoctorOneBotState {
    param([Parameter(Mandatory)][hashtable]$State)

    if (-not $State.adapter_enabled) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'AstrBot OneBot Adapter 未启用。' }
    }
    if (-not $State.listening) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'AstrBot OneBot 端口当前未监听。' }
    }
    if (-not $State.tcp_reachable) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'NapCat 当前无法访问 AstrBot OneBot 端口。' }
    }
    if (-not $State.reverse_configured) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'NapCat Reverse WebSocket 客户端未启用。' }
    }
    if (-not $State.qq_online) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'NapCat QQ 当前未确认在线。' }
    }
    if (-not $State.socket_established) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = '当前没有持久的 NapCat 到 AstrBot 套接字。' }
    }
    if (-not $State.websocket_connected) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'AstrBot 当前进程未报告已完成握手的 OneBot 客户端。' }
    }
    return [pscustomobject]@{ Level = 'PASS'; Detail = 'Adapter 已启用，当前 NapCat Reverse WebSocket 已连接。' }
}

function Get-DoctorDeepSeekState {
    param([Parameter(Mandatory)][hashtable]$State)

    if (-not $State.runtime_key_present) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'AstrBot 当前进程未取得 DEEPSEEK_API_KEY。' }
    }
    if (-not $State.source_enabled) {
        return [pscustomobject]@{ Level = 'MANUAL'; Detail = 'DeepSeek Provider Source 未配置或未启用。' }
    }
    if (-not $State.key_reference_valid) {
        return [pscustomobject]@{ Level = 'WARN'; Detail = 'DeepSeek Source 未引用 DEEPSEEK_API_KEY 环境变量。' }
    }
    if (-not $State.model_enabled) {
        return [pscustomobject]@{ Level = 'MANUAL'; Detail = 'deepseek/deepseek-flash 模型未配置或未启用。' }
    }
    if (-not $State.default_selected) {
        return [pscustomobject]@{ Level = 'MANUAL'; Detail = '当前默认对话 Profile 未选择 deepseek/deepseek-flash。' }
    }
    return [pscustomobject]@{ Level = 'PASS'; Detail = 'Source、密钥引用、模型及默认选择均已配置；未发起模型请求。' }
}
