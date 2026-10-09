# 项目计划

## v0.1：基础 QQ AI Bot

- AstrBot + NapCat Compose 部署与持久化
- OneBot v11 Reverse WebSocket
- DeepSeek 通过 AstrBot Provider 接入
- Yuuk1 Core Star：群白名单、项目管理员、人格补充、状态/帮助/重置命令、群级内存限流
- Group Identity Context v1 — VERIFIED：发送者名称优先使用群名片 card，回退 nickname；每群稳定 HMAC 身份、当前名称和最多 5 个 alias 持久化。identity_secret 与 group_identity.json 必须一起备份。上下文用 [显示名] 消息 标注，重名才加匿名短标签；ENGAGED 复用 member identity。用户 QQ E2E 已通过。
- Jingjing Free Talk v1 — VERIFIED：IDLE 普通消息概率 0.35；direct / @ / Reply 明确回复；ENGAGED 连续对话 300 秒且无聊天 cooldown；安全限流为每用户 8/60 秒、每群 30/60 秒；最多三条 QQ 消息。用户 QQ E2E 已通过。
- Jingjing Stickers v1 — VERIFIED：`jingjing_sticker(category)` 固定类别工具、本地安全图片目录、PNG/JPG/JPEG 运行时校验、SHA-256 内存重复抑制、单轮最多一图、文字先发/贴图后发及 image-only / failure fallback。用户 QQ E2E 已通过。
- QQ Custom Sticker v1 — 核心路径 E2E PASS（已知限制单独记录）：默认 `sticker_send_mode=image` 保持普通图片模式；`qq_custom` 发送 OneBot image `sub_type=1`。最新用户手动 QQ E2E 确认普通文字、文字+自定义表情、纯表情、昵称唤醒及 image 模式兼容通过，客户端可收藏自定义表情。Ambiguous/NTEvent 超时不自动重发和每轮最多一张已由本地模拟测试验证；修复后尚未再次触发真实 NTEvent 超时。历史上的 `(图)` / `(表情已发出)`、工具调用后空 completion、Agent 错误后可能仍发送已选 Sticker，以及真实 AstrBot Stage 空链 guard 集成覆盖缺口仍保留；上下文体积与空 completion 的因果关系未确认。
- Windows PowerShell 管理脚本、操作文档与纯逻辑测试

下一阶段建议：Cloud Deployment v1。该阶段尚未开始，本轮没有进行部署迁移或云端配置。

## v0.2：更自然的群聊体验（未整体启动）

Group Identity Context v1 是当前 v0.1 stabilization 范围内的身份/名称上下文，不是跨用户画像或长期个人记忆。

- Owner Identity v1 — VERIFIED（确定性身份问答 QQ E2E）：用户确认部署后完整真实 QQ E2E 全部通过。明确且直接面向鲸鲸的身份问答由当前可信 QQ sender ID 分类决定答复，避免 LLM 自行判断主人身份；未命中的自由聊天继续走原模型流程。昵称、自称、@、引用和共享历史不参与认证；不注入原始 QQ 号，不修改全局 Persona 或管理员权限。Owner 诊断默认关闭，当前运行配置已为 false。此验收保证范围限于规则识别到的明确身份问答。
- Relationship Memory Store Foundation — IMPLEMENTED / LOCALLY VERIFIED：使用标准库 SQLite 存放由 Group Identity HMAC 键限定的事实记录，支持事务 CRUD、版本替换和清除正文的删除。完整 Relationship Memory v1 尚未完成；Memory Injection 与 Controlled Memory Writing 均未开始。

- 主动参与概率
- 对引用/回复关系的更自然理解
- 用户级人格上下文
- 图片理解体验
- 更丰富的项目命令

## v0.3：扩展能力（暂不实现）

- Web search、Bilibili、Bangumi、Steam、GitHub、天气查询
- 群聊摘要

扩展优先使用 AstrBot Star、工具、Provider 和其他公开扩展 API；不 fork AstrBot Core。
