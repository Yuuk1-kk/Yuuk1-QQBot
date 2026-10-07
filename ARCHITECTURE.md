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
- Star settings come from _conf_schema.json and are persisted by AstrBot under data/astrbot/config/astrbot_plugin_yuuk1_core_config.json. Group identity private state uses StarTools.get_data_dir("astrbot_plugin_yuuk1_core"), which resolves inside the bind-mounted AstrBot data tree.
- No API key is part of plugin settings, tracked JSON, Python, or Compose source.
- NapCat `MODE=astrbot` copies its built-in OneBot template to persistent config on every startup. That template has an empty token and the private `ws://astrbot:6199/ws` URL. An `.env` token could not reliably configure both sides, so no token variable or config patcher is used. Both admin UIs remain loopback-bound and 6199 remains inside the two-service Compose network.

## Group Identity Context v1 — VERIFIED

AstrBot v4.28.2 resolves the sender display name from the group card (`card`) first and the sender nickname (`nickname`) as fallback. A stable per-group member key uses domain-separated HMAC-SHA256 over platform, group, and user identifiers; the raw identifiers are not persisted or included in logs or model context. Current name and up to five aliases are persisted in the bounded JSON identity store.

The `identity_secret` and `group_identity.json` files must be backed up and restored together with `data/astrbot/config/astrbot_plugin_yuuk1_core_config.json`. Dynamic context is rendered as `[display name] message`; only duplicate names receive a short anonymous suffix. ENGAGED reuses the same per-group member key. The user confirmed sender identification, A/B attribution, rename updates, AstrBot restart recovery, persistent storage, and ENGAGED continuity by QQ E2E.

## Persistence

AstrBot owns conversations, provider/profile state, and Yuuk1 Core plugin data in its data directory. NapCat owns its runtime configuration and QQ session data under data/napcat. Group Identity Context v1 stores a random 32-byte HMAC secret at data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/identity_secret and an atomically replaced JSON store at data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/group_identity.json. The store contains only group/member HMAC keys, current names, at most five aliases, and first/last seen timestamps; raw QQ/group IDs and message history are not persisted. The user/group rate limiter and recent message context remain in process memory. scripts/backup.ps1 requires the stack to be stopped and archives all AstrBot data (including the two identity files and data/astrbot/config/astrbot_plugin_yuuk1_core_config.json) plus NapCat configuration while excluding logs/cache/temp files. It writes only to ignored backups/; the optional -IncludeQQSession also archives NapCat QQ login state.

## Upgrade Strategy

1. Stop the services and run `scripts/backup.ps1`, with `-IncludeQQSession` only when the login state is required.
2. Check official releases, image digests, and Star API compatibility as described in `docs/UPSTREAM.md`; update Compose, `.env.example`, and any local `.env` override deliberately.
3. Pull and recreate containers, then review AstrBot/NapCat logs, run `doctor.ps1`, and verify the actual QQ and Provider flows.
4. Keep the Star compatibility range bounded in `metadata.yaml`; update `docs/ASTRBOT_RESEARCH.md` when adopting a newer API.

See `docs/ASTRBOT_RESEARCH.md` for inspected APIs and `docs/UPSTREAM.md` for release and rollback policy.

## Optional group participation

Group Identity Context is enabled by default and observes allowed QQ group messages only to update a bounded persistent name mapping. Free Talk and Idle Presence remain separate optional switches; when either is enabled, the observer also stores a bounded, TTL-pruned in-memory message summary per unified group session. It stores sanitized text/placeholders and speaker attribution, never a raw event or raw message object.

IDLE ordinary Free Talk applies allowlist/self/command/recent-activity gates, the default 0.35 probability, and one short Provider decision request. There is no Free Talk time cooldown; the project security limiter remains at 8 requests/user/60s and 30 requests/group/60s by default. A direct nickname address at the start of a message and a Reply whose resolved sender is the bot bypass the generic probability and classifier. After a successful bot turn, the group enters an in-memory ENGAGED state for 300 seconds. In that state, explicit continuation/direct cues and replies to the bot go straight to the native Agent path, explicit replies to another person are silent, and ambiguous messages use the existing single decision request to classify relevance. The timeout refreshes only after the entire reply turn sends successfully. SILENT yields no `ProviderRequest`; a selected response yields one `event.request_llm` with the current Conversation into AstrBot's regular AgentRequestSubStage. That native path selects the current Provider, applies the selected Persona and tools (including Web Search), and writes one answer to the current Conversation.

After one final QQ group LLM result is produced, the pre-send hook may keep its first natural text part in AstrBot's result pipeline and queue up to two follow-up text parts. AstrBot sends the first part normally; the after-send hook sends follow-up parts with a short delay, followed by any selected sticker. This does not create extra Agent or Provider generations. Short text, code, URLs, and recognized Markdown structures stay together. Bot-authored follow-up messages are rejected by the observer's existing self-message check.

The bounded group context is added only to the SPEAK request's user content as a `TextPart.mark_as_temp()` value. It never changes the stable system prompt or persisted Conversation. Jingjing Stickers v1 is **VERIFIED** by user-confirmed real QQ E2E. Sticker output uses the `jingjing_sticker(category)` Agent tool with a strict fixed category allowlist; the model never receives or supplies a path, filename, or URL. The tool is hidden for the current request when stickers are disabled or the gallery is empty, and Persona tool configuration is not changed. User-provided assets live under `plugins/astrbot_plugin_yuuk1_core/assets/stickers/<category>/`. Only PNG/JPG/JPEG are accepted, up to 8 MiB and 16 million pixels, with signature and Pillow decode validation, root containment, symlink rejection, and validation again before sending. Each turn queues at most one image. All text parts go first and the sticker follows; an empty final text can send image-only. Failed optional image delivery preserves text; failed image-only delivery falls back to “鲸鲸在这儿。” Repeat suppression defaults to a bounded global in-memory window of four SHA-256 fingerprints (configurable 1–5); multi-image categories avoid recent repeats where possible, while a single-image category may repeat. The cache is not persisted and clears on restart. User-confirmed E2E passed for image, text + sticker, image-only, multi-message + sticker, one-image-per-turn, repeat suppression, Free Talk/ENGAGED/Group Identity regressions, and self-loop prevention.

Idle Presence uses a single optional task owned by plugin `initialize()` / `terminate()`. It has no target until an allowed group message has been observed, respects an idle threshold, attempt gap and local active-hours window, and uses `Context.send_message()` with the in-memory unified session. Its one-shot generation reads the current selected Persona and Provider without writing to the AstrBot Conversation or running tools. Free Talk, Stickers, and Idle Presence switches default off; engagement defaults on but remains inert while Free Talk is off.
