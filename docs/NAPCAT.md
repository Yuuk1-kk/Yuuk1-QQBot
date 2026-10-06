# NapCatQQ 与 OneBot v11

## QQ 账号

建议为 Bot 使用专用 QQ 小号，完成必要的安全设置，并按 QQ 与 NapCat 当前规则使用。不要在仓库、截图或日志中公开账号凭据、二维码或会话文件。首次登录必须由账号所有者本人扫码。

## WebUI

NapCat WebUI 默认在 `http://127.0.0.1:6099/webui`。NapCat 的 QQ 登录态保存在 `data/napcat/qq`，运行配置保存在 `data/napcat/config`；整个 `data/` 已从 Git 排除。不要把 6099 映射到公网。

端口可在 `.env` 中修改。默认绑定 `127.0.0.1`；只有在已有受控 VPN/防火墙等访问路径时才调整 bind 地址。

## OneBot v11 Reverse WebSocket

连接方向由 AstrBot 官方 OneBot 文档确认：AstrBot 是 Reverse WebSocket 服务端，NapCat 是客户端。NapCat-Docker 的官方 `MODE=astrbot` 模板设置：

```text
ws://astrbot:6199/ws
```

Compose 中的 `astrbot` 是 Docker 服务名。不要改成容器里的 `localhost`、宿主机 IP 或 Windows 主机名。6199 不发布到宿主机，只供同一私有 Docker 网络内的 NapCat 使用。

在 AstrBot WebUI 的 Platforms 中添加并启用 OneBot v11，设置 Reverse WebSocket host 为 `0.0.0.0`、port 为 `6199`。NapCat 官方模板默认 token 为空，因此 AstrBot Token 也留空。

`MODE=astrbot` 的启动脚本每次都会把内置 `astrbot.json` 复制为 `/app/napcat/config/onebot11.json`。因此，在 NapCat WebUI 手动填写的 OneBot token 下次启动可能被清空；只在 `.env` 增加一个 token 变量也不能自动同步 AstrBot 和 NapCat。本项目保留默认空 token，并用只含两个服务的 Compose 网络及不发布 6199 的端口配置限制入口。如果改成跨主机、共享网络或公开入口，必须另行设计持久的双端 token 配置，不应沿用这个默认模板。

## 如何验证

1. `docker compose ps` 显示两个服务为 running。
2. AstrBot Data & Logs → Logs 中看到 OneBot v11 Adapter 已连接的日志；日志措辞可能因版本不同。
3. `scripts/doctor.ps1` 检查容器、网络和已连接的日志证据。
4. NapCat 已扫码登录后，在白名单群测试 @Bot 或回复 Bot。

日志和网络检查只能验证连接的部分证据；QQ 已登录及群消息往返需要人工确认。等待扫码应显示为 `[MANUAL]`，不是服务失败。

## 常见问题

- **NapCat 连不上 AstrBot：**检查 AstrBot OneBot v11 Adapter 是否启用，host 是否为 `0.0.0.0`，port 是否为 `6199`；检查两项服务位于 `bot` 网络。
- **配置写了 localhost：**容器中的 localhost 指自己。NapCat 必须连服务名 `astrbot`。
- **WebUI 打不开：**检查服务状态和 `.env` 中端口；若端口冲突，改 `ASTRBOT_WEBUI_PORT` 或 `NAPCAT_WEBUI_PORT` 再重启。
- **扫码/登录失败：**查看 `scripts/logs.ps1 -Service napcat`；按 NapCat 当前版本支持的客户端与登录规则处理。
- **QQ 已登录但 Bot 不回话：**确认 OneBot 已连接、AstrBot Profile 已选择模型、Yuuk1 Core 已加载、当前群号在 `allowed_groups` 中且触发方式符合 AstrBot Profile 设置；默认 QQ 私聊关闭，并检查用户级与群级限流。
