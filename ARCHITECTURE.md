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
- `restart: unless-stopped`; scripts never remove bind-mounted data.

## AstrBot Integration and Star Boundary

Yuuk1 Core loads from the repository plugin directory, mounted read-only into `/AstrBot/data/plugins/astrbot_plugin_yuuk1_core`. AstrBot writes plugin configuration into its own data/config directory. The plugin uses `on_waiting_llm_request` to apply the group allowlist and per-group rate limit before provider selection and auxiliary model work; `on_llm_request` adds the stable persona and generic provider-error reply. It does not implement a wake-up listener; AstrBot's native @Bot and reply behavior remains in charge.

Project commands use the `yuuk1` command group. Conversation reset calls AstrBot's ConversationManager API for the current unified message origin. Status reads the loaded provider/model metadata only; it does not send a paid probe request and never prints credentials.

## Config and Secret Flow

- Compose interpolates `.env` variables; `.env` is untracked and ignored.
- `DEEPSEEK_API_KEY` enters only the AstrBot container environment. In the AstrBot Provider WebUI, configure its API Key field as `$DEEPSEEK_API_KEY`.
- Provider and model configuration are persisted by AstrBot. Profile model selection is persisted by AstrBot.
- Star settings come from `_conf_schema.json` and are persisted by AstrBot under `data/astrbot/config/`.
- No API key is part of plugin settings, tracked JSON, Python, or Compose source.

## Persistence

AstrBot owns conversations and provider/profile state in its data directory. NapCat owns its runtime configuration and QQ session data under `data/napcat`. Yuuk1 Core stores no custom persistent state; the limiter uses process memory and resets on restart.

## Upgrade Strategy

1. Back up the entire `data/` directory while services are stopped.
2. Check AstrBot releases and Star API compatibility; update the image tag in `.env` deliberately.
3. Pull and recreate containers, then review AstrBot/NapCat logs and run `doctor.ps1`.
4. Keep the Star compatibility range bounded in `metadata.yaml`; update `docs/ASTRBOT_RESEARCH.md` when adopting a newer API.

See `docs/ASTRBOT_RESEARCH.md` for inspected revisions and compatibility surfaces.
