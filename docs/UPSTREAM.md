# 上游版本与镜像锁定

核对日期：**2026-10-07**。本项目的生产基线只采用明确的稳定版本；升级需人工检查兼容性。`scripts/check-upstream.ps1` 只报告可用版本，不修改镜像或配置。

## 当前锁定

| 组件 | 上游版本 / 源码 | 官方镜像与多架构 digest |
| --- | --- | --- |
| AstrBot | [`v4.28.2`](https://github.com/AstrBotDevs/AstrBot/releases/tag/v4.28.2)，commit [`3c7adafa1397e182d60b1016bf88759265113c8a`](https://github.com/AstrBotDevs/AstrBot/commit/3c7adafa1397e182d60b1016bf88759265113c8a) | `soulter/astrbot:v4.28.2@sha256:2215f337de16535953df936adaf34a36663d062d85b7ecffe06cdaed74f7b299` |
| NapCatQQ / NapCat-Docker | [`v4.18.33`](https://github.com/NapNeko/NapCatQQ/releases/tag/v4.18.33)，NapCatQQ commit [`ec6aadaeea38ed3bca67b82bab3d7a9c0f91b8d8`](https://github.com/NapNeko/NapCatQQ/commit/ec6aadaeea38ed3bca67b82bab3d7a9c0f91b8d8) | `mlikiowa/napcat-docker:v4.18.33@sha256:147cb18a758aa5a4dc8ef4b310e532b1dd68371a93c2e7e5bb2022aa12a05328` |

上述 digest 来自 Docker Hub 的 [AstrBot v4.28.2 tag API](https://hub.docker.com/v2/repositories/soulter/astrbot/tags/v4.28.2/) 与 [NapCat-Docker v4.18.33 tag API](https://hub.docker.com/v2/repositories/mlikiowa/napcat-docker/tags/v4.18.33/)，均为同时包含 `linux/amd64` 和 `linux/arm64` 的镜像索引 digest。Compose 中同时保留版本 tag 与 digest：tag 便于阅读，digest 固定实际拉取内容；即使上游重推同名 tag，部署仍指向核对过的镜像。AstrBot 的 [官方 Docker 部署文档](https://github.com/AstrBotDevs/AstrBot/wiki/en-deploy-astrbot-docker) 使用 `soulter/astrbot`，NapCat-Docker 的 [官方仓库](https://github.com/NapNeko/NapCat-Docker) 使用 `mlikiowa/napcat-docker`。

NapCat-Docker 官方仓库在本次审计中检查到 revision [`a97f856bb0d0bf895293520d4323cc3cd3d9495a`](https://github.com/NapNeko/NapCat-Docker/commit/a97f856bb0d0bf895293520d4323cc3cd3d9495a)，用于确认 Compose 模板、`MODE=astrbot` 和持久化目录。该仓库 revision **不作为** Docker Hub 镜像与源码逐字节对应的证明；部署身份由上述镜像 digest 固定。

## 升级与回退

1. 运行 `pwsh -File scripts/check-upstream.ps1` 查看官方 GitHub release 与 Docker Hub tag。脚本同时检查 `release.prerelease` 和 tag 名中的 `alpha`、`beta`、`rc`、`preview`、`dev`、`nightly`；例如 AstrBot `v4.29.0-beta.1` 的 GitHub `prerelease` 字段当前为 `false`，但它仍是 beta，不能被选作稳定版。
2. 阅读候选版本的发布说明。升级 AstrBot 前，重新核对 Star 加载目录、过滤器/事件钩子、Conversation API、ProviderRequest 与异常消息处理，更新 `docs/ASTRBOT_RESEARCH.md`。升级 NapCat 前，核对 AstrBot 模式的 OneBot Reverse WebSocket 模板、QQ 登录持久化路径和 WebUI 配置。
3. 停止服务，运行 `scripts/backup.ps1`，保留生成的本地备份。备份包含敏感运行数据，不能提交或上传。按正式镜像 tag 在 Docker Hub API 查到新的多架构 digest，然后同步修改 `compose.yml`、`.env.example` 和本文件的版本 / digest；若本地 `.env` 覆盖了镜像变量，也需手动同步。
4. 运行 Compose 配置检查、拉取并启动；检查容器、WebUI、Yuuk1 Core 加载、OneBot 连接以及实际 QQ 群消息。真实 DeepSeek 请求需要用户自己的密钥。
5. 若新版本不兼容，将镜像引用恢复至上表的 tag + digest 并重建容器；若上游升级迁移了持久化数据，先停止服务，再使用升级前的备份恢复数据。仅切回旧镜像并不保证能读取已迁移的数据。

不要自动跟随 `latest`、`master`、`nightly` 或 beta 镜像，也不要让 Dependabot 自动升级运行时镜像。Docker Hub 与 GitHub 的发布信息只是静态证据；首次容器启动和插件加载仍需实际 Docker 环境核验。
