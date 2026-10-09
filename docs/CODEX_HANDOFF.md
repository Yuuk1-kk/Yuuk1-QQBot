# Yuuk1-QQBot Codex Handoff — QQ Custom Sticker v1 Closeout

Updated: 2026-10-10. This is the current handoff for a new Codex session. It supersedes older Sticker checkpoints in `PROGRESS.md` and prior handoff snapshots. Do not repeat the Sticker v1 repository/runtime audit unless new evidence appears.

## Current Owner / Relationship Memory closeout (2026-10-10)

- Current branch is `main`, pre-closeout HEAD is `9e79a0f`. Owner Identity and Relationship Memory Store work is intentionally uncommitted and is being closed out together in the current commit. Recheck the final commit and working tree before any new task.
- **Owner Identity v1 deterministic identity Q&A: user-confirmed real QQ E2E PASS.** The user reports all planned cases passed after deployment. This is a guarantee for the conservative direct-question whitelist, not arbitrary free-form model attribution.
- Runtime `owner_identity_diagnostics_enabled=false` is effective after one AstrBot-only restart; Owner binding remained unchanged and NapCat was not restarted. Yuuk1 Core startup was clean and mounted source matched the workspace. No production message was sent by Codex.
- **Relationship Memory Store Foundation is only a storage foundation.** SQLite schema v1 and scoped CRUD/revisions/tombstones exist. There is no memory extraction, retrieval, prompt injection, LLM tool, or controlled writing. Do not mark Relationship Memory v1 complete.
- The release commit includes Owner identity classification/policy/diagnostics, deterministic direct identity replies, the Foundation store, focused tests, and synchronized docs. It excludes runtime config, SQLite data, Conversation history, identity secrets, logs, and credentials.
- Final closeout checks: pytest **115 passed**; Ruff, compileall, schema JSON, and `git diff --check` **PASS**. Use current `git log` for the exact closeout commit identifier.
- Next stage is not started: Memory Injection, Persona Calibration, and Cloud Deployment remain separate future work.

## Repository and commit

- Project: `D:\project\Yuuk1-QQBot`
- Branch: `main`
- Closeout base HEAD: `8d7d51e9298b65e7394e4fce6986d514f6d982ad` (`feat: add jingjing sticker support`). The final closeout commit is HEAD at the time of this handoff; use `git log -1 --oneline` for the exact SHA and later history.
- All pre-commit changes were reviewed as Sticker v1 implementation, tests, documentation, or the Sticker catalog addition. The closeout includes the new JPEG and this handoff.
- No push was performed.

## Latest user-confirmed QQ E2E

- Ordinary text: PASS.
- Text + QQ custom sticker: PASS.
- Pure sticker: PASS.
- Nickname wake: PASS.
- Ordinary `image` mode compatibility: PASS.
- The QQ client displayed the custom emoji correctly and confirmed it can be favorited. The latest normal send paths passed manual acceptance.
- These results were provided by the user. The final closeout did not send QQ messages or rerun external E2E.

## Read-only runtime snapshot

- Runtime plugin config: `stickers_enabled=true`, `sticker_send_mode=qq_custom`, `sticker_diagnostics_enabled=false`.
- AstrBot and NapCat Compose services were running. AstrBot startup logs confirmed `Yuuk1 Core ready`, `assets=21`, `tool_available=True`, `send_mode=qq_custom`, and `diagnostics=False`.
- The code/schema default send mode is still `image`; diagnostics default is `false`.
- The catalog contains 21 images. `plugins/astrbot_plugin_yuuk1_core/assets/stickers/laugh/a251d04922e251c5439d2d6ad1ff4be1_720.jpg` is a valid JPEG, 1080×1062, 56,205 bytes, within size and pixel limits, and in the correct category.
- Earlier at a diagnostic implementation checkpoint the container had not yet loaded the code. Later user-provided runtime logs confirmed the decoration-boundary diagnostic records appeared. The current runtime has diagnostics disabled.

## Delivery contract and local evidence

- `sticker_send_mode=qq_custom` serializes OneBot `image` with `sub_type=1`; `image` mode remains compatible.
- A pre-send preparation failure or AstrBot `Context.send_message()` returning `False` because no platform matched is a confirmed no-send boundary and may use ordinary-image fallback.
- Every `ActionFailed` is ambiguous. aiocqhttp raises it for OneBot `status=failed` and retains a result dict/retcode, but neither proves non-delivery. NapCat NTEvent acknowledgement timeouts use this exception path. Other send exceptions are also ambiguous. None triggers a retry or ordinary-image fallback.
- For text + Sticker, already-produced text remains intact. For image-only `qq_custom`, an ambiguous result adds no extra image or fallback text. Each turn remains limited to one selected Sticker.
- Plugin warnings record stage and exception type only. Opt-in diagnostics record allowlisted status/count fields and are gated by `sticker_diagnostics_enabled`.
- The NTEvent behavior was tested with local fake outcomes. A real NTEvent timeout has not been re-triggered since the fix; do not claim live timeout E2E verification.

## Final automated checks

- Complete pytest: 79 passed.
- Ruff: PASS.
- Python `compileall`: PASS.
- Schema JSON: PASS.
- `git diff --check`: PASS.
- Secret-pattern scan: 0 findings.
- No real QQ E2E, DeepSeek request, container restart, or NapCat modification was performed during closeout.

## Known limitations

- Historical pure-sticker requests sometimes emitted `(图)` or `(表情已发出)`. Their source remains unknown. Do not globally filter either phrase.
- DeepSeek previously returned empty completions after a successful Sticker tool call. One prior request measured about 115,192 input tokens (about 114,944 cached); no causal connection to the empty completion is established.
- An Agent error may still be followed by delivery of an already-selected Sticker. AstrBot v4.28.2 exposes no reliable public Agent failure marker at the relevant decoration hook; this was not fixed in closeout.
- The empty MessageChain path is not covered through AstrBot's actual `ResultDecorateStage` guard; current fake-hook tests do not close this integration gap.
- The local ambiguous-send regression does not replace a real timeout verification.

## Deferred work

- Sticker Completion Marker Protocol: deferred until Conversation persistence safety is established.
- Context / Memory optimization: a separate future stage; no history or memory data was changed.
- Visual Identity v1: not started.
- Cloud Deployment v1 remains the next broad stage in `PROJECT_PLAN.md`. Server migration has not started; evaluate SnowLuma only during that future deployment stage.

## Important source and test entry points

- `plugins/astrbot_plugin_yuuk1_core/main.py`: Sticker tool, result decoration, OneBot send classification, custom-to-image fallback, after-send path, and sanitized diagnostics.
- `plugins/astrbot_plugin_yuuk1_core/logic.py` and `_conf_schema.json`: `sticker_send_mode` normalization and default-off diagnostics setting.
- `plugins/astrbot_plugin_yuuk1_core/stickers.py`: mode constants and catalog logic.
- `tests/test_astrbot_plugin_registration.py`, `tests/test_yuuk1_logic.py`, `tests/test_stickers.py`: runtime-hook simulation, send outcomes, configuration, and catalog tests.
- `docs/ASTRBOT_RESEARCH.md`: AstrBot v4.28.2 and aiocqhttp send/error boundary findings.
- `PROGRESS.md`: dated feature history and final closeout record.

## Next session

Treat QQ Custom Sticker v1 as closed with the limitations above. Do not start Visual Identity v1, server migration, or another Sticker protocol as part of this handoff. Before any later task, check `git status --short` and `git log -1 --oneline`. Do not push without explicit authorization.

## Owner Identity v1 + Relationship Memory Store Foundation — 2026-10-09

This phase starts from `main` at `9e79a0fe47d1fd8d61a2383e3d32431ac702a806`. That base was clean before implementation; the current implementation and documentation changes are intentionally uncommitted. Recheck the working tree before continuing, and preserve those changes.

- Owner Identity v1 is implemented locally, but is **PENDING QQ E2E**. The `owner_qq_id` schema is an empty-by-default string. Recognition requires trusted platform `aiocqhttp` plus the current event's `sender_id`; it does not use nicknames, message text, @ targets, or `admin_users`. The current-request identity context is temporary `TextPart` data and contains no raw QQ ID. Owner identity grants no management or tool permissions.
- The runtime `owner_qq_id` was not read or changed, and this code was not loaded into a running AstrBot instance during the phase. To enable manual testing, open AstrBot WebUI → Plugins → Yuuk1 Core configuration, enter the Owner QQ ID as a string, and save. Do not add it to tracked files.
- Relationship Memory Store Foundation is implemented and locally tested. The DB path is `data/astrbot/plugin_data/astrbot_plugin_yuuk1_core/relationship_memory.sqlite3`, in the existing AstrBot bind mount. It uses Group Identity HMAC group/member keys, versioned SQLite schema, scoped transactional CRUD, fact-key uniqueness, revision replacement, and tombstones that clear fact text. Corrupt or unsupported databases are rejected without rebuild. SQLite has no static encryption; preserve the DB together with `identity_secret`, `group_identity.json`, and plugin configuration during future backup/migration.
- The store has no memory extraction, retrieval, prompt injection, LLM tool, or chat command. Relationship Memory v1 is not complete. Memory Injection and Controlled Memory Writing remain **NOT STARTED**.
- Current phase forbids runtime/config/container changes; none were made. Manual QQ E2E is still required for Owner recognition, same-name non-Owner rejection, non-QQ rejection, and unchanged admin command behavior. Store persistence and CRUD are local tests only.
- Final local checks for this phase: complete pytest **91 passed**; Ruff **PASS**; Python `compileall` **PASS**; schema JSON **PASS**; `git diff --check` **PASS**; privacy scan found **0 credential-pattern findings**, and the supplied Owner ID was absent from changed files. These checks do not establish live AstrBot loading or QQ E2E.

Next authorized task is only the user-reviewed manual Owner Identity QQ verification. Do not infer authorization to add Memory Injection, Controlled Writing, cloud deployment, or commit these changes.

## Owner Identity same-name impersonation mitigation — 2026-10-10 (latest checkpoint)

This checkpoint supersedes the 2026-10-09 Owner implementation details above. The earlier Owner E2E failed in a specific way: Account B renamed to `Yuuk1` was attributed the real Owner's relationship and maintainer identity. A later fresh QQ E2E has **not** been run after this local mitigation.

### Current repository baseline

- Branch: `main`; HEAD `9e79a0fe47d1fd8d61a2383e3d32431ac702a806` at this checkpoint.
- Worktree is intentionally uncommitted. Preserve the existing Relationship Memory foundation and all edits; do not reset, clean, or stage broadly.
- Existing untracked files remain `plugins/astrbot_plugin_yuuk1_core/relationship_memory.py` and `tests/test_relationship_memory.py`.
- Files changed across this phase include the existing project docs and Owner/Relationship implementation, tests, plus this request-level mitigation and its docs. Recheck the exact full diff before any later commit.

### Current Owner identity design

- `logic.classify_owner_identity()` returns `verified_owner`, `verified_non_owner`, `unconfigured`, or `unavailable`, using only platform name, current sender ID, and normalized configured Owner ID. Nickname, group card, text, @, Reply, shared history, and LLM output are not inputs. `is_configured_owner()` remains a compatibility wrapper for the positive state.
- For every allowed QQ request, `customize_request()` appends a concise `<trusted_identity_policy>` to that request's `ProviderRequest.system_prompt`, after the selected Persona/stable plugin system prompt. Verified non-Owners may still be addressed by display name (including `Yuuk1`), but cannot be assigned the Owner relationship, maintainer role, bot-setup history, or Owner experiences based on those names/messages. The true Yuuk1 can still be discussed as a separate person.
- No identity status is stored globally, on the plugin instance, or on a shared Conversation. The request policy is not inserted into user-content parts. AstrBot v4.28.2 persists user/assistant message pairs, not `system_prompt`; generated assistant replies can still enter shared history and are not trusted authentication evidence.
- New `owner_identity_diagnostics_enabled` is default-off. When on, it logs only an eight-character random correlation marker plus booleans for trusted platform match, whether Owner is configured, match state, and policy injection. It never logs QQ/group ID, names, body, prompt, HMAC, or credentials.
- Owner remains separate from `admin_users`; no admin command behavior changes. Relationship Memory Store Foundation is not full Relationship Memory v1: no injection or controlled writing exists.

### Verification and next action

- The Owner/plugin/schema focused local suite passed **33 tests** after the change. Consult the current final report / latest progress checkpoint for the complete pytest, Ruff, compileall, JSON schema, and diff-check results.
- Final local checks for this checkpoint: complete pytest **92 passed**; Ruff **PASS**; `compileall` on plugin and tests **PASS**; schema JSON **PASS**; `git diff --check` **PASS**; credential-pattern scan on changed and untracked files **0 findings**. These do not establish model compliance or live runtime loading.
- A privacy-safe read of the current runtime config found an Owner value configured and Owner diagnostics effectively off; the value was not displayed. AstrBot and NapCat were running. No restart or reload was done, and do not assume the running plugin has this change.
- Do not claim the same-name issue is fixed in live behavior based on mocks. The prompt-level mitigation is locally implemented only; model compliance is **PENDING** real QQ / DeepSeek verification.
- Next user step: after choosing to deploy/reload this code, test one verified Owner with a changed ordinary nickname, one non-Owner named `Yuuk1`, one non-Owner using the Owner's exact display name, one self-claim/@/quoted-history attempt, and one normal member/admin interaction in a safe test context. Confirm the model can address the impostor as `Yuuk1` without transferring the real Owner's relationship or history. Do not start Memory Injection or Controlled Writing as part of that test.
- This task did not restart Docker, change runtime settings, send a QQ message, contact DeepSeek, commit, or push. The running instance must not be assumed to have loaded the current local code.

## Owner Identity runtime regression — 2026-10-10 (current status)

The user has now run fresh QQ E2E and reported **FAIL**: real Owner A (display name `奶龙鉴赏家`) was called a group member, while distinct non-Owner B (display name `Yuuk1`) was called Owner. Do not infer authentication state from the model's statements about verification. This supersedes the previous checkpoint's pending-E2E wording.

Read-only checks found AstrBot and NapCat running, the read-only Yuuk1 plugin mount effective, and the then-current plugin files loaded at AstrBot startup. The runtime Owner configuration is syntactically valid and corresponds to A's identity-store record, not B's. This was established without disclosing account IDs or identity keys. Owner diagnostics were disabled; no A/B request classification evidence exists for the failed turns. The root cause is **UNKNOWN** until real request-level classification is captured.

The AstrBot v4.28.2 `on_llm_request` hook runs before its deferred `ToolLoopAgentRunner.reset`; a local test using the real request and runner classes confirmed synthetic Owner/non-Owner rules become separate system messages. This does not establish the content of the failing Provider requests or model compliance. Conversation history is shared by the group and may contain past incorrect assistant statements; do not delete it as part of diagnosis.

The uncommitted code now extends the existing default-off Owner diagnostic with `identity_classification` and `request_context_isolated`. The latter means only that the incoming request **system prompt** did not already contain an Owner policy. It does not inspect all history or the Provider payload. This change is not loaded into the already-running AstrBot process. No identity algorithm, Persona, Provider, relationship database, Sticker path, or runtime configuration was changed.

Next action requires user authorization for a temporary runtime configuration change and AstrBot-only restart. Enable `owner_identity_diagnostics_enabled`, then have the user send A and B messages one at a time. Correlate each safe diagnostic record using timestamp/order and the random request marker; confirm A=`verified_owner` and B=`verified_non_owner`. If either differs, investigate event/config classification. If both match, examine the assembled Provider request and conflicting Persona/history influence using privacy-safe observations, then propose the smallest rule change. Do not claim Owner Identity v1 passes until A/B interleaving and ordinary-member QQ E2E pass. No automatic QQ messages, restart, commit, or push were performed in this diagnostic phase.

## Owner Agent boundary diagnostic — 2026-10-10 (newest checkpoint)

- The approved manual A/B/A/B QQ test produced exactly four safe Owner diagnostic records. A1 and A2 were `verified_owner`; B1 and B2 were `verified_non_owner`; trusted platform, Owner configured, identity context injection, and request-entry isolation were all true. The bot's visible answers remained wrong in all four turns. Thus Hook-level authentication is correct for these observed requests, while the exact sent Provider payload and model-side reason remain unknown.
- The selected global Persona includes Yuuk1/Owner relationship language. The group shares one persistent Conversation with historical identity-related assistant replies. These are possible model-context influences, not proven causes. Do not change Owner binding, HMAC state, Persona, or Conversation to mask this failure.
- New uncommitted diagnostic code uses the existing default-off `owner_identity_diagnostics_enabled` setting and one event-local random request marker across `hook_request`, `agent_begin`, and `agent_done`. It records only classification, policy presence/completeness/match, policy message role, and system message count. The two Agent hooks are before and after context processing, respectively; **neither is the final HTTP payload boundary**. `agent_done` may not fire on Agent failure. Tests use synthetic identities and no network.
- The running AstrBot process still has the previous code; the new diagnostic awaits an approved AstrBot-only restart. The ignored runtime setting is currently `true` and must be changed back to `false` followed by an AstrBot-only restart after diagnosis. Merely editing the file does not disable the running process. No automatic QQ messages, restart, commit, or push occurred in this preparation turn.
- Deterministic identity Q&A was evaluated only. For tightly recognized first-person questions, a direct plugin reply can guarantee the Owner fact; LLM rewording cannot guarantee that it preserves the conclusion. Avoid quotes, reported speech, and ordinary discussion when matching. Any behavior implementation is a later, separately authorized step.

## Owner deterministic identity reply — 2026-10-10 (pre-deployment checkpoint; superseded)

- The 01:34 CST user-run A/B QQ test produced all three diagnostic stages for each request. A was `verified_owner`, B was `verified_non_owner`; the policy was complete, in one Agent system message, and matched the classification at Agent Begin and Agent Done. The two visible model answers still reversed identity. These hooks are not final HTTP payload capture; exact model-side cause remains unknown. The previous section's statement that new diagnostic code was not loaded is now historical: an approved AstrBot-only restart loaded it before this A/B test.
- The newest local code intercepts only short, directly addressed first-person identity questions at the existing QQ `on_waiting_llm_request` guard, after allowlist and rate limits. `owner_identity_reply.py` rejects Reply, forwards, media, long/quoted/code text, third-person queries, and ambiguous address. `classify_owner_identity()` remains the only Owner decision; nickname is display text only. The plugin stops the event before Provider selection and directly sends one deterministic answer. No send retry occurs on an unknown outcome. Direct sends update the existing Free Talk buffer on success, since AstrBot's normal `after_message_sent` hook does not run on this path. This does not touch Sticker or Relationship Memory.
- The implementation and tests are uncommitted. Synthetic local tests plus an isolated real AstrBot v4.28.2 Hook dispatcher/Agent substage probe have passed; consult the latest `PROGRESS.md` entry and rerun checks for exact final counts. **No real QQ E2E has tested this new behavior.** The running AstrBot process still contains the prior behavior; the ignored runtime `owner_identity_diagnostics_enabled` is still `true` despite its default-off schema. Await user deployment approval, then set false and restart **only AstrBot once** to load the code and disable runtime diagnostics. Verify the new plugin is ready and NapCat unchanged before asking the user to perform Owner/same-name/ordinary-chat QQ E2E. Do not commit or push without explicit instruction.
