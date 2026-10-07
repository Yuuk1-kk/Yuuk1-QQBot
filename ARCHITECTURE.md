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

The plugin uses `on_waiting_llm_request` to apply QQ context access and two-level rate limits before provider selection and auxiliary model work; `on_llm_request` appends a stable persona supplement and sets a generic provider-error reply. It does not replace AstrBot's wake-up handling or conversation pipeline. An optional group-message observer only buffers allowed group messages and starts the separately gated Free Talk flow; ordinary @/wake requests stay on AstrBot's native path.

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

## Optional group participation

When both optional settings are off, the plugin does not retain group-message context and sends no proactive messages. With Free Talk or Idle Presence enabled, a Star handler observes only allowed QQ group messages and stores a bounded, TTL-pruned in-memory summary per unified group session. It stores sanitized text/placeholders and display name or process-local alias, never a raw event or raw message object.

IDLE ordinary Free Talk applies allowlist/self/command/recent-activity gates, the default 0.35 probability, and one short Provider decision request. There is no Free Talk time cooldown; the project security limiter remains at 8 requests/user/60s and 30 requests/group/60s by default. A direct nickname address at the start of a message and a Reply whose resolved sender is the bot bypass the generic probability and classifier. After a successful bot turn, the group enters an in-memory ENGAGED state for 300 seconds. In that state, explicit continuation/direct cues and replies to the bot go straight to the native Agent path, explicit replies to another person are silent, and ambiguous messages use the existing single decision request to classify relevance. The timeout refreshes only after the entire reply turn sends successfully. SILENT yields no `ProviderRequest`; a selected response yields one `event.request_llm` with the current Conversation into AstrBot's regular AgentRequestSubStage. That native path selects the current Provider, applies the selected Persona and tools (including Web Search), and writes one answer to the current Conversation.

After one final QQ group LLM result is produced, the pre-send hook may keep its first natural text part in AstrBot's result pipeline and queue up to two follow-up text parts. AstrBot sends the first part normally; the after-send hook sends follow-up parts with a short delay, followed by any selected sticker. This does not create extra Agent or Provider generations. Short text, code, URLs, and recognized Markdown structures stay together. Bot-authored follow-up messages are rejected by the observer's existing self-message check.

The bounded group context is added only to the SPEAK request's user content as a `TextPart.mark_as_temp()` value. It never changes the stable system prompt or persisted Conversation. Sticker output is a registered `jingjing_sticker` Agent tool that selects only local, signature-checked PNG/JPG/JPEG assets; text-plus-sticker sends text first and image afterward so a failed image send cannot cancel the text. Asset categories and user-owned resources are under the plugin's `assets/stickers/` directory.

Idle Presence uses a single optional task owned by plugin `initialize()` / `terminate()`. It has no target until an allowed group message has been observed, respects an idle threshold, attempt gap and local active-hours window, and uses `Context.send_message()` with the in-memory unified session. Its one-shot generation reads the current selected Persona and Provider without writing to the AstrBot Conversation or running tools. Free Talk, Stickers, and Idle Presence switches default off; engagement defaults on but remains inert while Free Talk is off.
