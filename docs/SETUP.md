# Setup

本指南从获取仓库到在 QQ 群验证 Bot。容器和插件实际运行须在本机 Docker 环境中检查；真实 DeepSeek Key 和 QQ 扫码需由你本人提供/完成。

## 1. 准备环境

安装并启动 Docker Desktop，确认使用 Linux containers，并使用 Docker Compose v2。私有仓库创建并授予访问权限后，将 `<private-repository-url>` 换成 GitHub 页面上的克隆地址，在 PowerShell 中执行：

```powershell
git clone <private-repository-url> Yuuk1-QQBot
Set-Location .\Yuuk1-QQBot
.\scripts\bootstrap.ps1
```

`bootstrap.ps1` 在 `.env` 不存在时从 `.env.example` 复制占位文件，并创建 AstrBot、NapCat 和备份目录。它不会生成密钥或安装 Docker。若 Docker CLI、Compose 或 Engine 不可用，脚本给出相应原因并以非零状态退出；目录和 `.env` 仍可准备好。

## 2. 设置 DeepSeek Key

用编辑器打开 `.env`，只在本机将 `DEEPSEEK_API_KEY=replace-me` 改成你的真实 Key。该文件已被 Git 忽略。详细 Provider 步骤见 [DEEPSEEK.md](DEEPSEEK.md)。

## 3. 启动容器

```powershell
.\scripts\start.ps1
.\scripts\logs.ps1 -Service astrbot
```

首次启动时，AstrBot 日志会显示管理面板登录信息。打开 `http://127.0.0.1:6185`，登录后按 AstrBot 提示修改初始密码。NapCat WebUI 位于 `http://127.0.0.1:6099/webui`。两个 WebUI 默认只绑定宿主机 `127.0.0.1`。

在 AstrBot 插件列表中确认 **Yuuk1 Core** 已加载，并在 AstrBot 日志中查找 `Yuuk1 Core ready`。仓库插件目录经 Compose 只读挂载到 `/AstrBot/data/plugins/astrbot_plugin_yuuk1_core`，这正是 AstrBot v4.28.2 的插件发现目录；修改仓库插件源码后运行 `.\scripts\restart.ps1` 即可重新加载。若列表和日志都没有该插件，运行 `.\scripts\doctor.ps1` 检查并查看 AstrBot 日志；不要仅凭仓库文件存在就视为已加载。

## 4. 配置 DeepSeek Provider

AstrBot WebUI → Providers → Chat Completion → Add，优先选择 DeepSeek 原生类型（若当前版本提供）；否则选择 OpenAI Compatible。API Key 字段填 `$DEEPSEEK_API_KEY`，Base URL 和模型按 [DeepSeek 指南](DEEPSEEK.md) 配置。获取模型并启用后，在当前 Profile 的 AI / Model 设置中选定该 Provider 和模型并保存。

## 5. 启用 OneBot v11 Adapter

AstrBot WebUI → Platforms → Add Adapter → OneBot v11：

- Enable：打开
- Reverse WebSocket host：`0.0.0.0`
- Port：`6199`
- Token：在此默认部署中留空；NapCat 官方 `MODE=astrbot` 模板也为空，且 6199 不发布到宿主机
- 保存配置

NapCat 启动时的 `MODE=astrbot` 模板会创建指向 `ws://astrbot:6199/ws` 的 Reverse WebSocket 客户端，不需要填宿主机 IP。它每次启动都覆盖 NapCat 的 `onebot11.json`，因此本项目不声称可从 `.env` 自动同步 OneBot token，也不修改持久配置文件来制造一次性的成功。若将来需要 token，应在放弃该自动模板后设计持久的两端同步配置。更详细说明见 [NAPCAT.md](NAPCAT.md)。

## 6. 扫码登录并配置插件

打开 `http://127.0.0.1:6099/webui`，查看 NapCat 日志/页面提示并用专用 QQ 账号扫码。扫码是人工步骤；NapCat 等待扫码不表示容器故障。登录后通过 AstrBot Data & Logs → Logs 确认 OneBot Adapter 已连接，也可运行 `.\scripts\doctor.ps1` 查看其日志证据。

AstrBot WebUI → Plugins → Yuuk1 Core：

- `allowed_groups`：填写允许 Bot 回应的 QQ 群号；留空时群聊默认不响应。
- `allow_private_chat`：默认 `false`，QQ 私聊静默；只在明确需要时启用。
- `admin_users`：填写可使用 `/yuuk1 status` 与 `/yuuk1 reset` 的 QQ 号。
- 默认用户级限流是每 QQ 用户每 60 秒 3 次，跨群与私聊共享；群级是每群每 60 秒 15 次。按需修改人格与两级限流后保存/重载插件。

## 7. 验证

```powershell
.\scripts\doctor.ps1
.\scripts\logs.ps1 -Service napcat
```

在白名单群中验证 @Bot 或回复 Bot 的原生唤醒、`/yuuk1 help`、管理员 `/yuuk1 status` 和 `/yuuk1 reset`。非白名单群和默认私聊应静默；普通成员不能重置共享群会话。单个用户快速请求应先命中用户额度，其他成员在群额度内仍能使用；群总量超过额度时所有成员暂时静默。真实 API 与 QQ 群行为在本人完成这些步骤前均为 **MANUAL VERIFICATION REQUIRED**。
