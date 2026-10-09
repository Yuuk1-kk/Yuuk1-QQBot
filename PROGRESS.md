# Progress

Last updated: 2026-10-09

## v0.1 current state

The existing `main` branch and AstrBot / NapCat architecture remain in use. AstrBot v4.28.2, NapCat-Docker v4.18.33, both WebUIs and Yuuk1 Core were launched in real Docker. The first startup exposed an AstrBot command-decorator compatibility bug; commit `d93aca4` fixed it and real logs confirmed `Yuuk1 Core ready`. **v0.1 stabilization is VERIFIED** against the runtime and group E2E checks below.

## Real integration already exercised

- **DeepSeek ChatUI VERIFIED:** the configured DeepSeek Provider with default `deepseek/deepseek-flash` completed a real AstrBot ChatUI request. Doctor only reads configuration and never sends a billable model request.
- **NapCat QQ login VERIFIED after recreation:** the Bot QQ was scanned in and received group messages before this fix. After the account owner selected automatic login and signed in again, `restart.ps1` recreated NapCat and the read-only NapCat status API confirmed QQ online without another manual scan.
- **OneBot v11 connection VERIFIED after recreation:** the earlier Reverse WebSocket connection carried real QQ group messages. After recreation, doctor confirmed the current adapter, listener, NapCat peer socket and post-handshake client registry all connected again.
- **QQ group E2E VERIFIED before recreation:** an ordinary “你好” received no reply; `@Bot 你好` produced a DeepSeek reply; an administrator could run `/yuuk1 status`; a non-administrator was denied `/yuuk1 reset`.
- **Restart persistence VERIFIED:** `restart.ps1` recreated both containers with new IDs. QQ returned online without another manual scan, OneBot reconnected, AstrBot and Yuuk1 Core started, and doctor returned 0 FAIL/WARN/MANUAL. After recreation, the account owner sent `@鲸鲸 你好` in an allowed test group and confirmed a normal reply.

## Current persistence incident and fix

- The pinned NapCat image, official documentation, Compose, Docker inspect and Windows permissions all confirm a writable `./data/napcat/qq:/app/.config/QQ` mount. The persisted QQ directory contains about 2,200 files and was not lost. `data/napcat/config` is also mounted. Both are ignored by Git.
- NapCat v4.18.33 initially had no selected automatic login account: the ignored WebUI config's `autoLoginAccount` was empty and neither quick-login environment variable was set. The pinned startup code only passes QQ `-q` for a configured account; the NapCat WebUI quick-login path also requires one. After the account owner selected the account and signed in, the current official status API reports QQ online before and after recreation.
- `restart.ps1` now refuses to recreate the stack without a persistent WebUI auto-login selection, unless `-AllowQRRelogin` is explicitly passed. `start.ps1` checks that the QQ mount source directory exists. The existing backup behavior remains unchanged: it refuses a running-stack consistency backup and includes QQ session files only with `-IncludeQQSession`.
- **Post-recreate verification passed:** two containers were recreated, no manual rescan occurred, and both QQ login and OneBot connection returned PASS. The AstrBot `cmd_config.json`, NapCat WebUI config, and the single Persona record (including “鲸鲸”) had identical before/after hashes. The QQ data directory remained populated (2,207 files before, 2,208 after); normal session files grew. NapCat emitted a QR-related startup log line before a login-success line, so the automatic recovery conclusion rests on the live online check without a new human scan. The account owner confirmed a normal group reply to `@鲸鲸 你好` after recreation. No QQ account ID, key, token or session file is committed.

## Doctor runtime detection

- Yuuk1 Core load uses readable source/metadata, AstrBot's persisted enabled state, and an ephemeral marker written at the end of plugin `initialize()` and bound to the current PID/start tick. The current AstrBot process has been restarted and the marker is PASS; current-start logs also contain `Yuuk1 Core ready` without a new plugin import failure.
- DeepSeek Provider/Profile is PASS from static source, environment-reference, current AstrBot process environment, enabled-model and default-profile checks. No model request is made and no key is printed.
- OneBot checks now separate configured Adapter, port listener, NapCat-to-AstrBot TCP reachability, enabled Reverse WebSocket client config, a persistent live socket from NapCat, and AstrBot's fresh post-handshake client-registry state. Historical connected logs or TCP alone cannot mark the current connection PASS.
- NapCat QQ login uses the v4.18.33 authenticated, read-only status endpoint. The local WebUI token stays in memory; only safe PASS/FAIL/MANUAL text is shown. An unavailable endpoint or WebUI 2FA keeps this check MANUAL rather than guessing.
- Current doctor result after recreation: all checks PASS, including DeepSeek static and current process environment, plugin mount/load, NapCat QQ login/quick-login selection, OneBot TCP and current WebSocket connection. There are 0 FAIL, WARN or MANUAL entries. No model request was sent.

## Validation

- `python -m pytest -q`: 32 passed, including decorator compatibility, plugin enablement and client-registry state, marker freshness, current socket matching, doctor status combinations, stale-log rejection, secret redaction and restart guards.
- Ruff for `plugins scripts tests`, Python compileall for `plugins scripts tests`, parsing all PowerShell scripts, and `docker compose config --quiet`: PASS.
- Real Provider success and the original QQ group behavior were observed before the session-loss incident. The account owner confirmed a normal `@鲸鲸 你好` group reply after the persistence fix and container recreation.
- A consistency backup test is deferred because `backup.ps1` intentionally requires stopped services; the bot has not been stopped for backup. No Git remote is configured, and no push has occurred.

v0.1 stabilization and restart persistence are **VERIFIED**. The intentionally stopped-service backup/restore flow remains untested and is not claimed as verified. v0.2 has not started.

## Free Talk / Stickers / Idle Presence implementation status

The first implementation pass adds the optional Free Talk v1, Stickers v1, and Idle Presence code paths. AstrBot v4.28.2 source review confirmed the event listener / ProviderRequest / Conversation pipeline and the current Persona `tools=None` state; the Persona itself was not changed. All three new feature switches default off.

The current Free Talk v1 and Jingjing Stickers v1 behaviors are **VERIFIED** by the user's real QQ E2E results recorded below. Idle Presence remains disabled in the runtime. Earlier sections below preserve debugging history and intermediate snapshots; the final verification sections supersede their interim pending statuses.

The implementation uses one decision call for a Free Talk candidate that reaches the classifier, followed by the existing native Agent run only on SPEAK. Native Agent tool rounds remain governed by AstrBot's configured `max_steps`. Dynamic history is temp-marked user content. Text-plus-sticker sends the answer before attempting the image; the sticker-only branch falls back to generated text when image construction or proactive send fails. Idle generation is a single Persona-aware, no-tools call through the active Provider and does not write to Conversation history.

At the first implementation snapshot, local tests and Runtime checks passed while Free Talk behavior E2E and QQ sticker delivery were still pending. Those interim statements are historical and superseded by the final verification sections below.

## Free Talk observer regression follow-up (historical debugging record)

- The first real Free Talk test sent an allowed-group ordinary nickname message but produced no observer/candidate logs. Inspection of the pinned AstrBot v4.28.2 runtime showed the cause: `WakingCheckStage` sets `event.is_wake` when any Star adapter handler filter matches, including ordinary group messages. Yuuk1 incorrectly treated that internal marker as a native @/wake request and returned before its Free Talk gate.
- Yuuk1 now checks the actual native `event.is_at_or_wake_command` flag (and @ detection) for the wake bypass. Temporary INFO diagnostics log only message category and boolean gates; they exclude message text, account/group IDs, keys, tokens and Persona prompts. `on_group_message` remains the priority-0 adapter observer. `guard_qq_request` is an `OnWaitingLLMRequestEvent` hook later in the native generation path, so it cannot run before or stop the adapter observer; its default-pipeline guard remains in place.
- Regression coverage models AstrBot's `is_wake=True` ordinary-message behavior and verifies observer/candidate reachability, SILENT without generation, SPEAK with exactly one native generation request, native @/wake bypass, command/self/disallowed-group exclusions, and the guard path.
- After the fix, only `docker compose restart astrbot` was run. NapCat was not restarted or recreated. AstrBot logged `Yuuk1 Core ready`, OneBot reconnected, and the second `scripts/doctor.ps1` run returned all PASS, including current OneBot connection. There were no plugin import failures, tracebacks, listener conflicts or duplicate Idle Presence task indicators in the checked startup logs. The immediate doctor run before the WebSocket reconnect had a transient OneBot WARN; the follow-up after reconnect was fully PASS.
- The user then sent “大肥鱼在吗” in an allowed group. Real logs confirmed `on_group_message entered`, allowed group, no native wake/@, Free Talk enabled, and `candidate=True; nickname_candidate=True`. There were no decision-stage diagnostics in that build, so SPEAK/SILENT, Provider invocation and reply were not yet verified.
- The follow-up audit split candidate, recent-message, Free Talk cooldown, probability, throttle, event-stop, rate, provider, classifier, parse and generation-handoff outcomes into PII-free INFO diagnostics. Ordinary AstrBot replies no longer start the Free Talk 90-second cooldown; the decision throttle timestamp is now written only immediately before an actual classifier call. Nickname candidates bypass both generic recent-message and generic probability gates.
- Tests now cover first nickname candidate despite a recent ordinary reply, the nickname probability selection with generic probability at 0.2, decision timestamp semantics, provider-unavailable and classifier-exception diagnostics, and secret-text redaction. `pytest` 54 passed; Ruff, Python `compileall`, and PowerShell script parsing passed.
- The latest build was loaded with `docker compose restart astrbot` only. NapCat's container identity remained unchanged. Logs showed one `Yuuk1 Core ready`, one OneBot connected message, and no Yuuk1 plugin import failure, traceback, listener conflict or duplicate Idle task warning. Doctor returned all PASS, including current OneBot WebSocket connection. No QQ message has yet been sent after this latest build, so Free Talk decision/reply behavior remains pending. No commit has been created.

## Free Talk cooldown removal and multi-message delivery (historical implementation record)

- Removed Free Talk's group reply cooldown and decision interval from runtime decisions. The old `free_talk_min_interval_seconds`, `free_talk_decision_interval_seconds`, and `free_talk_nickname_probability` remain readable for existing WebUI config but are marked deprecated; both timing fields default to zero and none of the legacy fields block a candidate. Project per-user/per-group security rate limits remain active.
- Direct nickname address is recognized when a supported nickname begins the message and is followed by a call/request cue (or is used alone). Its candidate probability is fixed at 1.0 and it bypasses the generic recent-message and probability gates. Ordinary mentions remain generic. Generic probability defaults to 0.35. The decision prompt strongly favors SPEAK for direct calls unless a reply is clearly unnecessary.
- Added configurable post-generation splitting: `multi_message_enabled=true`, `multi_message_max_parts=3`, `multi_message_min_chars_to_split=20`. AstrBot sends the first part through its native result pipeline; its after-send hook sends up to two remaining parts 0.45 seconds apart. This reuses one final generated result. Short answers and detected code blocks, URLs, and Markdown structures remain a single message. When sticker delivery is enabled, pending sticker art follows all text parts.
- Removed temporary high-volume INFO diagnostics and retained sparse content-free DEBUG stage/reason/count records. Existing self-message, command, wake/@, allowlist and security rate-limit gates remain.
- The existing local plugin config had persisted the former defaults `free_talk_probability=0.2`, `free_talk_min_interval_seconds=90`, and `free_talk_decision_interval_seconds=10`; these were narrowly migrated to `0.35`, `0`, and `0`. Other runtime settings were left intact. The WebUI/runtime config now also contains the new multi-message defaults `true`, `3`, and `20`; current `stickers_enabled=false` and `idle_speak_enabled=false` remain unchanged.
- Local verification after this code change: `pytest` 57 passed, Ruff passed, Python compileall passed, PowerShell parsed all 10 scripts, schema JSON parsed, `git diff --check` passed, and `docker compose config --quiet` passed.
- Runtime verification: the Compose service was confirmed as `astrbot`, then only `docker compose restart astrbot` was run. NapCat retained container ID `20ab7947872d` and remained running; it was not restarted or recreated. AstrBot logged `Yuuk1 Core ready`, selected the existing `deepseek/deepseek-flash` model, reached WebUI ready, and logged the OneBot v11 adapter connected after reconnect. Since the restart, the last-5-minute log check found 0 plugin import failures, 0 traceback blocks, 0 listener conflicts, and 0 Idle Presence tasks. The one traceback in the last-300-lines window was timestamped before this restart and came from AstrBot's Web Search tool path, not the new startup. The first doctor run occurred before the OneBot handshake completed and showed a transient WARN; after the handshake, `doctor.ps1` returned all PASS, including plugin load, NapCat login, and OneBot connection. No QQ message has yet been sent after this build, so Free Talk and multi-message QQ delivery still need user E2E. No commit has been created.

## Free Talk v1 direct address and engagement (final verification)

- The latest QQ E2E reports exposed two behavior gaps: direct nickname detection did not recognize commands such as “大肥鱼下士出列”, and after a successful bot reply every next group message returned to the 0.35 generic candidate roll. Direct recognition now uses bounded local structure: a nickname at the message opening (with short punctuation/space prefix), followed by a second-person/question/call/request/imperative cue or standalone punctuation. Role/title + imperative forms are recognized; noun-description starts such as `表情包`, `名字`, `称呼`, `头像`, `角色`, and `昵称` are excluded. Direct calls hand off to AstrBot's native generation without probability or SPEAK/SILENT classification.
- Added per-group volatile ENGAGED state with the monotonic time of the last successful bot turn, the stable Group Identity member key, and the last bot-turn text/timestamp. Engagement state itself remains in memory. Lazy expiry returns the group to IDLE at 300 seconds; only a fully delivered bot turn refreshes the state once. Context selection keeps the latest bot turn plus up to eight recent group messages, including after the general context TTL prunes that bot turn from the message buffer.
- ENGAGED high-confidence direct calls, resolved Reply-to-bot messages, and clear follow-ups hand off to the native Conversation/Persona/Agent path without another probability roll. A Reply to another known sender is locally UNRELATED. New-topic/soft-transition ambiguity goes to the existing single SPEAK/SILENT request, whose prompt now judges relevance to the active conversation. No second relevance classifier was added. Unresolved Reply sender IDs remain ambiguous rather than being guessed.
- AstrBot v4.28.2 source inspection confirmed that `Reply.sender_id` is populated by the aiocqhttp adapter after OneBot `get_msg`; it also confirmed that `RespondStage` can invoke the after-send hook after catching a send exception. The plugin therefore checks the event's v4.28.2 successful-send marker and every queued follow-up send result before refreshing engagement. Three-part output still uses one generated result and records one bot turn after the complete send.
- Audited the two-level security limiter: the previous persisted 3 requests/user/60s could block a fourth/fifth rapid continuous turn. Defaults and the ignored local plugin config are now 8/user/60s and 30/group/60s; this still limits bursts and easily admits 3–5 turns. Rate limiting remains separate from engagement expiry and no chat cooldown was reintroduced. The active plugin config now explicitly has `engagement_enabled=true` and `engagement_timeout_seconds=300`; provider/persona/other service settings were not edited.
- Tests cover direct true/false examples, repeated direct calls, successful-send-only engagement, 299/300-second expiry, successful refresh, direct probability bypass, IDLE candidate probability, RELATED/UNRELATED/AMBIGUOUS paths, bot/other Reply handling, last-bot context retention across interleaving and TTL, native @/wake, one generated result for multi-part output, safety exclusions and five-turn rate-limit capacity.
- Local verification: `pytest` 63 passed; Ruff passed; Python `compileall` passed; all 10 PowerShell scripts parsed; schema JSON, `docker compose config --quiet`, `git diff --check`, and the secret-pattern scan passed (58 non-ignored files scanned).
- Runtime verification: only AstrBot was restarted with `docker compose restart astrbot`; the final restart loaded the final tested code. NapCat kept container ID `20ab7947872d6f80f72890bc35562964d20388e4ba20901929bd7a73dec1cd58` and remained Up. The final five-minute log window showed one `Yuuk1 Core ready`, one OneBot v11 connected message, zero plugin import failures, zero tracebacks, zero listener conflicts, and zero Idle Presence task logs.
- The user confirmed real QQ E2E PASS for direct nickname calls, ENGAGED continuation, unrelated group silence, resuming context after interruption, @ / Reply, and multi-message delivery. The user also confirmed Runtime / doctor PASS and persistent NapCat login. No Free Talk product behavior changed after these E2E checks.
- The current AstrBot Runtime had `Yuuk1 Core ready`, a connected OneBot v11 adapter, and a passing `scripts/doctor.ps1` result. NapCat remained online and its persistence was not modified in this finalization.

## Jingjing Free Talk v1 — VERIFIED

- Final semantics: IDLE ordinary group messages have a 0.35 proactive-join probability after local gates; direct nickname, @, and Reply-to-bot requests receive an explicit reply through AstrBot's native path. After a successful reply, the group remains ENGAGED for 300 seconds. Related messages during ENGAGED bypass the 0.35 probability; ambiguous messages use the existing relevance decision. Every fully successful reply refreshes the 300-second state. There is no chat cooldown.
- One Agent generation can be split into at most three QQ messages. A short send interval is used for later parts; this does not add generation calls. Security rate limits remain 8 requests per user per 60 seconds and 30 per group per 60 seconds.
- After final code cleanup, only `docker compose restart astrbot` was run. Logs showed one `Yuuk1 Core ready` and one OneBot v11 connected marker, with zero Yuuk1 plugin import failures, traceback blocks, or listener conflicts. NapCat remained running with the same container ID; no NapCat operation was performed. `scripts/doctor.ps1` returned all PASS, including plugin load, DeepSeek static config, NapCat QQ login/persistence, and current OneBot Reverse WebSocket connection.
- Runtime and doctor passed, NapCat login persistence remained healthy, and the listed direct / continuation / silence / interruption / @ / Reply / multi-message QQ E2E checks passed. Final local validation: `pytest` 63 passed; Ruff, `compileall`, all 10 PowerShell script parses, `docker compose config --quiet`, `git diff --check`, and the secret-pattern scan over 58 non-ignored paths all passed.
- Temporary FT diagnostic INFO logging has been removed. Free Talk emits only content-free DEBUG categories, decisions, part counts, and skip reasons. Plugin failure logging records handler name and exception type only; it does not serialize arbitrary exception or traceback text.
- At this historical Free Talk implementation checkpoint, Stickers were outside the verified scope; Jingjing Stickers v1 was implemented and verified later in this file.

## Group Identity Context v1 — VERIFIED

- The v4.28.2 public event APIs supply get_sender_id() and get_sender_name(). The pinned aiocqhttp conversion prefers sender.card, then sender.nickname; Yuuk1 consumes the resolved display name and uses “群友” when it is blank or unsafe.
- Group member keys use HMAC-SHA256 with separate domain strings for group scope and member identity. Inputs are platform + group, and platform + group + sender. The persisted keys are stable across restart and are scoped per group; raw QQ user IDs and group IDs are not stored.
- AstrBot StarTools.get_data_dir("astrbot_plugin_yuuk1_core") resolves to /AstrBot/data/plugin_data/astrbot_plugin_yuuk1_core; the host path is data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/ under the existing ./data/astrbot:/AstrBot/data bind mount.
- identity_secret stores the random 32-byte HMAC key; group_identity.json stores schema-versioned JSON with hashed group/member keys, current display name, up to five de-duplicated aliases, and first/last-seen timestamps. It stores no message history or personal facts. Writes are batched and use a same-directory temporary file, fsync, and atomic replace. The secret and store use private POSIX permissions; Windows relies on local Docker Desktop bind-mount ACLs.
- If the store is present but the secret is absent/invalid, the plugin will not silently generate a replacement or overwrite the store. The status marker reports only booleans and a bounded member count; doctor never prints names, hashes or key contents.
- Dynamic prompt context uses [display name] message, [鲸鲸] for bot turns, short HMAC suffixes only for duplicate names, and a temp-marked TextPart in user content. At.name and Reply.sender_nickname are used when available; target IDs are converted locally and are never included in prompt text. ENGAGED state reuses the same member key.
- Local regression tests now cover stable scope/member keys over reload, group isolation, rename/alias limits, secret loss behavior, non-destructive handling of invalid store data, raw-ID exclusion, sender attribution, duplicate names, newlines, At/Reply names, doctor state and secret redaction.
- Final local verification for this worktree: `pytest` 77 passed; Ruff, `compileall`, all PowerShell script parsing, `docker compose config --quiet`, `git diff --check`, and the secret-pattern scan passed.
- Runtime validation used only `docker compose restart astrbot`; NapCat was not operated and its container ID stayed unchanged. Startup logs showed the identity store load and `Yuuk1 Core ready`, with no plugin import failure, traceback block, or listener conflict. After the user E2E, both identity files were populated and persisted.
- The final read-only `doctor.ps1` run returned all PASS, including plugin load, identity secret/store, DeepSeek static config, NapCat login, and current OneBot connection. Doctor sent no model request.
- User-confirmed QQ E2E all passed: sender name, A/B speaker attribution, group-card rename, AstrBot restart identity recovery, `identity_secret` + `group_identity.json` persistence, and ENGAGED/member-identity continuity. Group Identity Context v1 is formally VERIFIED.
- Future Linux migration should copy together data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/identity_secret, group_identity.json, and data/astrbot/config/astrbot_plugin_yuuk1_core_config.json. The existing stopped-service backup archives data/astrbot; this task does not change backup behavior.

## Jingjing Stickers v1 — implementation checkpoint (historical; superseded below)

- Audited and reused the existing `jingjing_sticker` Agent tool, fixed local `assets/stickers/<category>/` catalog, result-decoration hook, multi-message after-send hook, and request-local tool removal. The tool accepts only a category; mode/path/filename/URL are not model parameters. The fixed categories are happy, angry, speechless, smug, sad, confused, laugh, peek, fatfish, and neutral.
- Hardened catalog and send validation: only direct-child PNG/JPG/JPEG files under the plugin asset root, no symlinks or root escape, at most 8 MiB and 16 million pixels, matching file signature and successful Pillow decode. Validation is repeated at send time because AstrBot v4.28.2 `Image.fromFileSystem` only builds a component and does not decode the file. Empty gallery is valid; it keeps plain-text behavior and the request-local sticker tool is removed.
- Added `sticker_repeat_window=4`, bounded 1–5. The short-lived global cache stores only SHA-256 fingerprints and clears on restart. A turn queues at most one image. Text parts are sent first and the optional image follows; an empty final text result can send image-only. An image failure leaves existing text intact; if there is no text, a short safe fallback is returned. Optional image failure does not prevent a successfully delivered text turn from refreshing ENGAGED once.
- At this checkpoint the gallery was empty and user-provided production assets and QQ image E2E had not yet been completed. The later verified section below records their completion.

## Jingjing Stickers v1 — VERIFIED

- The public Agent tool is `jingjing_sticker(category)`. The model supplies only one of the fixed categories: `happy`, `angry`, `speechless`, `smug`, `sad`, `confused`, `laugh`, `peek`, `fatfish`, or `neutral`. Persona tools configuration was not modified. When `stickers_enabled=false` or the gallery is empty, the tool is removed from the current request; with valid assets it is available to the current Agent.
- Local assets belong under `plugins/astrbot_plugin_yuuk1_core/assets/stickers/<category>/`; category directories may be empty. The plugin accepts only PNG/JPG/JPEG, <= 8 MiB and <= 16 million pixels, checks signature and Pillow decode, resolves paths under the sticker root, rejects symlink/path escapes, and revalidates before sending. GIF/WebP/SVG and remote URLs are rejected.
- Each Agent turn can send at most one sticker. All generated text parts are sent first and the optional sticker last; an empty text result may send image-only. Sticker failure preserves already-produced text; image-only failure falls back to “鲸鲸在这儿。” without another LLM call. Sticker delivery does not add a second ENGAGED refresh and bot-authored images do not re-enter the Free Talk observer.
- `sticker_repeat_window` defaults to 4 and is bounded to 1–5. The bounded in-memory cache stores only SHA-256 asset fingerprints and is not persisted. It clears on restart; a category with one image may repeat, while categories with multiple images avoid recent repeats where possible.
- The user confirmed real QQ E2E PASS for image-only, text + sticker, multi-message + sticker, maximum one image per bot turn, repeat suppression, ordinary technical-question restraint, and no regressions in Free Talk, ENGAGED, Group Identity, or self-loop prevention. Runtime / doctor were confirmed normal; NapCat was not operated. This is the final feature verification record.
- Sticker selection/skip DEBUG diagnostics added during implementation were removed; only the content-free startup status and failure event/stage/exception-type warning remain. The plugin logger audit found no raw QQ/group IDs, message text, prompt/context, Provider ID, Persona content, sticker path/filename, API key, or token output.
- Final closeout validation: `pytest` 78 passed; Ruff, Python `compileall`, all 10 PowerShell parses, schema JSON parse, `docker compose config --quiet`, `git diff --check`, and the secret-pattern scan (50 text files, zero matches) passed. `scripts/doctor.ps1` returned 0 failures and all checks PASS, including Yuuk1 Core plugin load, DeepSeek static configuration, NapCat QQ login/persistent data, and current OneBot connection.
- The user-confirmed QQ E2E results and read-only doctor status are the runtime verification evidence for this closeout. No restart was needed for log/documentation/test-fixture cleanup; NapCat was not operated. No Persona, Provider, Web Search, Free Talk, or Group Identity behavior was changed.

## Sticker QQ Custom Emoji Mode v1 — implementation checkpoint (historical; superseded below)

This checkpoint predates the later user-confirmed QQ E2E. Its pending-E2E statements describe the state at that time only; see the latest Codex handoff at the end of this file.

- Read-only source audit used the running pinned AstrBot v4.28.2 and NapCat v4.18.33 containers. AstrBot's built-in Image/Record serializer drops unknown fields, but the public generic `BaseMessageComponent.toDict()` path preserves subclass fields and the pinned aiocqhttp adapter serializes them as OneBot message data. NapCat v4.18.33 accepts `image.data.sub_type` and passes it to its picture element/protocol builder. No AstrBot Core or NapCat files were changed.
- Added `sticker_send_mode`, default `image`, with opt-in `qq_custom` that emits the existing sticker bytes as a generic OneBot image segment with `sub_type=1`. `jingjing_sticker(category)`, image catalog validation, repeat suppression, one-image limit, text-first ordering, image-only delivery and ENGAGED flow are unchanged.
- A pre-send preparation failure or explicit OneBot rejection can safely fall back to the regular Image segment. An ambiguous transport exception does not retry the image because OneBot/QQ may already have accepted it. Existing text is not cleared; image-only errors retain the existing short fallback text. Logs contain only fixed stage names and exception type, never image bytes, full paths, filenames or QQ/group identifiers.
- Unit coverage now checks default/invalid mode normalization, generic component serialization of `image` + `sub_type=1`, custom image-only delivery, custom text-plus-sticker delivery, explicit-rejection fallback, and no retry after an ambiguous transport error.
- Custom-mode client presentation has not been verified. Waiting for user QQ E2E on desktop/mobile display, preview/favorite behavior, text + sticker, image-only, and fallback. Do not describe the custom emoji style as VERIFIED until those checks pass.

## Jingjing QQ Custom Sticker Mode v1 — failure investigation checkpoint (historical; current state below)

This checkpoint records the initial silent-request report and the diagnostic setup before the later user E2E. Its configuration snapshot is historical; see the current selected settings and verification boundary at the end of this file.

- The user reported that `stickers_enabled=true` + `sticker_send_mode=qq_custom` produced no visible sticker/reply to an @ message, while `image` mode worked. Read-only inspection of the live AstrBot plugin config found `stickers_enabled=true`, `sticker_send_mode=qq_custom`, and no diagnostics setting (therefore diagnostics remain off by default). No NapCat container or config was changed.
- Read-only v4.28.2 source inspection confirmed `Context.send_message()` returns `True` after a matching platform's `send_by_session()` returns normally; it does not mean a QQ client rendered the media. The aiocqhttp adapter awaits its OneBot `send_group_msg` call and propagates errors. The mode is consulted only when an allowed sticker selection is attached to a result; plain text without a sticker selection does not enter the custom sender. For image-only sticker results, a normal API return clears the empty LLM result and bypasses AstrBot's later response hook. This is a plausible silent-response path if NapCat/QQ accepts the API call but the client does not display the custom image, but the reported incident's tool/send stages are absent from available logs, so the exact root cause is not confirmed.
- AstrBot v4.28.2 source confirms the active request carries a `ToolSet` after Persona tools are merged (`tools=None` means all tools), and `MainAgentHooks` calls `OnUsingLLMToolEvent` before dispatch plus `OnLLMToolRespondEvent` after completion. The request hook can also inspect only whether `jingjing_sticker` is present. This distinguishes tool unavailable, LLM did not call it, selection handler entry, and returned tool status without recording tool arguments/results.
- Added `sticker_diagnostics_enabled`, a default-off plugin setting for temporary INFO stage/status logs. When enabled it records request tool visibility, AstrBot tool selection, handler entry/result, reply decoration, configured/actual send mode, OneBot API completion/rejection/unknown, ordinary-image fallback, and image-only text fallback. Messages, QQ/group IDs, provider IDs, prompts, tool arguments/results, paths, filenames, image content, and credentials are excluded.
- For the next user-triggered E2E, only the ignored AstrBot plugin config was updated to set `sticker_diagnostics_enabled=true`; the code/schema default remains false. Only `docker compose restart astrbot` was run. Startup logs show `Yuuk1 Sticker subsystem ready; assets=21; tool_available=True; send_mode=qq_custom; diagnostics=True`, `Yuuk1 Core ready`, and the OneBot v11 adapter connected. Plugin import failures and traceback blocks were both zero; the NapCat container ID was unchanged. No QQ test message was sent by this task.
- The previous `qq_custom` incident remains undiagnosed because no tool-call or send-stage evidence was retained. If the new log reports `tool_not_called` with request visibility `available`, the model produced its answer without invoking the tool; if it reports a tool call, the following selection/decorate/send/fallback events identify the next boundary. The exact model-side reason is still unknown, and no custom-mode fix is claimed before the user E2E.

## Codex handoff — 2026-10-09 (historical snapshot; superseded by final closeout below)

This was the handoff snapshot at that time. Earlier sections retain historical implementation and debugging checkpoints; the final closeout section at the end of this file is now authoritative.

### Git baseline

- Branch: `main`.
- HEAD: `8d7d51e9298b65e7394e4fce6986d514f6d982ad` (`feat: add jingjing sticker support`). The Free Talk v1 (`228a301c449cb8d17591c9c28cc0de0845566266`) and Group Identity Context v1 (`6692867c38408dd0204c1422cfbd38e3cc719724`) commits are ancestors in the current history; none of these SHAs were assumed to be HEAD without checking.
- At the start of this handoff, 12 tracked files were modified and one sticker JPG was untracked. The exact file list is in `docs/CODEX_HANDOFF.md`. This handoff added/updated documentation only; it did not edit plugin or test code. `docs/CODEX_HANDOFF.md` is newly created and therefore also untracked until committed. Preserve every existing change.

### QQ Custom Sticker v1 status

- **E2E PASS — limited scope:** the user confirmed DeepSeek selected `jingjing_sticker`, the local asset was selected, QQ displayed the text and custom emoji correctly, the emoji could be favorited, and at least one image-only reply succeeded. Reported diagnostic markers were `tool_visibility=available`, `llm_selected=selected`, `selection=selected`, `sticker_queue=queued`, `onebot_send=api_completed`, and `reply_delivery=text_and_sticker_completed`.
- `api_completed` means the OneBot send call returned normally. Client presentation is supported by the separate user visual confirmation, not by that API status.
- **PENDING:** a one-off pure-image request also emitted `(图)`. A later request for the same target emitted only the image. The placeholder source has not been isolated to LLM output, plugin logic, AstrBot result decoration, or a fallback path. Do not globally filter `(图)`.
- **PENDING:** an earlier `qq_custom` request to an @ message was silent. It was not reproduced in the later reported run, but the original event lacks tool/send-stage evidence and its root cause is unknown. Do not describe it as fixed.
- **PENDING:** stable image-only behavior and a full regression with `sticker_diagnostics_enabled=false` have not had final acceptance.
- No item is currently classified as BLOCKED.

### Local runtime snapshot at that handoff (historical)

- At that handoff, the ignored AstrBot plugin config at `data/astrbot/config/astrbot_plugin_yuuk1_core_config.json` contained `stickers_enabled=true`, `sticker_send_mode=qq_custom`, and `sticker_diagnostics_enabled=true`. The schema/code default for diagnostics remains `false`.
- Read-only startup-log inspection confirmed `assets=21`, `tool_available=True`, `send_mode=qq_custom`, `diagnostics=True`, and `Yuuk1 Core ready`. `docker compose ps` showed AstrBot and NapCat running. The filtered log window contained startup markers but no later Sticker send-stage trace; live OneBot WebSocket state was not independently rechecked in this handoff. No new QQ E2E run is claimed from the current container session.
- The current sticker tree contains 21 image assets. One JPG is untracked: `plugins/astrbot_plugin_yuuk1_core/assets/stickers/laugh/a251d04922e251c5439d2d6ad1ff4be1_720.jpg`.
- This documentation handoff did not restart containers or change runtime configuration. The previous report says only AstrBot was restarted and NapCat was neither restarted nor modified.

### Historical validation record

The latest prior report supplied for this handoff records: pytest **79 passed**; Ruff, Python `compileall`, PowerShell script parsing, Compose config, schema JSON, and `git diff --check` passed; secret-pattern scan had 0 findings; `doctor.ps1` had 0 failures; 21 sticker assets were present. These are **historical results** and were not rerun in this handoff. Earlier snapshots in this file record 78 and smaller test counts; those are older checkpoints, not current results.

Actual checks in this handoff were read-only Git/document/source/test inspection, selected runtime-config field inspection, container status inspection, filtered startup-log inspection, and a sticker asset count. No tests, Ruff, compileall, PowerShell parse, Compose validation, or secret scan were run.

### Next task at that historical snapshot (superseded below)

Investigate the image-only `(图)` placeholder. First trace whether it comes from LLM output, plugin code, AstrBot reply decoration, or fallback logic; inspect `reply_decoration` and send-hook timing; then add a targeted regression. Preserve normal text replies and ordinary `image` mode, never globally filter `(图)`, never retry an ambiguous send, and allow custom-to-image fallback only before a send or after a confirmed no-platform result. Keep diagnostics redacted. This was the next-session task at that historical snapshot and was not implemented in that checkpoint. Visual Identity v1 remains separate and out of scope.

### Stop conditions

Do not send production QQ messages automatically, scan QQ, change QQ/NapCat settings, restart containers, modify Persona/Provider or Sticker assets, discard worktree changes, commit, push, tag, or start Visual Identity v1. Ask for user involvement only if the next investigation actually requires missing real credentials, a QQ scan, irreversible external authorization, or resolution of a major architecture conflict. Mark externally unverified behavior `MANUAL VERIFICATION REQUIRED`.

## Sticker Diagnostic Boundary v1 — implementation checkpoint (2026-10-09)

- Added opt-in, content-free observations at the Agent-visible `on_llm_response` hook, Yuuk1 decoration entry, and completion of Yuuk1's own result decoration. Each boundary is correlated by an opaque 8-hex request marker; it records only mode, selection presence, component counts, booleans, and fixed stage/status values.
- `(图)` detection is exact per Plain component after trimming outer whitespace. Plain components are not concatenated. The new instrumentation does not rewrite the result chain or alter the sticker send path. AstrBot's built-in post-hook decoration and final pre-send text remain unobservable through a reliable public plugin hook; `after_message_sent` runs after primary delivery.
- Root cause of the observed `(图)` remains **UNKNOWN**. The earlier silent `qq_custom` @ request also remains unresolved. No automatic filter or fix was added.
- At this implementation checkpoint, the running container had not yet loaded that local code update. This was a historical state only: later user-provided runtime logs confirmed the new decoration-boundary diagnostics appeared after the plugin was loaded. The current runtime configuration and loading status are recorded below.
- Current validation for this code change: targeted registration test **1 passed**; requested three-file pytest set **30 passed**; Ruff **PASS**; in-memory Python syntax compilation **PASS**; `git diff --check` **PASS**. No QQ E2E was run.
- Next step: after the user loads this plugin version in AstrBot, perform one controlled QQ request that selects a sticker and asks for image-only output; compare `llm_response_visible`, `yuuk1_decoration_entry`, and `yuuk1_decoration_complete` by request marker. Do not globally remove `(图)`.

## QQ Custom Sticker v1 — final closeout (2026-10-09)

This section supersedes older “pending E2E”, “diagnostics not loaded”, and runtime configuration snapshots above. It records user-confirmed E2E separately from local automated verification.

### E2E verified by the latest user report

- Ordinary text, text + QQ custom sticker, pure sticker, nickname wake, and ordinary `image`-mode compatibility all passed the latest manual QQ E2E.
- The QQ client displayed the custom sticker correctly and confirmed it can be favorited. The latest normal send paths passed manual acceptance.
- These are user-reported external checks; this closeout did not send QQ messages or rerun E2E.

### Locally verified

- Runtime configuration was read without exposing unrelated settings: `stickers_enabled=true`, `sticker_send_mode=qq_custom`, `sticker_diagnostics_enabled=false`.
- AstrBot and NapCat were running. AstrBot startup logs confirmed `Yuuk1 Core ready`, `assets=21`, and `tool_available=True` in `qq_custom` mode with diagnostics disabled. A user-provided later log had already confirmed the decoration-boundary diagnostic records appeared at runtime; the prior “not loaded” note above describes only its earlier checkpoint.
- The 21-image catalog includes the added JPEG in `assets/stickers/laugh/`; its extension, directory and JPEG decoding are valid.
- All `ActionFailed` responses (including NTEvent acknowledgement timeouts) and other send exceptions are treated as ambiguous; they do not trigger another image attempt. The only runtime fallback boundaries are pre-send preparation failure and `Context.send_message()` confirming that no platform matched. Diagnostics remain redacted.
- One selected material per turn is still enforced. Final local checks in this closeout: complete pytest **79 passed**, Ruff **PASS**, Python `compileall` **PASS**, schema JSON **PASS**, `git diff --check` **PASS**, secret-pattern scan **0 findings**. No real NTEvent timeout was re-triggered after the conservative fix.

### Known limitations

- Historical pure-sticker requests sometimes emitted `(图)` or `(表情已发出)`; the source remains unknown. Never globally filter either text.
- DeepSeek has returned empty completions after a successful Sticker tool call. One prior request measured about 115,192 input tokens (about 114,944 cached); cause is unknown and the context size does not establish causality.
- On an Agent error, an already-selected Sticker may still be sent. AstrBot v4.28.2 does not expose a reliable public Agent failure marker at the relevant decoration hook; this is not fixed here.
- The true empty MessageChain path has not been tested through AstrBot's real `ResultDecorateStage` guard; existing tests do not close that integration gap.
- The ambiguous-send fix is covered with local fake NapCat/OneBot outcomes, not a newly reproduced live timeout.

### Deferred work and commit boundary

- Sticker Completion Marker Protocol: deferred because Conversation persistence safety was not established.
- Context / Memory optimization: separate later stage; no history or memory data was changed here.
- Visual Identity v1: not started.
- SnowLuma evaluation belongs to a future server deployment stage; server migration has not started.
- The final Sticker closeout commit is the current HEAD after this documentation is committed; use `git log -1 --oneline` for its exact identifier. No push is authorized.
