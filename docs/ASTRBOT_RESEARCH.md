# AstrBot / NapCat / DeepSeek Research Notes

Research snapshot: 2026-10-07. Prefer the official repositories and documentation linked below; repeat these checks before changing the pinned compatibility range.

## Revisions inspected

- AstrBot production baseline is stable release tag `v4.28.2`, commit `3c7adafa1397e182d60b1016bf88759265113c8a` (released 2026-09-27). The releases page also showed `v4.29.0-beta.1`, commit `f20fba64c29623d248629f4d4bb9474bf4e745bc` (2026-10-01). Its `-beta` tag makes it a beta regardless of GitHub's `release.prerelease` field, which can be false. Version checks must classify both the tag text and metadata; no beta is selected for this baseline.
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

Yuuk1's `allow_private_chat` defaults to `false`; QQ private chat is denied by both its command group filter and LLM request hooks until explicitly enabled. The global AstrBot whitelist is unsuitable as the only project gate because its empty list disables filtering and it can exempt AstrBot admins. `/yuuk1 reset` remains a project-admin command because the current group conversation may be shared.

## OneBot v11 / NapCat connection

AstrBot's OneBot documentation explicitly says AstrBot is the Reverse WebSocket server and the protocol implementation is the client. The server listens on host `0.0.0.0` (for a container deployment), port `6199` by default, and path `/ws`; the connection URL is `ws(s)://<host>:6199/ws`.

The inspected NapCat-Docker `MODE=astrbot` template configures a WebSocket client URL of `ws://astrbot:6199/ws`, array message format, no token, and reconnect intervals. Docker service-name DNS lets this work without a hard-coded host IP. Its `entrypoint.sh` copies `/app/templates/astrbot.json` over `/app/napcat/config/onebot11.json` whenever `MODE` is set on startup. A token edited in NapCat WebUI would therefore not be a durable setting under this mode; a single `.env` variable would not reliably synchronize both ends. The project leaves the token empty with 6199 unexposed outside the two-service Compose bridge and both WebUIs bound to loopback. A deployment that changes those network assumptions needs a separate persistent token strategy.

## Plugin discovery and source mount

At v4.28.2, `PluginManager.plugin_store_path` comes from `get_astrbot_plugin_path()` (`data/plugins`). `_get_modules()` enumerates child directories and accepts one containing `main.py` or a Python file matching the directory name. `load()` imports `data.plugins.<directory>.main` for the former case and logs `Loading plugin <directory> ...` before import. The Compose `./data/astrbot:/AstrBot/data` mount supplies AstrBot's data root, and its nested read-only mount maps `./plugins/astrbot_plugin_yuuk1_core` to `/AstrBot/data/plugins/astrbot_plugin_yuuk1_core`. This leaves the repository's `main.py` in the actual loader path without copying plugin files. Recreating AstrBot after source changes triggers a fresh import. Source-path inspection establishes discoverability but cannot establish actual load success. The v4.28.2 live plugin registry requires dashboard authentication. Yuuk1 writes a secret-free `/tmp` marker at the end of `initialize()`, recording the process PID and Linux start tick; `terminate()` removes it. Doctor accepts the marker only for that live process and checks the metadata, source files and persisted disabled-plugin preference. Logs remain supplemental evidence.

## Runtime doctor state sources (v4.28.2 / v4.18.33)

- AstrBot's `cmd_config.json` stores `provider_sources`, enabled models in `provider`, the selected default under `agent_runner.config.model.provider_id`, and enabled aiocqhttp platforms. A DeepSeek Source has a `key` **list** containing the literal environment reference `$DEEPSEEK_API_KEY`; doctor compares the reference and confirms the current AstrBot process has a nonempty environment variable, without printing its value or sending a model request. The current default profile has no additional `abconf_mapping` entries.
- `data_v4.db` stores disabled plugin module paths in global preference `inactivated_plugins`, inside `value["val"]`. A plugin config file or the marketplace `plugins.json` cache cannot prove a Star is loaded.
- AstrBot `/api/platform/stats` reports an adapter task as running before the WebSocket connects, so it is not a connection proof. The plugin uses public `Context.get_platform_inst()` to locate the configured aiocqhttp adapter and samples its `_wsr_api_clients` registry, which the pinned aiocqhttp implementation populates only after WebSocket handshake and removes on disconnect. A fresh, process-bound marker carries the boolean result. Doctor also distinguishes port 6199 LISTEN, a short NapCat-to-AstrBot TCP dial, and a persistent ESTABLISHED socket from the current NapCat IP, and requires NapCat's enabled Reverse WebSocket config and live QQ online state. Neither TCP reachability nor historic success logs alone produce connection PASS. `_wsr_api_clients` is a verified internal compatibility surface that must be rechecked on AstrBot upgrades.
- NapCat-Docker documents `/app/.config/QQ` as the QQ data path and `/app/napcat/config` as the config path. Both were already bind mounted and writable on Windows Docker Desktop. QQ data survived recreation, but `webui.json.autoLoginAccount` was empty and neither `ACCOUNT` nor `NAPCAT_QUICK_ACCOUNT` was set. The pinned image starts QQ with `-q` only for a nonempty `ACCOUNT`; NapCatQQ v4.18.33 also attempts WebUI quick login only when `NAPCAT_QUICK_ACCOUNT` or persisted `autoLoginAccount` is present. Persisted files alone do not select the account to restore.
- NapCatQQ v4.18.33 `POST /api/QQLogin/CheckLoginStatus` is a read-only live status endpoint. Its handler requires both a runtime login flag and `core.selfInfo.online === true`. Doctor authenticates locally with the ignored WebUI token kept only in memory, returns fixed PASS/FAIL/MANUAL text, and uses MANUAL when 2FA or authentication prevents safe automation.

## Provider and plugin LLM invocation

- AstrBot recommends using its built-in Provider types (including an optimized native type when one is available) and selecting the configured model in the active Profile.
- For plugin-initiated generation, the current SDK method is `Context.llm_generate(chat_provider_id=..., prompt=...)`; get the active ID from `get_current_chat_provider_id(umo=...)` or fetch the Provider with `get_using_provider_async(umo=...)`.
- Ordinary @/wake requests do not receive a separate Yuuk1 model request. Optional Free Talk adds one direct SPEAK/SILENT classifier call only after local gates; SPEAK then yields a ProviderRequest with the active Conversation to AstrBot native Agent processing. The project allowlist/rate gate still runs before the final native provider call, and on_llm_request appends the existing stable supplement and temporary group context.
- AstrBot's OneBot adapter owns @Bot/reply wake-up behavior; this plugin does not create a second message trigger or prompt pipeline.

## Plugin config and state

- A plugin has a `metadata.yaml`, a `main.py` with a `Star` subclass, and optionally `_conf_schema.json`.
- AstrBot loads schema config from `data/config/<plugin_name>_config.json` and passes it to the plugin constructor. The WebUI schema supports `string`, `text`, `int`, `float`, `bool`, `object`, `list`, and other documented types; `secret: true` masks but does not encrypt a field.
- AstrBot's plugin guide says persistent plugin data belongs in the AstrBot data area, not the plugin source folder, since updates may replace plugin files. Yuuk1 Core has no custom durable state; rate-limit buckets stay in memory.
- The plugin uses `_conf_schema.json` (no custom Page), with JSON/list values normalized defensively.
- A small two-level sliding-window limiter stays in memory: 3 admitted LLM requests per QQ user across groups and private chats, plus 15 per group, each over 60 seconds. Admission checks both capacities before recording either hit so one user hitting their personal quota does not spend more group quota. Private chats, when opted in, use only the user quota. The limits reset when the plugin process restarts.
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

- Project-level fail-closed allowlist for QQ group AI requests and commands; private chat opt-in defaults off
- Project-configured admin IDs for `/yuuk1 status` and `/yuuk1 reset`
- Stable Bot name/system-prompt append that leaves the current profile/persona prompt in place
- Per-user and per-group in-memory sliding-window limits for LLM requests
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
- [v4.28.2 plugin loader source](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/star/star_manager.py)
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
- [NapCat-Docker startup entrypoint](https://github.com/NapNeko/NapCat-Docker/blob/main/entrypoint.sh)
- [NapCatQQ v4.18.33 quick login startup](https://github.com/NapNeko/NapCatQQ/blob/v4.18.33/packages/napcat-webui-backend/index.ts)
- [NapCatQQ v4.18.33 login status handler](https://github.com/NapNeko/NapCatQQ/blob/v4.18.33/packages/napcat-webui-backend/src/api/QQLogin.ts)
- [NapCat-Docker documented persistent paths](https://github.com/NapNeko/NapCat-Docker/blob/main/README.md)

### DeepSeek official

- [Your First API Call](https://api-docs.deepseek.com/quick_start/)
- [Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)
- [API Updates](https://api-docs.deepseek.com/updates/)

## Research decisions

- Pin the reviewed AstrBot stable `v4.28.2` image by tag and digest, and treat `-alpha`, `-beta`, `-rc`, and `-preview` tag names as non-stable even if release metadata says otherwise. Keep NapCat pinned separately; see `docs/UPSTREAM.md`.
- Use AstrBot's DeepSeek/OpenAI-compatible Provider and its environment-variable support; no custom DeepSeek client.
- Use NapCat's official AstrBot mode template and service-name DNS; do not expose the internal 6199 listener to the host.
- Use Star schema config for the small set of editable project settings; no Plugin Page.
- Use AstrBot's ConversationManager API to reset and AstrBot's native Profile/Persona pipeline rather than a parallel database or prompt manager.
- Empty `allowed_groups` blocks every group by default, and `allow_private_chat=false` blocks QQ private chats by default. Both checks apply to the project command group and LLM hooks.

## Optional Free Talk, stickers, and idle presence (v4.28.2)

This work is pinned to AstrBot v4.28.2, not master:

- `filter.event_message_type(EventMessageType.GROUP_MESSAGE)` is exported by `astrbot.api.event.filter`. In v4.28.2 `WakingCheckStage` sets `event.is_wake=True` both for actual @/wake requests and whenever any Star handler filter passes; therefore `event.is_wake` is not a reliable native-wake discriminator. The native Agent branch in `ProcessStage` checks `event.is_at_or_wake_command`. Yuuk1 previously treated the overloaded `is_wake` marker as a native wake and returned before its Free Talk candidate gate, making every activated observer inert. The observer now distinguishes only the native flag and an extracted @Bot segment. A silent non-wake handler yields no `ProviderRequest`, and `ProcessStage` does not invoke the default Agent for it.
- The group observer and `/yuuk1` handlers are `AdapterMessageEvent` handlers with default priority `0`; the registry sorts adapter handlers by descending priority, preserving registration order for equal priority. Its `GROUP_MESSAGE` filter is applied during `WakingCheckStage`, before `StarRequestSubStage` invokes the observer. `guard_qq_request` is an `OnWaitingLLMRequestEvent`, dispatched only after a `ProviderRequest` enters Agent processing; its `stop_event()` cannot preempt the earlier group observer. The observer is registered before the command group in the class, so at equal priority it runs first and returns for slash commands; commands remain handled by the command group.
- Direct nickname calls and resolved Replies to this bot pass one `event.request_llm(prompt=..., conversation=...)` into AstrBot's native Conversation/Persona/Agent/Tools path. They bypass Free Talk probability and classifier requests. AstrBot's `Reply` component exposes `sender_id`; the v4.28.2 aiocqhttp adapter resolves it by calling OneBot `get_msg` and constructing `Reply(sender_id=...)`. If sender resolution is unavailable, Yuuk1 does not assume the target was the bot.
- IDLE ordinary messages use one `Context.llm_generate` classifier call only when the local recent-message and probability gates pass. After a successful bot turn, per-group in-memory engagement lasts for 300 seconds; related direct/follow-up messages go to the native path without another probability roll, unrelated Reply-to-human messages stop locally, and ambiguous messages use that same single classifier request to judge whether they continue the conversation. The classifier prompt includes the last bot turn and up to eight recent group summaries. There is never a second relevance-classifier request. `Context.llm_generate` calls `Provider.text_chat` directly and does not run tools or write a Conversation; a selected answer then enters one native Agent run. The security limiter defaults to 8 requests/user/60s and 30 requests/group/60s, is charged once per model turn, and keeps a 3–5 round exchange below the user cap.
- In the pinned runtime, `Context.get_current_chat_provider_id(umo)` calls `get_using_provider_async(umo)`, which resolves the UMO's provider preference and then the active local-Agent Profile model / configured chat-provider fallback. It raises `ProviderNotFoundError` if no chat Provider resolves; `llm_generate` itself requires a provider ID and raises when the ID cannot be found. The plugin therefore logs only provider-resolution success/failure and does not pass a `None` provider ID onward.
- Free Talk has no chat cooldown. The old `free_talk_min_interval_seconds`, `free_talk_decision_interval_seconds`, and `free_talk_nickname_probability` remain readable for compatibility and do not participate in decisions. IDLE ordinary messages use probability 0.35. Direct-address recognition is local and structural: a supported nickname must appear at the start (allowing a short opening punctuation/space prefix), followed by a call/question/request cue or standalone punctuation; noun-description starts such as `表情包`, `名字`, `称呼`, `头像`, `角色`, and `昵称` are excluded. It is not a full-phrase allowlist. Explicit direct calls bypass recent-message requirements, probability, and SPEAK/SILENT classification.
- Free Talk runtime logging is sparse DEBUG output for candidate type, decision, outgoing part count, and skip reason. It does not log message text, platform identifiers, provider ID, prompt/context, Persona, credentials, or exception text. The plugin error hook records only the handler name and exception type; arbitrary traceback text is intentionally omitted because exception strings may contain request data.
- AstrBot v4.28.2's `ResultDecorateStage` dispatches `on_decorating_result` before it applies reply prefix/mention/quote decoration; `RespondStage` sends the resulting chain and invokes `OnAfterMessageSentEvent` before clearing the result. The RespondStage catches platform send exceptions and can still invoke the after-send hook, so that hook alone is not delivery evidence. In the pinned runtime, `AstrMessageEvent.send()` sets `_has_send_oper` only after the platform adapter send completes; Yuuk1 checks this marker and the return status of every queued follow-up part before refreshing engagement. Yuuk1 leaves the first generated text part in AstrBot's result chain and stores only later parts on the event. The after-send hook delivers those parts through `Context.send_message` with a 0.45 second interval, then sends a queued sticker if enabled. This is one final generation and preserves AstrBot's normal handling of the first part. Short text and detected code/URL/Markdown structures stay intact; output is capped at three parts, and engagement updates once for the whole completed turn.
- Dynamic group summaries are appended only as `TextPart` values in `ProviderRequest.extra_user_content_parts`, and each is marked with `TextPart.mark_as_temp()`. They do not enter the stable `system_prompt`, Persona, or stored Conversation history. The context buffer is in memory, per unified group session, TTL-pruned and bounded; it stores text summaries/placeholders and no raw message objects.
- `Context.send_message(unified_msg_origin, MessageChain)` is the pinned proactive-send API. Idle presence retains only observed allowlisted group session strings in memory, waits through an idle threshold and local active-hour window, uses a single lifecycle-owned task, and cancels/awaits that task in `terminate()`. Idle text uses the currently selected Persona prompt and Provider in a one-shot `Context.llm_generate` call; it does not execute tools or append to Conversation history. Tool execution from a background task is intentionally avoided because `Context.tool_loop_agent` requires an `AstrMessageEvent`.
- `filter.llm_tool(name="jingjing_sticker")` is exported and registers a tool for the Agent. AstrBot applies the selected Persona's tool restrictions to the active request. The v4.28.2 `PersonaManager.update_persona` source explicitly defines `tools=None` as all tools and `tools=[]` as no tools. A read-only query of the current local Persona row returned `tools=None`, so the current Persona allows both existing Web Search tools and the new sticker tool without changing the Persona.
- `Image.fromFileSystem(path)` is available. The pinned aiocqhttp adapter's send serializer converts Image/Record components to base64 and sends the OneBot `image` segment. This implementation accepts only local PNG/JPG/JPEG files after signature/size checks; GIF/WebP/SVG and remote files are excluded pending a real QQ E2E. Text-plus-sticker sends the text through the Agent result first and attempts the image afterward; sticker-only mode keeps the generated text if image construction or the proactive OneBot send fails.

Research source links, all on the fixed tag:

- [filter exports and listener/tool registration](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/api/event/filter/__init__.py)
- [Star handler decorators and ProviderRequest dispatch](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/star/register/star_handler.py)
- [event fields, request_llm and temporary parts](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/platform/astr_message_event.py)
- [Reply component public fields](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/message/components.py)
- [aiocqhttp OneBot Reply resolution](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py)
- [aiocqhttp event send and successful-send marker](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_message_event.py)
- [native wake stage](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/pipeline/waking_check/stage.py)
- [Star Request/Agent dispatch](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/pipeline/process_stage/stage.py)
- [native Conversation, Persona, tools and Web Search request preparation](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/astr_main_agent.py)
- [Context generation, provider lookup and send_message](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/star/context.py)
- [Result decoration and after-send hook ordering](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/pipeline/result_decorate/stage.py)
- [Respond stage delivery and OnAfterMessageSentEvent ordering](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/pipeline/respond/stage.py)
- [temporary TextPart implementation](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/agent/message.py)
- [Persona tool semantics](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/persona_mgr.py)
- [filesystem Image component](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/message/components.py)
- [OneBot image serialization](https://github.com/AstrBotDevs/AstrBot/blob/v4.28.2/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_message_event.py)

These source links document the pinned API and pipeline facts. The current worktree was subsequently imported by the AstrBot v4.28.2 runtime after an AstrBot-only restart; the current doctor result and post-restart log evidence are recorded in `PROGRESS.md`. The new engagement/direct-address user-visible behavior still requires the next QQ group E2E.
