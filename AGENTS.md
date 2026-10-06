# Repository Guidance

## 文档优先级

发生冲突时依次参考：`PROJECT_PLAN.md` → `AGENTS.md` → `ARCHITECTURE.md` → `PROGRESS.md`。上游 AstrBot 当前官方源码和文档用于核验 API 与运行时事实；更新研究结论写入 `docs/ASTRBOT_RESEARCH.md`。

## Secret Policy

- 不提交真实 API Key、QQ 账号凭据、NapCat WebUI token、Cookie、Session、数据库、日志或 `.env`。
- 只能在 `.env.example` 使用明确占位值。脚本不可生成 Secret，也不可打印 Secret。
- 不通过插件回复或日志输出 Secret；异常回复保持通用，日志如需 traceback 先脱敏。

## AstrBot Upstream Boundary

- AstrBot 是 Runtime / Core；NapCat 是 QQ transport；DeepSeek 通过 AstrBot Provider 接入。
- 不 fork AstrBot Core，原则上不得改动 `astrbot/core/`。优先使用 Star、配置、事件钩子、过滤器、Provider 和 Profile API。
- 插件不得另建会话数据库、LLM Provider、平台适配器、消息流水线或 WebUI。
- 不确定 API 时，先查当前官方源码和文档，再实现并更新研究文档。

## 修改后验证

- 运行插件纯逻辑测试、Python 语法检查和 Ruff。
- 修改 PowerShell 时解析全部脚本；修改 Compose 时执行 `docker compose config --quiet`（需要 Docker CLI）。
- 检查 Star metadata、Schema、Compose 网络和挂载路径；运行 Secret scan。
- 真实 Provider、QQ 登录和群聊行为只有在实际外部凭据可用时才可标记通过。

## Git Rules

- 默认分支 `main`。不自动 push 到未知 remote。
- 不覆盖或删除仓库外用户文件；不提交运行数据与 Secret。
- 提交应小且说明目的。当前 v0.1 首提建议 `feat: bootstrap AstrBot QQ AI bot`。

## Stop Conditions

只有缺少真实 Secret、需要用户扫码 QQ、需要不可逆外部授权，或遇到无法合理判断的重大架构冲突时，才请求用户介入。普通实现选择由维护者按上游规范决定。不能验证的外部行为须如实标记 `MANUAL VERIFICATION REQUIRED`。
