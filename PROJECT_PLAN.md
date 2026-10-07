# 项目计划

## v0.1：基础 QQ AI Bot

- AstrBot + NapCat Compose 部署与持久化
- OneBot v11 Reverse WebSocket
- DeepSeek 通过 AstrBot Provider 接入
- Yuuk1 Core Star：群白名单、项目管理员、人格补充、状态/帮助/重置命令、群级内存限流
- Group Identity Context v1 — VERIFIED：发送者名称优先使用群名片 card，回退 nickname；每群稳定 HMAC 身份、当前名称和最多 5 个 alias 持久化。identity_secret 与 group_identity.json 必须一起备份。上下文用 [显示名] 消息 标注，重名才加匿名短标签；ENGAGED 复用 member identity。用户 QQ E2E 已通过。
- Windows PowerShell 管理脚本、操作文档与纯逻辑测试

## v0.2：更自然的群聊体验（尚未开始）

Group Identity Context v1 是当前 v0.1 stabilization 范围内的身份/名称上下文，不是跨用户画像或长期个人记忆。

- 主动参与概率
- 对引用/回复关系的更自然理解
- 用户级人格上下文
- 图片理解体验
- 更丰富的项目命令

## v0.3：扩展能力（暂不实现）

- Web search、Bilibili、Bangumi、Steam、GitHub、天气查询
- 群聊摘要

扩展优先使用 AstrBot Star、工具、Provider 和其他公开扩展 API；不 fork AstrBot Core。
