# Operations

以下命令在仓库根目录 PowerShell 中执行。

## Start / Stop / Restart

```powershell
.\scripts\start.ps1
.\scripts\stop.ps1
.\scripts\restart.ps1
```

`stop.ps1` 会执行 Compose down，但不删除 bind-mounted `data/`。不要使用 `docker compose down -v` 作为日常停机命令。

修改仓库中的 Yuuk1 Core 源码后运行 `restart.ps1`。Compose 的只读 bind mount 会把 `plugins/astrbot_plugin_yuuk1_core` 映射到 AstrBot 的 `data/plugins` 发现目录，无需复制文件。重启后用 `doctor.ps1` 和 AstrBot 插件列表确认实际加载。

## Logs

```powershell
.\scripts\logs.ps1
.\scripts\logs.ps1 -Service astrbot -Tail 200
.\scripts\logs.ps1 -Service napcat
```

日志和 NapCat 运行数据包含账号与运行信息，按敏感数据保护；排障贴日志前先检查并脱敏。

## Update

1. 停止服务，运行 `scripts/backup.ps1` 创建升级前备份；若回滚时必须保留现有 QQ 登录态，显式加 `-IncludeQQSession`。
2. 运行 `scripts/check-upstream.ps1`，查看 [UPSTREAM.md](UPSTREAM.md) 的锁定版本、官方 release 和镜像 digest；检查 [ASTRBOT_RESEARCH.md](ASTRBOT_RESEARCH.md) 的 Star API 兼容面。`v4.29.0-beta.1` 等 tag 即使 GitHub metadata 标记不可靠，仍按 beta 处理。
3. 核实候选镜像的稳定 tag 与多架构 digest，同步更新 `compose.yml`、`.env.example`、`docs/UPSTREAM.md`，并检查本地 `.env` 的覆盖值。确认后执行：

```powershell
docker compose config --quiet
docker compose pull
.\scripts\restart.ps1
.\scripts\doctor.ps1
```

4. 查看 AstrBot 与 NapCat 日志、Yuuk1 Core 加载状态，再做 Provider、Adapter 和 QQ 群真实消息验证。升级失败时恢复旧镜像 pin；如果数据已被新版本迁移，停止服务后再用升级前备份恢复。不要自动跟随 `latest` 或 beta。

## Backup / Restore

先停掉 Bot，运行仓库提供的备份脚本：

```powershell
.\scripts\stop.ps1
.\scripts\backup.ps1
```

默认备份包括 `data/astrbot` 和 `data/napcat/config`，排除日志、缓存与临时文件。若需要同时保留 NapCat QQ 登录态，显式运行 `.\scripts\backup.ps1 -IncludeQQSession`；否则恢复后需要重新扫码。脚本将带时间戳的 ZIP 放在已忽略的 `backups/`，不会上传。备份包含会话和配置等敏感数据，应加密并限制访问。

恢复时保持服务停止，先确认当前 `data/` 另有保留，再把选定 ZIP 中的 `data/` 文件还原到仓库根目录。恢复会覆盖对应现有文件；确认备份来源和目标路径后再操作，然后启动服务、运行 `doctor.ps1` 并进行手工消息验证。

## Troubleshooting

- Compose 配置：`docker compose config --quiet`
- 容器状态与端口探测：`.\scripts\doctor.ps1`
- AstrBot 日志：`.\scripts\logs.ps1 -Service astrbot`
- NapCat 日志：`.\scripts\logs.ps1 -Service napcat`
- Adapter：AstrBot 在容器内监听 `0.0.0.0:6199`，NapCat 使用 `ws://astrbot:6199/ws`；6199 不发布到宿主机。`MODE=astrbot` 每次启动覆盖 NapCat 的 OneBot 模板，默认 token 为空。
- No provider：检查环境变量名、AstrBot Provider API Key 值 `$DEEPSEEK_API_KEY`、模型启用状态和当前 Profile。
- No group reply：确认插件已加载、群号已在白名单中、原生唤醒设置已满足，且该用户及全群都未触发限流；私聊默认关闭。

修复后再次运行 `doctor.ps1` 和实际群聊验证。诊断结果区分 `[PASS]`、`[WARN]`、`[FAIL]`、`[MANUAL]`；需要用户扫码或真实 API 请求的步骤不能由诊断脚本伪造。
