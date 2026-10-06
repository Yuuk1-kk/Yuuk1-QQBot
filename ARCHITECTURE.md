# Architecture

## Runtime

```text
QQ Group → NapCatQQ → OneBot v11 Reverse WebSocket → AstrBot Adapter
         → AstrBot Pipeline / Conversation / Agent
         → Yuuk1 Core Star hooks and commands
         → AstrBot Provider → DeepSeek API
```

AstrBot is the bot runtime. It owns platform adapters, event/message pipeline, wake-up handling, profiles/personas, conversation persistence, provider selection and invocation, plugin loading, and WebUI. NapCat translates QQ transport to OneBot v11. DeepSeek is configured as an AstrBot chat provider.

## Docker and Network

- Compose creates a private `bot` bridge network shared by only `astrbot` and `napcat`.
- AstrBot listens for OneBot Reverse WebSocket on internal port `6199`; NapCat uses upstream `MODE=astrbot`, whose template connects to `ws://astrbot:6199/ws` by service DNS.
- Port 6199 is not published on the host. AstrBot WebUI 6185 and NapCat WebUI 6099 bind to `127.0.0.1` by default; `.env` can change host ports and binds.
- AstrBot state persists under `data/astrbot`; NapCat configuration and QQ login state persist under `data/napcat`.
- Compose references reviewed stable release tags and immutable multi-architecture image digests; the exact pins and upgrade procedure are in `docs/UPSTREAM.md`.
- `restart: unless-stopped`; scripts never remove bind-mounted data.

## AstrBot Integration and Star Boundary

Compose bind-mounts `./data/astrbot` at `/AstrBot/data` and the repository's `./plugins/astrbot_plugin_yuuk1_core` read-only at `/AstrBot/data/plugins/astrbot_plugin_yuuk1_core`. AstrBot v4.28.2 scans its `data/plugins` directory for a child with `main.py`, then imports `data.plugins.astrbot_plugin_yuuk1_core.main`. The nested mount puts this checkout's actual source at that discovery path. After source changes, `scripts/restart.ps1` recreates the AstrBot container so the loader imports the new code; no manual copy into `data/` is needed. The container must still be started to prove actual loading; `doctor.ps1` checks the startup log marker and WebUI plugin status can confirm it. AstrBot writes plugin configuration into its own data/config directory.

The plugin uses `on_waiting_llm_request` to apply QQ context access and two-level rate limits before provider selection and auxiliary model work; `on_llm_request` appends a stable persona supplement and sets a generic provider-error reply. It does not implement a wake-up listener or a conversation pipeline; AstrBot's native @Bot, reply, Profile, Persona, Provider, and conversation behavior remain in charge.

Project commands use the `yuuk1` command group. The QQ command group and LLM hooks deny all groups until `allowed_groups` is populated and deny private chats unless `allow_private_chat` is explicitly enabled. `/yuuk1 status` and `/yuuk1 reset` require a configured project admin. Conversation reset calls AstrBot's ConversationManager API for the current unified message origin. Status only reports whether a provider is loaded; it does not send a paid probe request or print credentials. The default in-memory limits are 3 requests per QQ user and 15 per group per 60 seconds, with the user quota shared across groups and private chats. Denied requests do not consume the other quota.

## Config and Secret Flow

- Compose interpolates `.env` variables; `.env` is untracked and ignored.
- `DEEPSEEK_API_KEY` enters only the AstrBot container environment. In the AstrBot Provider WebUI, configure its API Key field as `$DEEPSEEK_API_KEY`.
- Provider and model configuration are persisted by AstrBot. Profile model selection is persisted by AstrBot.
- Star settings come from `_conf_schema.json` and are persisted by AstrBot under `data/astrbot/config/`.
- No API key is part of plugin settings, tracked JSON, Python, or Compose source.
- NapCat `MODE=astrbot` copies its built-in OneBot template to persistent config on every startup. That template has an empty token and the private `ws://astrbot:6199/ws` URL. An `.env` token could not reliably configure both sides, so no token variable or config patcher is used. Both admin UIs remain loopback-bound and 6199 remains inside the two-service Compose network.

## Persistence

AstrBot owns conversations and provider/profile state in its data directory. NapCat owns its runtime configuration and QQ session data under `data/napcat`. Yuuk1 Core stores no custom persistent state; the limiter uses process memory and resets on restart. `scripts/backup.ps1` requires the stack to be stopped, archives AstrBot data and NapCat configuration while excluding logs/cache/temp files, and writes to ignored `backups/`. The optional `-IncludeQQSession` also archives NapCat QQ login state; restoring the default backup into an empty deployment requires another QR login.

## Upgrade Strategy

1. Stop the services and run `scripts/backup.ps1`, with `-IncludeQQSession` only when the login state is required.
2. Check official releases, image digests, and Star API compatibility as described in `docs/UPSTREAM.md`; update Compose, `.env.example`, and any local `.env` override deliberately.
3. Pull and recreate containers, then review AstrBot/NapCat logs, run `doctor.ps1`, and verify the actual QQ and Provider flows.
4. Keep the Star compatibility range bounded in `metadata.yaml`; update `docs/ASTRBOT_RESEARCH.md` when adopting a newer API.

See `docs/ASTRBOT_RESEARCH.md` for inspected APIs and `docs/UPSTREAM.md` for release and rollback policy.
