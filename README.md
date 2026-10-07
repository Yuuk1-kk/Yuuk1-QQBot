# Yuuk1-QQBot

基于 AstrBot、NapCatQQ、OneBot v11 Reverse WebSocket 和 DeepSeek 的 QQ 群 AI Bot 项目。AstrBot 负责运行时、平台适配、Provider、会话和 WebUI；项目定制逻辑只放在 Star 插件中。

**Status: v0.1 stabilization VERIFIED.** Docker、插件、DeepSeek ChatUI、QQ 群 E2E，以及 NapCat 重建后的自动登录、OneBot 重连和群聊回复均已真实通过；结果见 [PROGRESS.md](PROGRESS.md)。

## 架构

```text
QQ 群
  ↓
NapCatQQ
  ↓ OneBot v11 Reverse WebSocket (ws://astrbot:6199/ws)
AstrBot
  ↓ Yuuk1 Core Star
DeepSeek（经 AstrBot Provider）
```

AstrBot 与 NapCat 位于同一 Compose 网络。6199 只在容器网络内可达；两个管理 WebUI 默认只绑定到宿主机回环地址。

## 技术栈

- AstrBot：Bot Runtime、OneBot v11 Adapter、Pipeline、Conversation、Provider、Star loader 和 WebUI
- NapCatQQ：QQ transport 与 OneBot v11
- DeepSeek：通过 AstrBot 原生 Provider 接入
- Docker Compose：服务编排与数据持久化
- Yuuk1 Core：群白名单、私聊开关、管理员命令、人格补充和用户级 + 群级限流

## 前置条件

- Windows 10/11 与 Docker Desktop（启用 Linux containers）
- Docker Compose v2
- 一个用于 Bot 的 QQ 账号，首次登录需要你本人扫码
- DeepSeek API Key

## Quick Start

私有仓库创建并授予访问权限后，将以下 `<private-repository-url>` 换成 GitHub 页面上的实际克隆地址，再在 PowerShell 中执行：

```powershell
git clone <private-repository-url> Yuuk1-QQBot
Set-Location .\Yuuk1-QQBot
.\scripts\bootstrap.ps1
notepad .env
```

`bootstrap.ps1` 会创建未跟踪的 `.env` 和数据目录，并检查 Docker CLI、Compose 与 Engine；不会安装 Docker 或生成密钥。在 `.env` 中把 `DEEPSEEK_API_KEY=replace-me` 改为真实密钥，然后启动：

```powershell
.\scripts\start.ps1
.\scripts\doctor.ps1
```

打开 AstrBot WebUI `http://127.0.0.1:6185`，按首次启动日志登录并修改初始密码。确认 Yuuk1 Core 出现在插件列表，再配置 DeepSeek Provider / Profile 和 OneBot v11 Adapter。打开 NapCat WebUI `http://127.0.0.1:6099/webui`，用 Bot QQ 扫码登录，并在 WebUI 中选择自动登录账号以便容器重建后恢复。最后设置群白名单与项目管理员，在允许的 QQ 群中验证 @Bot、命令和 AI 回复。具体顺序见 [部署指南](docs/SETUP.md)。

详细步骤见 [部署指南](docs/SETUP.md)、[NapCat 指南](docs/NAPCAT.md) 和 [DeepSeek 指南](docs/DEEPSEEK.md)。

## 配置入口

- 锁定的 Docker 镜像、端口、时区、`DEEPSEEK_API_KEY`：仓库根目录 `.env`；升级流程见 [UPSTREAM](docs/UPSTREAM.md)
- AstrBot OneBot Adapter / Provider / Profile：AstrBot WebUI
- 群白名单、私聊开关、管理员、人格、限流：AstrBot WebUI → 插件 → Yuuk1 Core 配置
- NapCat 登录与 transport 配置：NapCat WebUI；Reverse WebSocket 地址由官方 `MODE=astrbot` 模板设为 `ws://astrbot:6199/ws`

`allowed_groups` 为空时所有群默认静默；`allow_private_chat=false` 时 QQ 私聊默认禁用。群聊/私聊允许后，同一 QQ 用户默认每 60 秒最多 3 次模型请求，每个群默认每 60 秒最多 15 次；两级限流只在进程内保存。`/yuuk1 reset` 与 `/yuuk1 status` 仅对 `admin_users` 生效。

## 管理脚本

| 脚本 | 作用 |
| --- | --- |
| `scripts/bootstrap.ps1` | 检查 Docker / Compose，创建 `.env` 占位文件和数据目录 |
| `scripts/start.ps1` | 校验 Compose 并启动服务 |
| `scripts/stop.ps1` | 停止并移除容器，保留 `data/` |
| `scripts/restart.ps1` | 确认已选择 NapCat 自动登录账号后重新创建容器，保留 `data/`；`-AllowQRRelogin` 显式允许再次扫码 |
| `scripts/logs.ps1` | 查看全部或指定服务日志 |
| `scripts/doctor.ps1` | 输出 `[PASS]`、`[WARN]`、`[FAIL]`、`[MANUAL]` 诊断状态 |
| `scripts/backup.ps1` | 停机后备份 AstrBot 数据和 NapCat 配置到忽略的 `backups/` |
| `scripts/check-upstream.ps1` | 只报告当前锁定和上游版本，不自动升级 |

开发检查可在仓库根目录运行：

```powershell
python -m pip install -r dev-requirements.txt
python -m pytest
python -m ruff check plugins scripts tests
```

## 项目状态

真实集成与重建后群聊验证结果见 [PROGRESS.md](PROGRESS.md)。`doctor.ps1` 不会发送计费模型请求。

## 安全

- `.env`、`data/`、`backups/`、NapCat QQ 会话和日志已加入 `.gitignore`。
- WebUI 默认仅绑定 `127.0.0.1`；OneBot 6199 不发布到宿主机。
- 不在插件配置、Git 跟踪文件或日志中存放、显示 API Key。
- DeepSeek Key 通过 Compose 环境变量传给 AstrBot；在 Provider 表单中填写 `$DEEPSEEK_API_KEY`。
- NapCat `MODE=astrbot` 每次启动都会重写 OneBot 模板，默认 Token 为空；本项目不写不可靠的配置补丁。默认只允许两容器通过专用 Compose 网络连接，详情见 [NapCat 指南](docs/NAPCAT.md)。
- 备份默认不含 QQ 登录态；需要保留时显式使用 `scripts/backup.ps1 -IncludeQQSession`。备份含敏感数据，应由本人安全保管。
- 不要把 WebUI 端口直接映射到公网。QQ 账号登录和 API Key 由用户本人保管。

## Upstream

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) · [官方文档](https://docs.astrbot.app/)
- [NapCatQQ](https://github.com/NapNeko/NapCatQQ) · [NapCat-Docker](https://github.com/NapNeko/NapCat-Docker)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
