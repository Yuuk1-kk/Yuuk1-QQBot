# DeepSeek Provider

Yuuk1 Core 不创建 DeepSeek 客户端。所有请求由 AstrBot Provider 和它的 Profile / Conversation 流程发起。

## 获取 Key

在 [DeepSeek Platform](https://platform.deepseek.com/) 登录后前往 API Keys 创建 Key。将其写入本地 `.env` 的 `DEEPSEEK_API_KEY`。不要粘贴到插件配置、Issue、群聊或跟踪文件。

## AstrBot 配置

1. 在 AstrBot WebUI → Providers → Chat Completion → Add 中优先选择 DeepSeek 原生 Provider（如果当前版本提供）。
2. API Key 字段填写字面量 `$DEEPSEEK_API_KEY`。Compose 将 `.env` 中的变量传入 AstrBot 容器，AstrBot 在 Provider 层读取该环境变量。
3. 若使用 OpenAI Compatible 类型，Base URL 可填 `https://api.deepseek.com/v1`（DeepSeek 官方兼容 OpenAI 格式；官方请求示例的根地址是 `https://api.deepseek.com`）。
4. 获取并启用模型，然后在当前 Profile 的 AI / Model 配置中选为对话模型并保存。
5. 可用 AstrBot Provider 页面中的 Test Model 测试，然后在 QQ 群验证完整链路。

## 模型

截至本项目研究时，DeepSeek 官方 API 文档的快速开始列出 `deepseek-flash` 与 `deepseek-v4-pro`；更新日志也介绍了 `deepseek-v4-flash` 名称。文档对 Flash 标识存在新旧命名并列的情况，因此优先以 AstrBot 获取到的官方模型列表及 DeepSeek 当前 API 文档为准；初始建议选用官方 Chat Completions / Quick Start 当前展示的 `deepseek-flash`。模型名称不写死在本项目代码中。

## 验证与排查

- 插件 `/yuuk1 status` 仅查看当前会话是否有已加载 Provider 和模型名，不会发送 API 测试请求。
- 使用 AstrBot Provider 的 Test Model 或实际 QQ 群消息验证 Key、模型和网络。
- 未配置/未加载 Provider 时检查 Profile 选择、模型是否启用、容器是否收到 `DEEPSEEK_API_KEY`。
- 更换 `.env` 中 Key 后运行 `scripts/restart.ps1`，并在 AstrBot Provider 页面确认其仍引用 `$DEEPSEEK_API_KEY`。

官方来源：

- [DeepSeek Your First API Call](https://api-docs.deepseek.com/quick_start/)
- [DeepSeek Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)
- [DeepSeek API Updates](https://api-docs.deepseek.com/updates/)
- [AstrBot Connecting Model Services](https://docs.astrbot.app/en/providers/start.html)
