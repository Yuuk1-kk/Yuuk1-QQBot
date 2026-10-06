# Yuuk1-QQBot

基于 AstrBot、NapCatQQ、OneBot v11 Reverse WebSocket 和 DeepSeek 的 QQ 群 AI Bot 项目。AstrBot 负责运行时、平台适配、Provider、会话和 WebUI；项目定制逻辑只放在 Star 插件中。

## 架构

```text
QQ 群
  → NapCatQQ
  → OneBot v11 Reverse WebSocket (ws://astrbot:6199/ws)
  → AstrBot Platform Adapter / Pipeline / Conversation / Agent
  → Yuuk1 Core Star
  → AstrBot Provider
  → DeepSeek API
```

AstrBot 与 NapCat 位于同一 Compose 网络。6199 只在容器网络内可达；两个管理 WebUI 默认只绑定到宿主机回环地址。

## 技术栈

- AstrBot：Bot Runtime、OneBot v11 Adapter、Pipeline、Conversation、Provider、Star loader 和 WebUI
- NapCatQQ：QQ transport 与 OneBot v11
- DeepSeek：通过 AstrBot 原生 Provider 接入
- Docker Compose：服务编排与数据持久化
- Yuuk1 Core：项目白名单、管理员命令、人格补充和群聊限流

## 前置条件

- Windows 10/11 与 Docker Desktop（启用 Linux containers）
- Docker Compose v2
- 一个用于 Bot 的 QQ 账号，首次登录需要你本人扫码
- DeepSeek API Key

## Quick Start

在仓库根目录打开 PowerShell：

```powershell
.\scripts\bootstrap.ps1
notepad .env
```

在 `.env` 中把 `DEEPSEEK_API_KEY` 替换为真实密钥，然后启动：

```powershell
.\scripts\start.ps1
.\scripts\logs.ps1 -Service astrbot
```

打开 AstrBot WebUI `http://127.0.0.1:6185`，按首次启动日志中的信息登录。随后按 [SETUP](docs/SETUP.md) 配置 DeepSeek Provider、OneBot v11 Adapter 和插件白名单；打开 NapCat WebUI `http://127.0.0.1:6099/webui` 并扫码登录 QQ。真实 API 调用和 QQ 群验证需要手动完成。

详细步骤见 [部署指南](docs/SETUP.md)、[NapCat 指南](docs/NAPCAT.md) 和 [DeepSeek 指南](docs/DEEPSEEK.md)。

## 配置入口

- Docker 镜像、端口、时区、`DEEPSEEK_API_KEY`：仓库根目录 `.env`
- AstrBot OneBot Adapter / Provider / Profile：AstrBot WebUI
- 群白名单、管理员、人格、限流：AstrBot WebUI → 插件 → Yuuk1 Core 配置
- NapCat 登录与 transport 配置：NapCat WebUI；Reverse WebSocket 地址由官方 `MODE=astrbot` 模板设为 `ws://astrbot:6199/ws`

## 管理脚本

| 脚本 | 作用 |
| --- | --- |
| `scripts/bootstrap.ps1` | 检查 Docker / Compose，创建 `.env` 占位文件和数据目录 |
| `scripts/start.ps1` | 校验 Compose 并启动服务 |
| `scripts/stop.ps1` | 停止并移除容器，保留 `data/` |
| `scripts/restart.ps1` | 重新创建并启动容器，保留 `data/` |
| `scripts/logs.ps1` | 查看全部或指定服务日志 |
| `scripts/doctor.ps1` | 检查服务、端口、OneBot 网络和必要配置是否存在 |

开发检查可在仓库根目录运行：

```powershell
python -m pip install -r dev-requirements.txt
python -m pytest
python -m ruff check plugins tests
```

## 项目状态

v0.1 实现和本地验证记录在 [PROGRESS.md](PROGRESS.md)。AstrBot/NapCat 启动、DeepSeek 实际请求、QQ 扫码和群聊往返都需要本机环境与真实凭据，未完成前均标记为 **MANUAL VERIFICATION REQUIRED**。

## 安全

- `.env`、`data/`、NapCat QQ 会话和日志已加入 `.gitignore`。
- WebUI 默认仅绑定 `127.0.0.1`；OneBot 6199 不发布到宿主机。
- 不在插件配置、Git 跟踪文件或日志中存放、显示 API Key。
- DeepSeek Key 通过 Compose 环境变量传给 AstrBot；在 Provider 表单中填写 `$DEEPSEEK_API_KEY`。
- 不要把 WebUI 端口直接映射到公网。QQ 账号登录和 API Key 由用户本人保管。

## Upstream

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) · [官方文档](https://docs.astrbot.app/)
- [NapCatQQ](https://github.com/NapNeko/NapCatQQ) · [NapCat-Docker](https://github.com/NapNeko/NapCat-Docker)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
