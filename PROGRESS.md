# Progress

Last updated: 2026-10-07

## v0.1 Release Candidate

The repository is ready for manual runtime integration. The baseline commit is `a7eac7d281da2c18b4d3c9ab94be52859448dcf0` on `main`; this hardening work retains its history and architecture.

## Completed

- Replaced both mutable `latest` images with reviewed official stable release tags and immutable multi-architecture digests: AstrBot v4.28.2 and NapCat-Docker v4.18.33. Recorded sources, upgrade and rollback procedure in `docs/UPSTREAM.md` and added a read-only upstream checker that classifies beta from tag names as well as release metadata.
- Confirmed in AstrBot v4.28.2 source that its Star loader scans `/AstrBot/data/plugins/<name>/main.py`. Compose mounts the repository Yuuk1 Core source at exactly that path, read-only; a container restart reloads edited source. The plugin now emits `Yuuk1 Core ready` after initialization so `doctor.ps1` can check real runtime evidence once Docker is available.
- QQ group allowlist remains fail-closed; private chats are now disabled by default. `/yuuk1 reset` is administrator-only and uses AstrBot ConversationManager. Status reports no provider ID, model string or credential. The plugin only supplements AstrBot's native persona and conversation pipeline.
- Added atomic in-memory per-user and per-group request limits. Defaults are 3 admitted LLM requests per QQ user across chats and 15 per group, each over 60 seconds. A request denied by one bucket does not consume the other; expired scopes are pruned during later traffic.
- Kept WebUI host binds on `127.0.0.1`, OneBot 6199 unpublished, a two-service bridge, persistent narrow mounts and `no-new-privileges` for AstrBot. NapCat `MODE=astrbot` rewrites its empty-token OneBot template on every start, so token auto-configuration was not added without a reliable persistent two-sided mechanism.
- Bootstrap prepares the ignored local `.env`, data and backup directories before checking Docker. Doctor now distinguishes `[PASS]`, `[WARN]`, `[FAIL]` and `[MANUAL]` and checks container, WebUI, plugin-ready and OneBot log evidence when runtime is available.
- Added a stopped-service backup script for AstrBot data and NapCat config, excluding logs/cache/temp; optional `-IncludeQQSession` also saves the QQ login state. `backups/` is ignored by Git.
- Added CI for Python syntax, pytest, Ruff, Star metadata/schema, secret and ignored-data checks, Compose config and mounts, plus Windows PowerShell parsing. Dependabot covers GitHub Actions and development Python dependencies; runtime images remain manually reviewed.

## Verification performed locally

- **PASS:** `python -m pytest -q`: 16 tests.
- **PASS:** `python -m ruff check plugins tests` and `python -m compileall -q plugins tests`.
- **PASS:** PowerShell parser for every `scripts/*.ps1` file.
- **PASS:** `git diff --check`, YAML/JSON and Compose structure checks, Star metadata/schema checks, tracked-file secret-pattern scan, and Git ignore checks.
- **PASS:** `scripts/check-upstream.ps1` queried official releases and Docker Hub digests; AstrBot `v4.29.0-beta.1` was classified as BETA despite unreliable GitHub prerelease metadata.
- **PASS:** `scripts/backup.ps1` was exercised with temporary probe data. The archive contained only AstrBot data and NapCat config, excluding a log and QQ session; probe files and archive were removed afterward.
- **EXPECTED BLOCK:** `scripts/bootstrap.ps1` prepared ignored files/directories and exited 2 because Docker CLI is absent. `scripts/doctor.ps1` reported the missing Docker CLI and manual DeepSeek setup without exposing a secret.

## Blocked and manual integration

- **BLOCKED_BY_LOCAL_DOCKER:** `docker --version`, `docker compose version`, `docker compose config`, image pull, container startup, WebUI responses, actual Yuuk1 Core load and OneBot connection cannot be verified here. Docker Desktop and CLI are not installed in this workspace. The source and mount paths have been inspected, but static inspection is not a runtime PASS.
- **BLOCKED_BY_LOCAL_GH:** `gh --version` and `gh auth status` cannot run because GitHub CLI is not installed. No remote is configured, no GitHub repository was created, no push occurred and GitHub Actions has not run. The CI configuration itself is locally checked.
- **MANUAL VERIFICATION REQUIRED:** provide the real DeepSeek API Key, configure and select its AstrBot Provider/Profile, log in to both WebUIs and rotate initial credentials, enable the OneBot v11 Adapter, scan NapCat QQ login, set `allowed_groups` and `admin_users`, then test actual QQ group commands and AI responses.

The next work should stay within v0.1 integration until the above runtime and first CI checks have passed. Product features planned for v0.2 have not been started.
