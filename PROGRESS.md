# Progress

Last updated: 2026-10-07

## v0.1 Release Candidate

The first real Docker startup has now verified both containers, both WebUIs and the Yuuk1 Core bind mount. A command decorator compatibility bug discovered during this startup was fixed without changing AstrBot Core. The baseline commit is `a7eac7d281da2c18b4d3c9ab94be52859448dcf0` on `main`; this work retains its history and architecture.

## Completed

- Replaced both mutable `latest` images with reviewed official stable release tags and immutable multi-architecture digests: AstrBot v4.28.2 and NapCat-Docker v4.18.33. Recorded sources, upgrade and rollback procedure in `docs/UPSTREAM.md` and added a read-only upstream checker that classifies beta from tag names as well as release metadata.
- Confirmed in AstrBot v4.28.2 source that its Star loader scans `/AstrBot/data/plugins/<name>/main.py`. Compose mounts the repository Yuuk1 Core source at exactly that path, read-only; a container restart reloads edited source. The plugin emits `Yuuk1 Core ready` after initialization, and the marker has now been observed in real post-restart logs.
- **First runtime compatibility fix:** the original `@filter.command_group("yuuk1").custom_filter(...)` called `.custom_filter` on the plain decorator function returned by AstrBot v4.28.2 and failed at import time with `AttributeError`. The fixed stack applies `@filter.command_group("yuuk1")` to the method first, then `@filter.custom_filter(Yuuk1CommandAllowlistFilter)` to the resulting `RegisteringCommandable`. All other plugin decorators were checked against the v4.28.2 exports. A plugin-import registration regression test now covers this composition.
- QQ group allowlist remains fail-closed; private chats are now disabled by default. `/yuuk1 reset` is administrator-only and uses AstrBot ConversationManager. Status reports no provider ID, model string or credential. The plugin only supplements AstrBot's native persona and conversation pipeline.
- Added atomic in-memory per-user and per-group request limits. Defaults are 3 admitted LLM requests per QQ user across chats and 15 per group, each over 60 seconds. A request denied by one bucket does not consume the other; expired scopes are pruned during later traffic.
- Kept WebUI host binds on `127.0.0.1`, OneBot 6199 unpublished, a two-service bridge, persistent narrow mounts and `no-new-privileges` for AstrBot. NapCat `MODE=astrbot` rewrites its empty-token OneBot template on every start, so token auto-configuration was not added without a reliable persistent two-sided mechanism.
- Bootstrap prepares the ignored local `.env`, data and backup directories before checking Docker. Doctor distinguishes `[PASS]`, `[WARN]`, `[FAIL]` and `[MANUAL]` and checks container, WebUI, plugin-ready and OneBot log evidence. Real NapCat v4.18.33 has Bash but no `node` executable, so doctor now uses Bash's TCP probe and exits 0 when all mandatory checks pass.
- Added a stopped-service backup script for AstrBot data and NapCat config, excluding logs/cache/temp; optional `-IncludeQQSession` also saves the QQ login state. `backups/` is ignored by Git.
- Added CI for Python syntax, pytest, Ruff, Star metadata/schema, secret and ignored-data checks, Compose config and mounts, plus Windows PowerShell parsing. Dependabot covers GitHub Actions and development Python dependencies; runtime images remain manually reviewed.

## Verification performed locally

- **PASS:** `python -m pytest -q`: 18 tests, including v4.28.2 command decorator composition and plugin import.
- **PASS:** `python -m ruff check plugins tests` and `python -m compileall -q plugins tests`.
- **PASS:** PowerShell parser for every `scripts/*.ps1` file.
- **PASS:** `git diff --check`, YAML/JSON and Compose structure checks, Star metadata/schema checks, tracked-file secret-pattern scan, and Git ignore checks.
- **PASS:** `scripts/check-upstream.ps1` queried official releases and Docker Hub digests; AstrBot `v4.29.0-beta.1` was classified as BETA despite unreliable GitHub prerelease metadata.
- **PASS:** `scripts/backup.ps1` was exercised with temporary probe data. The archive contained only AstrBot data and NapCat config, excluding a log and QQ session; probe files and archive were removed afterward.
- **PASS:** Docker CLI 29.8.2 and Compose 5.5.1 work via the installed user-local Docker Desktop path. `docker compose config --quiet` passes; both containers are running and both WebUIs respond.
- **PASS:** `docker compose restart astrbot`; post-restart logs show `Yuuk1 Core ready` and no new import failure. Because Docker `restart` retained the earlier failed-start logs, AstrBot alone was then recreated with its persistent bind mount intact. The new `docker compose logs astrbot --tail 300` contains the ready marker and zero `Failed to import/load plugin astrbot_plugin_yuuk1_core`, tracebacks or error lines.
- **PASS:** `scripts/doctor.ps1` reports `Yuuk1 Core plugin load = PASS` and zero failures. Missing DeepSeek, OneBot adapter/connection and QQ login remain `[MANUAL]`.

## Blocked and manual integration

- **RUNTIME PASS:** Docker Desktop is running. AstrBot v4.28.2, NapCat v4.18.33, both WebUIs, Yuuk1 Core mount and Yuuk1 Core initialization are verified. Docker CLI is installed under the user-local Docker Desktop directory and needs that directory on PATH in this Codex shell.
- **BLOCKED_BY_LOCAL_GH:** `gh --version` and `gh auth status` cannot run because GitHub CLI is not installed. No remote is configured, no GitHub repository was created, no push occurred and GitHub Actions has not run. The CI configuration itself is locally checked.
- **MANUAL VERIFICATION REQUIRED:** provide the real DeepSeek API Key, configure and select its AstrBot Provider/Profile, enable the OneBot v11 Adapter, scan NapCat QQ login, set `allowed_groups` and `admin_users`, then test actual QQ group commands and AI responses. These integrations were deliberately not configured in this fix.

The next work should stay within v0.1 integration until the above runtime and first CI checks have passed. Product features planned for v0.2 have not been started.
