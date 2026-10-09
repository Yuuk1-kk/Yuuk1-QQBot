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
- 群白名单、私聊开关、管理员、Owner 身份、人格、限流、群身份上下文：AstrBot WebUI → 插件 → Yuuk1 Core 配置
- NapCat 登录与 transport 配置：NapCat WebUI；Reverse WebSocket 地址由官方 `MODE=astrbot` 模板设为 `ws://astrbot:6199/ws`

`allowed_groups` 为空时所有群默认静默；`allow_private_chat=false` 时 QQ 私聊默认禁用。群聊/私聊允许后，同一 QQ 用户默认每 60 秒最多 8 次模型请求，每个群默认每 60 秒最多 30 次；两级限流只在进程内保存。该限流保护服务免受刷屏和异常循环影响，正常 3–5 轮连续对话不会触顶。`/yuuk1 reset` 与 `/yuuk1 status` 仅对 `admin_users` 生效。

`owner_qq_id` 是鲸鲸的关系身份绑定，默认空；只按可信 QQ 平台当前事件的 sender ID 与该字符串匹配。Owner 身份不等于 `admin_users`，不会增加任何管理、系统或工具权限。要启用时，在 AstrBot WebUI 的“插件 → Yuuk1 Core 配置”中填写 Owner 的 QQ 号字符串并保存；本仓库不保存该运行值。

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

### Group Identity Context v1 — VERIFIED

当前实现用于让鲸鲸在同一个允许群中区分发言人。每条临时群聊上下文按 [显示名] 消息 标记；同名成员仅在需要时附加短匿名标签。当前显示名来自 AstrBot event.get_sender_name()；AstrBot v4.28.2 的 aiocqhttp adapter 优先取群名片 card，再回退到 nickname。名字缺失或不安全时使用“群友”。

身份键由 HMAC-SHA256 计算，范围包含平台、群和 QQ 用户；同一用户在不同群得到不同身份键。原始 QQ / 群 ID 只用于收到事件时计算 HMAC，不写进 identity store、prompt 或插件日志。持久内容限于当前显示名、最多 5 个 alias、first/last seen 时间和 HMAC 键，不包含消息全文或人物事实。

文件位于 AstrBot 官方插件数据目录，对应宿主机路径：

- data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/identity_secret
- data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/group_identity.json
- data/astrbot/config/astrbot_plugin_yuuk1_core_config.json（实际 WebUI 插件配置）

identity_secret 是随机 32 字节密钥，第一次启动时创建，AstrBot restart/recreate 后保持不变。JSON store 通过同目录临时文件、fsync 和原子替换批量写入；名称变更最多保留 5 个去重 alias，每群最多记录 500 名成员。若 store 已存在而 secret 丢失，插件不会自动生成替代 secret 或覆盖旧 store，doctor 会报告身份持久化故障。

### Owner Identity v1 + Relationship Memory Store Foundation

Owner Identity v1 的确定性身份问答已部署，用户确认真实 QQ E2E 全部通过。对直接面向鲸鲸的明确第一人称身份问句，插件按可信平台、当前 sender ID 和 `owner_qq_id` 分类并直接回复，在 Provider 选择前停止本轮 Agent；歧义、引用、转述、转发和长文本继续原流程。该保证限于被白名单规则识别的身份问答，不代表一般自由聊天永不发生身份误归属。昵称、自称、@、引用和共享历史不参与 Owner 认证；不注入原始 QQ 号、不修改全局 Persona 或管理员授权。`owner_identity_diagnostics_enabled` 默认值及当前运行值均为 `false`。

Relationship Memory Store Foundation 使用 Python 标准库 SQLite，默认路径为 `data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/relationship_memory.sqlite3`。记录按现有 HMAC `group_key` 与 `subject_member_key` 双重限定，当前仅提供插件内部 CRUD；没有 LLM 工具、聊天命令、自动抽取、记忆检索或 DeepSeek 注入。数据库没有静态加密。未来迁移时需在停机一致性备份中同时保留该数据库、`identity_secret`、`group_identity.json` 与插件配置；现有 `scripts/backup.ps1` 会归档 AstrBot data，但本轮未执行备份或迁移。

未来迁移到 Linux Docker 时，应一起复制上述 identity secret、identity store 与插件配置，并保持 AstrBot data 目录由持久卷承载。现有停机一致性备份归档 data/astrbot，因此会包含这三项；不要把这些运行数据放入 Git。代码、本地回归、AstrBot Runtime 和用户确认的真实 QQ 群 E2E 均已通过；Group Identity Context v1 已正式 VERIFIED。

- **Free Talk v1 — VERIFIED**：打开 `free_talk_enabled` 后，Yuuk1 Core 才会为 `allowed_groups` 里的群保留最近 20 条 / 15 分钟的内存摘要。IDLE 普通消息经过本地近期消息门后，以默认 `free_talk_probability=0.35` 决定是否进入一次 SPEAK/SILENT 判断。直接呼叫“鲸鲸 / 大肥鱼 / 蓝色大肥鱼 / 小鲸 / 鲸鱼娘”、@鲸鲸 和 Reply 鲸鲸时走明确回复路径，不经过 0.35 普通候选概率。普通句子中的昵称提及仍按 IDLE 普通消息处理。
- **连续对话**：`engagement_enabled=true` 默认开启，按群保留最近一次成功回复的稳定成员键、鲸鲸最后一轮回复和最近群聊上下文；状态只在内存保存。每次成功回复后 300 秒内，相关消息不再经过 0.35：高置信延续直接进入原生回复，高置信无关引用静默，模糊内容只用现有的一次分类请求判断相关性。每次成功完成的整轮回复刷新 300 秒状态。300 秒是 ENGAGED 状态时长，不是聊天冷却；Free Talk 没有时间冷却。QQ v4.28.2 `Reply.sender_id` 可识别引用对象，未解析的引用不会猜测目标。旧 `free_talk_min_interval_seconds` 和 `free_talk_decision_interval_seconds` 保留兼容、不参与决策。安全限流仍按每用户 8 次 / 60 秒、每群 30 次 / 60 秒生效；自消息防回环、命令及未允许群排除继续生效。SPEAK 后只进入一次 AstrBot 原生 Conversation、Persona、Agent、Tools 和 Web Search 流程。
- **多消息回复**：`multi_message_enabled=true` 默认开启，`multi_message_max_parts=3`，`multi_message_min_chars_to_split=20`。只在最终生成后按段落或完整短句轻量拆分，不增加 LLM 调用；短文本、URL 和 Markdown 结构保持单条。后续余下文本会以约 0.45 秒间隔发送；启用文字加贴图时，顺序为首条文本、剩余文本、贴图。
- **Jingjing Stickers v1 — VERIFIED**：工具 API 为 `jingjing_sticker(category)`，只接受 happy、angry、speechless、smug、sad、confused、laugh、peek、fatfish、neutral 固定分类。素材放在 `plugins/astrbot_plugin_yuuk1_core/assets/stickers/<category>/`；每类目录可为空。仅 PNG/JPG/JPEG，单图不超过 8 MiB、1600 万像素，并通过签名、Pillow 完整解码和发送前复检；拒绝 GIF/WebP/SVG、URL、符号链接和目录逃逸。模型只传分类，不接触路径、文件名或 URL。`stickers_enabled=false` 或图库为空时不向当前 Agent 暴露工具；图库有有效素材时，工具按请求可用，不修改 Persona tools。`sticker_repeat_window=4`（范围 1–5）只在内存保存 SHA-256 指纹；多图类别尽量避开最近素材，单图类别允许重复，AstrBot 重启后历史清空。一轮最多发送一张图；多消息回复先发所有文字，最后发贴图；无文字时允许 image-only。贴图失败保留已有文字；image-only 失败时回退“鲸鲸在这儿。”，不额外调用 LLM。用户已确认真实 QQ 图片发送、文字+贴图、image-only、多消息+贴图、重复抑制及安全/回归 E2E 全部通过。
- **QQ 自定义表情发送模式 — 核心 E2E PASS（已知限制保留）**：`sticker_send_mode` 默认 `image`，保持普通图片兼容；`qq_custom` 通过 AstrBot v4.28.2 公开组件序列化 OneBot image `sub_type=1`，NapCat v4.18.33 转发该自定义图片子类型。最新用户手动 QQ E2E 确认普通文字、文字+自定义表情、纯表情、昵称唤醒和 image 模式兼容通过，且客户端可收藏自定义表情。只有发送前准备失败或 `Context.send_message()` 明确返回无匹配平台时才进行普通图片 fallback；`ActionFailed`（包括 NTEvent 超时）及其他发送异常均按结果不确定处理，不自动重发。结果不确定时保留已发送文字；纯表情 `qq_custom` 不补发额外兜底文字。NTEvent 修复尚未在新的真实超时场景中复验。历史上的 `(图)` / `(表情已发出)`、工具调用后空 completion、Agent 错误后可能继续发送 Sticker，以及真实 AstrBot Stage 空链 guard 集成测试缺口仍待处理；上下文体积与空 completion 的因果关系未确认。
- **Idle Presence**：打开 `idle_speak_enabled` 后才启动一个可取消的后台任务。默认群聊安静 30 分钟、检查间隔 5 分钟、单群尝试间隔 6 小时、主动时段 09:00–23:00、本次检查触发概率 0.10。只向插件运行期间观察到的允许群发送。
- Group Identity Context 默认启用，只在允许群中观察群成员身份和名称；Free Talk 与 Idle Presence 默认关闭，只有启用它们才保留有界的群聊消息上下文。多消息回复默认开启，但只在已有的允许 QQ 群 LLM 回复完成后拆分。动态消息上下文仅使用临时 user content，不写入 Persona 或持久 Conversation。
- 当前 AstrBot v4.28.2 “鲸鲸” Persona 的 `tools` 实际值为 `None`，按上游语义会允许所有工具，包括 Web Search 和 `jingjing_sticker`。若之后把 Persona 改成显式工具列表，需要在列表中加入 `jingjing_sticker` 才能发送表情；本轮未修改 Persona。

每次最终生成最多拆成 3 条 QQ 消息；短文本、URL 和 Markdown 结构保持完整，不增加 LLM 调用。Free Talk v1、Group Identity Context v1 和 Jingjing Stickers v1 均已由用户真实 QQ E2E 验证。下一阶段建议为 Cloud Deployment v1；本仓库本轮未开始该阶段。
