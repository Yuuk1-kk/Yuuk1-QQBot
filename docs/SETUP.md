# Setup

本指南从 Clone 仓库到在 QQ 群验证 Bot。真实 DeepSeek Key 和 QQ 扫码需由你本人提供/完成。

## 1. 准备环境

安装并启动 Docker Desktop，确认使用 Linux containers，并使用 Docker Compose v2。Clone 后在仓库根目录打开 PowerShell：

```powershell
git clone <your-repository-url> Yuuk1-QQBot
Set-Location .\Yuuk1-QQBot
.\scripts\bootstrap.ps1
```

`bootstrap.ps1` 在 `.env` 不存在时从 `.env.example` 复制占位文件，并创建 AstrBot、NapCat 数据目录。它不会生成密钥。

## 2. 设置 DeepSeek Key

用编辑器打开 `.env`，只在本机将 `DEEPSEEK_API_KEY=replace-me` 改成你的真实 Key。该文件已被 Git 忽略。详细 Provider 步骤见 [DEEPSEEK.md](DEEPSEEK.md)。

## 3. 启动容器

```powershell
.\scripts\start.ps1
.\scripts\logs.ps1 -Service astrbot
```

首次启动时，AstrBot 日志会显示管理面板登录信息。打开 `http://127.0.0.1:6185`，登录后按 AstrBot 提示修改初始密码。NapCat WebUI 位于 `http://127.0.0.1:6099/webui`。

## 4. 配置 DeepSeek Provider

AstrBot WebUI → Providers → Chat Completion → Add，优先选择 DeepSeek 原生类型（若当前版本提供）；否则选择 OpenAI Compatible。API Key 字段填 `$DEEPSEEK_API_KEY`，Base URL 和模型按 [DeepSeek 指南](DEEPSEEK.md) 配置。获取模型并启用后，在当前 Profile 的 AI / Model 设置中选定该 Provider 和模型并保存。

## 5. 启用 OneBot v11 Adapter

AstrBot WebUI → Platforms → Add Adapter → OneBot v11：

- Enable：打开
- Reverse WebSocket host：`0.0.0.0`
- Port：`6199`
- Token：留空（NapCat 官方 `MODE=astrbot` 模板默认不设置 Token；端口只在 Compose 私有网络内开放）
- 保存配置

NapCat Compose 模板会连 `ws://astrbot:6199/ws`，不需要填宿主机 IP。更详细说明见 [NAPCAT.md](NAPCAT.md)。

## 6. 扫码登录并配置插件

打开 `http://127.0.0.1:6099/webui`，查看 NapCat 日志/页面提示并用专用 QQ 账号扫码。登录成功后，AstrBot Data & Logs → Logs 应出现 OneBot adapter 已连接的日志。

AstrBot WebUI → Plugins → Yuuk1 Core：

- `allowed_groups`：填写允许 Bot 回应的 QQ 群号；留空时群聊默认不响应。
- `admin_users`：填写可使用 `/yuuk1 status` 与 `/yuuk1 reset` 的 QQ 号。
- 按需修改人格与限流值，然后保存/重载插件。

## 7. 验证

```powershell
.\scripts\doctor.ps1
.\scripts\logs.ps1 -Service napcat
```

在白名单群中验证 @Bot 或回复 Bot 的原生唤醒、`/yuuk1 help`、管理员 `/yuuk1 status` 和 `/yuuk1 reset`。非白名单群应静默。真实 API 和 QQ 群行为在本人完成这些步骤前均为 **MANUAL VERIFICATION REQUIRED**。
