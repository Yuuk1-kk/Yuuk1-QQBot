# AstrBot / NapCat / DeepSeek Research Notes

Research snapshot: 2026-10-07. Prefer the official repositories and documentation linked below; repeat these checks before changing the pinned compatibility range.

## Revisions inspected

- AstrBot stable release tag `v4.28.2`, commit `3c7adafa1397e182d60b1016bf88759265113c8a` (released 2026-09-27). The releases page also showed `v4.29.0-beta.1`, commit `f20fba64c29623d248629f4d4bb9474bf4e745bc` (2026-10-01); it is prerelease, so v0.1 targets the latest stable line instead.
- NapCatQQ repository HEAD inspected: `ec6aadaeea38ed3bca67b82bab3d7a9c0f91b8d8`.
- NapCat-Docker repository HEAD inspected: `a97f856bb0d0bf895293520d4323cc3cd3d9495a`, dated 2026-10-05. Read `compose/astrbot.yml`, `templates/templates/astrbot.json`, and `entrypoint.sh`.
- DeepSeek official Quick Start, Chat Completions API, API Updates, and AstrBot's provider documentation checked on 2026-10-07.

## AstrBot architecture

AstrBot is the runtime/core. The inspected source has distinct platform adapters and `AstrMessageEvent`, provider abstractions and provider sources, a staged pipeline, Star registration/lifecycle, and `ConversationManager`. Those services are already the right place for cross-platform transport, model selection/invocation, wake-up processing, history, and WebUI configuration.

### Component responsibilities

1. **Platform Adapter:** receives the platform protocol event, constructs the AstrBot message event, exposes platform send/action methods and capability metadata. The OneBot implementation is in `astrbot/core/platform/sources/aiocqhttp/`.
2. **Provider:** wraps a model service behind AstrBot's provider interface. `ProviderManager` selects configured chat providers; provider configuration and model configuration stay in AstrBot's data and WebUI.
3. **Conversation:** `ConversationManager` maps unified message origins to current conversations and exposes create/switch/delete/update operations. `delete_conversation(umo)` removes the selected conversation and clears its selected-session pointer; there is no reason for a Star to touch the database directly.
4. **Pipeline:** processes message events, native wake-up/permission filters, commands and Agent requests. The internal agent path calls `on_waiting_llm_request` before provider selection and `on_llm_request` after building the ProviderRequest but before provider invocation. A stopped event prevents the provider call.
5. **Star plugin:** registers event/command handlers and hooks, receives `Context` and schema-backed config, uses AstrBot APIs, and implements only project-specific behavior. `terminate()` is available for unload cleanup.

## Native whitelist and administrator findings

AstrBot already has a global `platform_settings.enable_id_white_list` / `id_whitelist` pipeline stage. It accepts a group ID or unified message origin, but an empty list explicitly disables filtering; additionally, `wl_ignore_admin_on_group` defaults to `true`, allowing AstrBot admins to bypass the filter. That global switch affects all platforms and Stars.

Yuuk1 keeps `allowed_groups` in this plugin because the project requires a per-project fail-closed default: an empty plugin list blocks every QQ group, and it does not change other AstrBot platforms/plugins. Duplicating the same non-empty IDs in AstrBot's global list is optional defense-in-depth for installations that want a runtime-wide allowlist; it is not required for Yuuk1's own AI and command policy. AstrBot's built-in `admins_id` similarly exists, but `admin_users` is scoped only to Yuuk1 management commands so project access does not grant broader AstrBot administration.

## OneBot v11 / NapCat connection

AstrBot's OneBot documentation explicitly says AstrBot is the Reverse WebSocket server and the protocol implementation is the client. The server listens on host `0.0.0.0` (for a container deployment), port `6199` by default, and path `/ws`; the connection URL is `ws(s)://<host>:6199/ws`.

The inspected NapCat-Docker `MODE=astrbot` template configures a WebSocket client URL of `ws://astrbot:6199/ws`, array message format, no token, and reconnect intervals. Docker service-name DNS lets this work without a hard-coded host IP. Compose keeps 6199 private to the two-service bridge network and only publishes the two local admin UIs.

## Provider and plugin LLM invocation

- AstrBot recommends using its built-in Provider types (including an optimized native type when one is available) and selecting the configured model in the active Profile.
- For plugin-initiated generation, the current SDK method is `Context.llm_generate(chat_provider_id=..., prompt=...)`; get the active ID from `get_current_chat_provider_id(umo=...)` or fetch the Provider with `get_using_provider_async(umo=...)`.
- Yuuk1 Core does not issue a separate model request. It leaves the native AstrBot conversation/agent call intact, uses `@filter.on_waiting_llm_request()` for the project allowlist/rate gate before provider selection, and uses `@filter.on_llm_request()` to append stable persona context and set a safe provider-error reply.
- AstrBot's OneBot adapter owns @Bot/reply wake-up behavior; this plugin does not create a second message trigger or prompt pipeline.

## Plugin config and state

- A plugin has a `metadata.yaml`, a `main.py` with a `Star` subclass, and optionally `_conf_schema.json`.
- AstrBot loads schema config from `data/config/<plugin_name>_config.json` and passes it to the plugin constructor. The WebUI schema supports `string`, `text`, `int`, `float`, `bool`, `object`, `list`, and other documented types; `secret: true` masks but does not encrypt a field.
- AstrBot's plugin guide says persistent plugin data belongs in the AstrBot data area, not the plugin source folder, since updates may replace plugin files. Yuuk1 Core has no custom durable state; rate-limit buckets stay in memory.
- The plugin uses `_conf_schema.json` (no custom Page), with JSON/list values normalized defensively.
- The inspected upstream `pyproject.toml` configures Ruff, Pyright (`typeCheckingMode = basic`, Python 3.10), and pytest. This repository mirrors the Ruff rule families and line length, uses pytest for policy tests, and carries a matching Pyright basic-mode config. Pyright is not run in this workspace because the AstrBot SDK is supplied by the container runtime rather than installed into the local Python environment.

## Error behavior and the generic provider reply

The inspected v4.28.2 internal agent path catches a provider/agent exception and, absent an event custom error string, can send the exception message to the chat. AstrBot's `persona_error_reply.py` reads the event extra `persona_custom_error_message`; Yuuk1 sets it through the public `event.set_extra()` API before the provider call so provider failures result in a short generic Chinese reply. The exception remains in AstrBot-side logs. This key is currently an internal compatibility surface and must be rechecked on AstrBot upgrades. Plugin handler exceptions are separately handled by AstrBot's `on_plugin_error` hook; Yuuk1 sanitizes the traceback before logging and sends only a generic reply.

## Existing features we reuse

- OneBot platform adapter / WebSocket server
- MessageEvent and native wake-up/reply behavior
- Pipeline and permission/command filters
- Provider manager and LLM Provider abstraction
- Profile/Persona and Agent runner
- Conversation manager and persistence
- Star loader, configuration schema, lifecycle, WebUI and logs

## Yuuk1-specific behavior

- Project-level fail-closed allowlist for group-originated default AI requests
- Project-configured admin IDs for `/yuuk1 status` and `/yuuk1 reset`
- Stable Bot name/system-prompt append that leaves the current profile/persona prompt in place
- Per-group in-memory sliding-window request limit
- Project command namespace and safe provider/runtime status
- A generic user-facing provider error message, attached through the current event-extra extension point

## Compatibility surfaces to revisit on AstrBot upgrades

- `astrbot.api.event.filter.on_waiting_llm_request` / `on_llm_request` registration and the `ProviderRequest` import/fields
- `event.get_platform_name()`, group/sender IDs, `stop_event()`, `send()`, and `set_extra()` semantics
- Whether the pipeline still invokes `on_waiting_llm_request` before Provider selection, invokes `on_llm_request` before Provider I/O, and respects a stopped event
- Whether `persona_custom_error_message` remains the supported internal event-extra key; prefer a public replacement if AstrBot adds one
- `Context.get_using_provider_async`, `Context.conversation_manager.delete_conversation`, and Provider metadata/model methods
- Command-group API, Star config injection, `metadata.yaml`, and `_conf_schema.json` type support
- AstrBot image tags/data mount paths and current Docker deployment documentation
- NapCat-Docker's `MODE=astrbot` template, client URL, WebUI port, config persistence, and image tags
- DeepSeek current model identifiers, compatible base URL and API behavior

## Sources

### AstrBot official

- [AstrBot repository](https://github.com/AstrBotDevs/AstrBot) — stable tag source: [v4.28.2](https://github.com/AstrBotDevs/AstrBot/tree/v4.28.2)
- [Release notes](https://github.com/AstrBotDevs/AstrBot/releases)
- [OneBot v11 connection](https://docs.astrbot.app/platform/aiocqhttp.html)
- [AstrBot Docker deployment](https://docs.astrbot.app/deploy/astrbot/docker.html)
- [Provider setup](https://docs.astrbot.app/en/providers/start.html)
- [Star plugin guide](https://docs.astrbot.app/dev/star/)
- [LLM Provider guide](https://docs.astrbot.app/en/dev/star/guides/ai.html)
- [Plugin configuration schema](https://docs.astrbot.app/en/dev/star/guides/plugin-config.html)
- [AstrBot global config and allowlist](https://docs.astrbot.app/en/dev/astrbot-config.html)
- [Plugin Pages guidance](https://docs.astrbot.app/en/dev/star/guides/plugin-pages.html)
- Source areas inspected at v4.28.2: `astrbot/core/platform/`, `astrbot/core/platform/sources/aiocqhttp/`, `astrbot/core/provider/`, `astrbot/core/provider/sources/`, `astrbot/core/pipeline/`, `astrbot/core/star/`, `astrbot/core/conversation_mgr.py`, and Star/Provider docs under `docs/`.

### NapCat official

- [NapCatQQ repository](https://github.com/NapNeko/NapCatQQ)
- [NapCat-Docker repository](https://github.com/NapNeko/NapCat-Docker)
- [NapCat-Docker AstrBot Compose template](https://github.com/NapNeko/NapCat-Docker/blob/main/compose/astrbot.yml)
- [NapCat-Docker AstrBot OneBot template](https://github.com/NapNeko/NapCat-Docker/blob/main/templates/templates/astrbot.json)

### DeepSeek official

- [Your First API Call](https://api-docs.deepseek.com/quick_start/)
- [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)
- [API Updates](https://api-docs.deepseek.com/updates/)

## Research decisions

- Use the latest stable AstrBot release, not the newer beta, for v0.1 compatibility.
- Use AstrBot's DeepSeek/OpenAI-compatible Provider and its environment-variable support; no custom DeepSeek client.
- Use NapCat's official AstrBot mode template and service-name DNS; do not expose the internal 6199 listener to the host.
- Use Star schema config for the small set of editable project settings; no Plugin Page.
- Use AstrBot's ConversationManager API to reset and AstrBot's native Profile/Persona pipeline rather than a parallel database or prompt manager.
- Empty `allowed_groups` blocks every group by default. Private-chat commands are not constrained by the group allowlist.
