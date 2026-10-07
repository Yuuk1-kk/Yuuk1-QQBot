"""Exercise restart's QQ-session guard without touching the real Docker stack."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

RESTART_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "restart.ps1"


def _ps_quote(value: Path) -> str:
    return str(value).replace("'", "''")


def _run_restart(
    tmp_path: Path, *, account_selected: bool, qq_file_present: bool
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required for restart guard tests")

    repo = tmp_path / "synthetic-repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    restart = scripts / "restart.ps1"
    restart.write_bytes(RESTART_SCRIPT.read_bytes())
    (repo / ".env").write_text("# synthetic fixture\n", encoding="utf-8")

    config = repo / "data" / "napcat" / "config"
    config.mkdir(parents=True)
    selected = {"autoLoginAccount": "synthetic-account"} if account_selected else {}
    (config / "webui.json").write_text(json.dumps(selected), encoding="utf-8")

    nt_qq = repo / "data" / "napcat" / "qq" / "nt_qq"
    nt_qq.mkdir(parents=True)
    if qq_file_present:
        (nt_qq / "synthetic-session.dat").write_text(
            "synthetic fixture", encoding="utf-8"
        )

    calls_path = tmp_path / "docker-calls.txt"
    command = (
        "$ErrorActionPreference = 'Stop'; "
        "function docker { "
        f"Add-Content -LiteralPath '{_ps_quote(calls_path)}' "
        "-Value ($args -join ' '); "
        "$global:LASTEXITCODE = 0 "
        "}; "
        "try { "
        f"& '{_ps_quote(restart)}'; "
        "exit 0 "
        "} catch { "
        "[Console]::Error.WriteLine($_.Exception.Message); "
        "exit 99 "
        "}"
    )
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    calls = calls_path.read_text(encoding="utf-8").splitlines() if calls_path.exists() else []
    return completed, calls


def test_restart_blocks_recreate_without_auto_login_account(tmp_path: Path) -> None:
    completed, calls = _run_restart(
        tmp_path, account_selected=False, qq_file_present=True
    )
    assert completed.returncode == 99
    assert "自动登录账号" in completed.stderr
    assert calls == []


def test_restart_blocks_recreate_without_qq_session_files(tmp_path: Path) -> None:
    completed, calls = _run_restart(
        tmp_path, account_selected=True, qq_file_present=False
    )
    assert completed.returncode == 99
    assert "QQ 持久化数据" in completed.stderr
    assert calls == []


def test_restart_recreates_with_synthetic_account_and_qq_file(tmp_path: Path) -> None:
    completed, calls = _run_restart(
        tmp_path, account_selected=True, qq_file_present=True
    )
    assert completed.returncode == 0, completed.stderr
    assert calls == ["compose config --quiet", "compose up -d --force-recreate"]
