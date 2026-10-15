# Operations

以下命令在仓库根目录 PowerShell 中执行。

## Start / Stop / Restart

```powershell
.\scripts\start.ps1
.\scripts\stop.ps1
.\scripts\restart.ps1
```

`stop.ps1` 会执行 Compose down，但不删除 bind-mounted `data/`。不要使用 `docker compose down -v` 作为日常停机命令。

修改仓库中的 Yuuk1 Core 源码后运行 `restart.ps1`。Compose 的只读 bind mount 会把 `plugins/astrbot_plugin_yuuk1_core` 映射到 AstrBot 的 `data/plugins` 发现目录，无需复制文件。重启后用 `doctor.ps1` 和 AstrBot 插件列表确认实际加载。

## Logs

```powershell
.\scripts\logs.ps1
.\scripts\logs.ps1 -Service astrbot -Tail 200
.\scripts\logs.ps1 -Service napcat
```

日志和 NapCat 运行数据包含账号与运行信息，按敏感数据保护；排障贴日志前先检查并脱敏。

## QQ 群 Conversation 管理 v1

Conversation Management v1 已通过 AstrBot WebUI 单插件热重载进入运行时。AstrBot 管理行为页面确认 `/jjctx current`、`/jjctx list`、`/jjctx new` 和 `/jjctx switch` 已启用；OneBot 连接、插件初始化和当前 Persona 已核验。用户随后确认真实 QQ E2E 成功，原 Conversation 历史仍保留。插件热重载会清空 Yuuk1 Core 进程内的 Free Talk 临时上下文，不会清除 Conversation 历史。

### 权限与无响应故障记录（2026-10-14）

新版代码将 `/jjctx` 的权限限制在插件范围内，要求三个条件同时满足：事件来自受支持的 OneBot QQ 群聊；当前群和事件 UMO 与插件 `allowed_groups` 相符；`event.get_sender_id()` 精确命中 Yuuk1 Core `admin_users`。命令组过滤器在分发前检查一次，每个处理器在读取或改动 Conversation 前再检查一次。Owner 身份、昵称、自称、群名片、引用消息、QQ 群管理员身份和 AstrBot 全局管理员身份都不能替代这些条件。

故障起因是 AstrBot v4.28.2 的 `event.is_admin()` 表示 AstrBot 管理员角色。平台配置里的 `admins_id` 与 `unique_session` 决定该角色或隔离标记；QQ 群管理员角色不会自动成为 `event.is_admin()`。此前只在 Yuuk1 Core `admin_users` 中配置的 QQ 管理员也会被 AstrBot 原生权限层拒绝。原装饰器使用 `SHARED_GROUP_ADMIN, raise_error=False`，该层会静默跳过处理器；旧版 Yuuk1 自定义过滤器也会直接停止事件，且没有回复。这解释了 `/help` 可正常回复而 `/jjctx` 无响应。用户已确认修复后真实 QQ 命令测试成功；账号标识未写入文档。

为消除 AstrBot v4.28.2 `SHARED_GROUP_ADMIN` 的额外全局权限门槛，`/jjctx` 子命令采用 `PermissionType.MEMBER`，再由组级过滤器、各子命令过滤器和处理器中的同一确定性项目检查共同保护。AstrBot 的 `MEMBER` 过滤器允许命令通过原生权限层，但未经项目授权的请求会在处理器前停止，不能读取会话列表或改动选择指针。过滤器拒绝时发送固定且不含账号、群或会话标识的提示；WakingCheck 已停止事件后，后续过滤器只返回拒绝，避免重复提示。无需扩大 AstrBot 全局管理员名单，也无需开启 `unique_session`。

运行时热重载后，AstrBot 管理行为页面列出上述四条 `/jjctx` 命令且均已启用。Yuuk1 Core 初始化、Group Identity、Relationship Memory Store、Sticker 子系统及 OneBot 连接检查正常；Persona 仍为「鲸鲸v1.1」，重载前后的目标群 Conversation 指针一致。用户随后确认真实 QQ E2E 成功。代码中的权限过滤与处理器检查共同执行项目级授权；管理行为页面中的 AstrBot 命令权限显示“所有人”代表使用 MEMBER 入口，本身不代表所有群成员能通过插件授权。

| 命令 | 作用 |
| --- | --- |
| `/jjctx new` | 通过 AstrBot ConversationManager 新建并选中 Conversation，保留原 Conversation 历史和 Persona 绑定 |
| `/jjctx current` | 查看本群当前 Conversation、创建时间和可解析的 Persona |
| `/jjctx list [page]` | 分页列出本群 Conversation；不显示消息正文 |
| `/jjctx switch <ID>` | 切换到本群已有 Conversation；接受完整 UUID 或唯一的至少 8 位十六进制前缀 |
| `/new` | AstrBot 原生命令：新建空 Conversation，保留旧历史；仍受 AstrBot `SHARED_GROUP_ADMIN` 限制 |

此次无损体验不要执行项目的 `/yuuk1 reset`：它会删除当前 AstrBot Conversation，与原生 `/new` 的保留旧历史行为不同。

每次计划执行生产 Conversation 新建或切换前，用 `/jjctx current` 和 `/jjctx list` 记录**完整的旧 Conversation ID**。需要可恢复的生产快照时，使用 `sqlite3.Connection.backup()` 在线备份运行中的 `data/astrbot/data_v4.db`，把备份放在仓库外受限目录，并检查备份的 `PRAGMA integrity_check` 与 `conversations` 记录数；备份失败则停止切换。运行中的数据库不可直接复制单个 `.db` 文件替代在线备份；仓库原有 `scripts/backup.ps1` 是停机备份流程。

可在仓库根目录的 PowerShell 执行以下在线备份示例；输入的目录须在仓库外，并由本人限制访问。它只输出备份路径与记录数，不输出聊天内容：

```powershell
$jjctxBackupDir = Read-Host '输入仓库外备份目录'
@'
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
import sys

repo = Path.cwd().resolve()
source = (repo / "data/astrbot/data_v4.db").resolve(strict=True)
directory = Path(sys.argv[1]).expanduser()
if not directory.is_absolute():
    raise SystemExit("备份目录必须是绝对路径")
directory = directory.resolve()
if directory == repo or repo in directory.parents:
    raise SystemExit("备份目录必须位于仓库外")
directory.mkdir(parents=True, exist_ok=True)
target = directory / ("astrbot-data_v4-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".db")
if target.exists():
    raise SystemExit("目标备份已存在")
try:
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30)) as live:
        with closing(sqlite3.connect(target, timeout=30)) as backup:
            live.backup(backup)
    with closing(sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)) as verify:
        integrity = verify.execute("PRAGMA integrity_check").fetchone()[0]
        count = verify.execute("SELECT count(*) FROM conversations").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError("备份完整性检查未通过")
except Exception:
    target.unlink(missing_ok=True)
    raise
print(f"备份：{target}\nConversation 记录数：{count}\n完整性：{integrity}")
'@ | python - $jjctxBackupDir
```

先确认群内没有正在执行的任务，再由配置中的维护者手动执行 `/jjctx new`。它会沿用当前 Conversation 的 Persona，读回确认新指针，并确认原群 Conversation 记录仍存在；如需返回旧历史，执行 `/jjctx switch <完整旧 ID>`，之后仍可切回新 ID。切换和新建都拒绝已观察到的活动任务或无法确认的状态。AstrBot 上游没有提供与新任务注册原子协调的锁，因此仍应在群安静时操作；此检查不能阻止检查完成后立即到达的新消息。新建不会删除旧 Conversation 或清空 Yuuk1 Core Free Talk 缓存；人格体验对照前建议等待至少 15 分钟无相关群聊消息与鲸鲸回复，让缓存自然过期。

如果 `/jjctx switch` 暂时不可用，先保留旧 ID 与备份；获得用户批准后重载插件或只重启 AstrBot，使命令恢复，再切回旧 ID。完整数据库恢复仅作为最后手段：需要停服、先另存当前数据，并接受备份之后的新 Conversation 与其他运行数据可能丢失；不得用数据库 SQL 直接改当前会话指针。

## Owner Identity v1.1.1 运行时与 QQ 部分验收

用户确认已手动热重载 Yuuk1 Core。用户在一个新 Conversation 中确认 Owner 关系与机器人确定性回复引用测试表现正常；此结果为部分 QQ E2E，不能代表其他群聊、私聊和引用边界场景都已通过。热重载不会清空 AstrBot Conversation；它会清除进程内 Free Talk 临时缓存。不要为后续验收修改 Owner ID、管理员名单、Persona 或 Provider。

用户在 QQ 中按下列顺序手动验收；每次只记录当前发言者身份分类、处理路径以及引用结果是已验证还是 UNKNOWN，不保存聊天正文或完整账号：

1. Owner 在私聊和目标群分别问一次直接身份问题，并在群名片变更后再问一次；直接身份答案应跟随可信 sender ID，读名字时只使用当前显示名。
2. 普通群友改用 `Yuuk1` 昵称并自称主人；再与 Owner 交错发言。昵称和自称不能改变主人关系，也不能使身份状态串到另一位发言者。
3. Owner 自然要求“以后叫我老大”，再问一次与鲸鲸的关系。观察称呼偏好是否自然处理；单独拒绝一个称呼不代表 Owner 身份认证失败。
4. 分别引用鲸鲸的一条确定性身份回复、一条普通回复和一条群友消息，询问“那这是谁发的？”或“这句是你说的吗？”。真实 bot/成员来源应与 OneBot 元数据一致；缺失群号、查询失败或不一致时应回答无法可靠核实，不应猜昵称。
5. 继续一次自然闲聊，并检查 `/jjctx current`。若引用来源返回 UNKNOWN，记录当时 QQ 类型/阶段，不要开启会记录完整 Prompt 的 AstrBot trace。

验收时区分当前 sender 的可信分类、请求进入确定性还是 Agent 路径、以及最终回复。直接身份答复正确不等于自由聊天整体通过；对没有请求级证据的历史截图，不把 Free Talk、Conversation 或 Provider 单独认定为根因。

## Update

1. 停止服务，运行 `scripts/backup.ps1` 创建升级前备份；若回滚时必须保留现有 QQ 登录态，显式加 `-IncludeQQSession`。
2. 运行 `scripts/check-upstream.ps1`，查看 [UPSTREAM.md](UPSTREAM.md) 的锁定版本、官方 release 和镜像 digest；检查 [ASTRBOT_RESEARCH.md](ASTRBOT_RESEARCH.md) 的 Star API 兼容面。`v4.29.0-beta.1` 等 tag 即使 GitHub metadata 标记不可靠，仍按 beta 处理。
3. 核实候选镜像的稳定 tag 与多架构 digest，同步更新 `compose.yml`、`.env.example`、`docs/UPSTREAM.md`，并检查本地 `.env` 的覆盖值。确认后执行：

```powershell
docker compose config --quiet
docker compose pull
.\scripts\restart.ps1
.\scripts\doctor.ps1
```

4. 查看 AstrBot 与 NapCat 日志、Yuuk1 Core 加载状态，再做 Provider、Adapter 和 QQ 群真实消息验证。升级失败时恢复旧镜像 pin；如果数据已被新版本迁移，停止服务后再用升级前备份恢复。不要自动跟随 `latest` 或 beta。

## Backup / Restore

先停掉 Bot，运行仓库提供的备份脚本：

```powershell
.\scripts\stop.ps1
.\scripts\backup.ps1
```

默认备份包括 `data/astrbot` 和 `data/napcat/config`，排除日志、缓存与临时文件。若需要同时保留 NapCat QQ 登录态，显式运行 `.\scripts\backup.ps1 -IncludeQQSession`；否则恢复后需要重新扫码。脚本将带时间戳的 ZIP 放在已忽略的 `backups/`，不会上传。备份包含会话和配置等敏感数据，应加密并限制访问。

恢复时保持服务停止，先确认当前 `data/` 另有保留，再把选定 ZIP 中的 `data/` 文件还原到仓库根目录。恢复会覆盖对应现有文件；确认备份来源和目标路径后再操作，然后启动服务、运行 `doctor.ps1` 并进行手工消息验证。

## Troubleshooting

- Compose 配置：`docker compose config --quiet`
- 容器状态与端口探测：`.\scripts\doctor.ps1`
- AstrBot 日志：`.\scripts\logs.ps1 -Service astrbot`
- NapCat 日志：`.\scripts\logs.ps1 -Service napcat`
- Adapter：AstrBot 在容器内监听 `0.0.0.0:6199`，NapCat 使用 `ws://astrbot:6199/ws`；6199 不发布到宿主机。`MODE=astrbot` 每次启动覆盖 NapCat 的 OneBot 模板，默认 token 为空。
- No provider：检查环境变量名、AstrBot Provider API Key 值 `$DEEPSEEK_API_KEY`、模型启用状态和当前 Profile。
- No group reply：确认插件已加载、群号已在白名单中、原生唤醒设置已满足，且该用户及全群都未触发限流；私聊默认关闭。

修复后再次运行 `doctor.ps1` 和实际群聊验证。诊断结果区分 `[PASS]`、`[WARN]`、`[FAIL]`、`[MANUAL]`；需要用户扫码或真实 API 请求的步骤不能由诊断脚本伪造。
