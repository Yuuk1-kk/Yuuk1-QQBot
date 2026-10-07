# Progress

Last updated: 2026-10-07

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
