# Progress

Last updated: 2026-10-07

## Implemented in the v0.1 repository

- AstrBot + NapCat Compose, private shared bridge network, persistent data bind mounts, local-only WebUI bindings, internal OneBot reverse WS.
- Yuuk1 Core Star metadata, WebUI schema, fail-closed group allowlist, configured project admins, persona hook, help/status/reset commands, in-memory per-group sliding window limiter, plugin error handling.
- PowerShell bootstrap/start/stop/restart/logs/doctor scripts.
- Setup, NapCat, DeepSeek, operations, architecture, research, project plan, and repository guidance.
- Unit tests for access checks, settings normalization, and sliding-window behavior.

## Local verification

- **PASS:** Python `compileall` for the plugin.
- **PASS:** Ruff checks for `plugins/` and `tests/`.
- **PASS:** Pytest policy suite (8 tests).
- **PASS:** PowerShell parser check for all 6 management scripts.
- **PASS:** YAML/JSON parsing and structural checks for Compose, Star metadata and configuration schema.
- **PASS:** `git grep` key-pattern scan found no obvious API keys in tracked files; `.env` and `data/` ignore rules were checked.
- **NOT RUN:** `docker compose config`, image pull and container startup; Docker CLI is not installed in this workspace.
- **NOT RUN:** Pyright; the AstrBot SDK is provided by the container runtime and is not installed in the local Python environment.
- **MANUAL VERIFICATION REQUIRED:** DeepSeek API requests and QQ login/group message flow need user-owned credentials and a QQ scan.

## Manual verification required

- Provide DeepSeek API Key in local `.env`.
- Start Docker services.
- Configure and test the AstrBot DeepSeek provider and select it in the active Profile.
- Enable OneBot v11 in AstrBot and verify NapCat Reverse WebSocket connection.
- Scan into NapCat with the intended QQ account; configure allowed group/admin IDs in the Star schema.
- Test commands and AI replies in an allowed QQ group.
