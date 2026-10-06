# Operations

以下命令在仓库根目录 PowerShell 中执行。

## Start / Stop / Restart

```powershell
.\scripts\start.ps1
.\scripts\stop.ps1
.\scripts\restart.ps1
```

`stop.ps1` 会执行 Compose down，但不删除 bind-mounted `data/`。不要使用 `docker compose down -v` 作为日常停机命令。

## Logs

```powershell
.\scripts\logs.ps1
.\scripts\logs.ps1 -Service astrbot -Tail 200
.\scripts\logs.ps1 -Service napcat
```

日志和 NapCat 运行数据包含账号与运行信息，按敏感数据保护；排障贴日志前先检查并脱敏。

## Update

1. 停止服务并备份 `data/`。
2. 查看 AstrBot/NapCat 官方 release 与本项目 `docs/ASTRBOT_RESEARCH.md`，确认兼容面。
3. 修改 `.env` 中镜像 tag（默认使用上游文档推荐的 `latest`），然后执行：

```powershell
docker compose pull
.\scripts\restart.ps1
.\scripts\doctor.ps1
```

4. 查看 AstrBot 与 NapCat 日志，再做 Provider、Adapter 和群聊手工验证。

## Backup / Restore

停掉 Bot 后，将 `data/` 作为一个整体复制或压缩到受控的备份位置。PowerShell 示例：

```powershell
.\scripts\stop.ps1
Compress-Archive -Path .\data\* -DestinationPath ..\Yuuk1-QQBot-data-backup.zip
```

备份包括 AstrBot 会话/Provider 配置与 NapCat QQ 登录态，应加密并限制访问。恢复时先停止容器，再把备份还原到同一 `data/` 目录；不要把备份放入 Git。

## Troubleshooting

- Compose 配置：`docker compose config --quiet`
- 容器状态与端口探测：`.\scripts\doctor.ps1`
- AstrBot 日志：`.\scripts\logs.ps1 -Service astrbot`
- NapCat 日志：`.\scripts\logs.ps1 -Service napcat`
- Adapter：AstrBot 监听 `0.0.0.0:6199`，NapCat 使用 `ws://astrbot:6199/ws`。
- No provider：检查环境变量名、AstrBot Provider API Key 值 `$DEEPSEEK_API_KEY`、模型启用状态和当前 Profile。
- No group reply：确认插件已启用、群号已在白名单中、Native wake-up 设置已满足且群未触发限流。

修复后再次运行 `doctor.ps1` 和实际群聊验证。需要用户扫码或真实 API 请求的步骤不能由诊断脚本伪造。
