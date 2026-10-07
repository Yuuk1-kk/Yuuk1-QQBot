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

`allowed_groups` 为空时所有群默认静默；`allow_private_chat=false` 时 QQ 私聊默认禁用。群聊/私聊允许后，同一 QQ 用户默认每 60 秒最多 8 次模型请求，每个群默认每 60 秒最多 30 次；两级限流只在进程内保存。该限流保护服务免受刷屏和异常循环影响，正常 3–5 轮连续对话不会触顶。`/yuuk1 reset` 与 `/yuuk1 status` 仅对 `admin_users` 生效。

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

## 可选群聊功能与回复格式

- **Free Talk v1 — VERIFIED**：打开 `free_talk_enabled` 后，Yuuk1 Core 才会为 `allowed_groups` 里的群保留最近 20 条 / 15 分钟的内存摘要。IDLE 普通消息经过本地近期消息门后，以默认 `free_talk_probability=0.35` 决定是否进入一次 SPEAK/SILENT 判断。直接呼叫“鲸鲸 / 大肥鱼 / 蓝色大肥鱼 / 小鲸 / 鲸鱼娘”、@鲸鲸 和 Reply 鲸鲸时走明确回复路径，不经过 0.35 普通候选概率。普通句子中的昵称提及仍按 IDLE 普通消息处理。
- **连续对话**：`engagement_enabled=true` 默认开启，按群保留最近一次成功回复的用户标记、鲸鲸最后一轮回复和最近群聊上下文；状态只在内存保存。每次成功回复后 300 秒内，相关消息不再经过 0.35：高置信延续直接进入原生回复，高置信无关引用静默，模糊内容只用现有的一次分类请求判断相关性。每次成功完成的整轮回复刷新 300 秒状态。300 秒是 ENGAGED 状态时长，不是聊天冷却；Free Talk 没有时间冷却。QQ v4.28.2 `Reply.sender_id` 可识别引用对象，未解析的引用不会猜测目标。旧 `free_talk_min_interval_seconds` 和 `free_talk_decision_interval_seconds` 保留兼容、不参与决策。安全限流仍按每用户 8 次 / 60 秒、每群 30 次 / 60 秒生效；自消息防回环、命令及未允许群排除继续生效。SPEAK 后只进入一次 AstrBot 原生 Conversation、Persona、Agent、Tools 和 Web Search 流程。
- **多消息回复**：`multi_message_enabled=true` 默认开启，`multi_message_max_parts=3`，`multi_message_min_chars_to_split=20`。只在最终生成后按段落或完整短句轻量拆分，不增加 LLM 调用；短文本、URL 和 Markdown 结构保持单条。后续余下文本会以约 0.45 秒间隔发送；启用文字加贴图时，顺序为首条文本、剩余文本、贴图。
- **Sticker**：打开 `stickers_enabled` 后，模型可使用 `jingjing_sticker` 工具从 `plugins/astrbot_plugin_yuuk1_core/assets/stickers/` 选择本地 PNG/JPG/JPEG。每图最多 8 MiB；GIF/WebP/远程图不支持。目录只在 AstrBot 加载时扫描，增删图片后只重启 AstrBot。没有资源时自动保留文字回复。
- **Idle Presence**：打开 `idle_speak_enabled` 后才启动一个可取消的后台任务。默认群聊安静 30 分钟、检查间隔 5 分钟、单群尝试间隔 6 小时、主动时段 09:00–23:00、本次检查触发概率 0.10。只向插件运行期间观察到的允许群发送。
- Free Talk、Sticker 和 Idle Presence 开关默认关闭；只有开启 Free Talk 或 Idle Presence 才收集允许群聊的有界内存上下文。多消息回复默认开启，但只在已有的允许 QQ 群 LLM 回复完成后拆分，不额外观察或保存消息上下文。动态上下文只存在进程内，不写入 Persona 或 Conversation。
- 当前 AstrBot v4.28.2 “鲸鲸” Persona 的 `tools` 实际值为 `None`，按上游语义会允许所有工具，包括 Web Search 和 `jingjing_sticker`。若之后把 Persona 改成显式工具列表，需要在列表中加入 `jingjing_sticker` 才能发送表情；不要为此覆盖 Persona。

每次最终生成最多拆成 3 条 QQ 消息；短文本、URL 和 Markdown 结构保持完整，不增加 LLM 调用。Free Talk v1 的 direct nickname、ENGAGED 连续对话、无关群聊静默、中断后承接、@ / Reply、多消息发送以及 Runtime / doctor 已由用户真实验证。贴图图片 E2E 尚未完成，需用户提供 1–3 张鲸鲸图片；Sticker v1 是下一阶段。
