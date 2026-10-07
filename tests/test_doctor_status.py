"""Exercise doctor's pure status rules without Docker, credentials, or API calls.

These tests invoke the same PowerShell functions used by doctor.ps1. JSON
fixtures keep runtime inputs synthetic, including deliberately stale log hints.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATUS_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doctor-status.ps1"
NAPCAT_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "napcat-login-status.ps1"
)
FUNCTIONS = {
    "Get-DoctorPluginState",
    "Get-DoctorOneBotState",
    "Get-DoctorDeepSeekState",
    "Get-DoctorIdentitySecretState",
    "Get-DoctorIdentityStoreState",
}


def _evaluate(function_name: str, states: list[dict[str, object]]) -> tuple[list[dict], str]:
    assert function_name in FUNCTIONS
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required for doctor status tests")

    script_path = str(STATUS_SCRIPT).replace("'", "''")
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f". '{script_path}'; "
        "$states = [Console]::In.ReadToEnd() | ConvertFrom-Json -AsHashtable; "
        "$results = @(foreach ($state in $states) { "
        f"{function_name} -State $state "
        "}); "
        "[Console]::Out.WriteLine((ConvertTo-Json -InputObject $results "
        "-Compress -Depth 8))"
    )
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        input=json.dumps(states),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, list)
    assert len(parsed) == len(states)
    for result in parsed:
        assert isinstance(result, dict)
        assert result["Level"] in {"PASS", "WARN", "FAIL", "MANUAL"}
        assert isinstance(result["Detail"], str) and result["Detail"]
    return parsed, completed.stdout + completed.stderr


def test_plugin_requires_mount_discovery_enablement_and_current_load() -> None:
    healthy = {
        "mounted": True,
        "discovered": True,
        "enabled": True,
        "ready_current": True,
    }
    states = [
        healthy,
        *(healthy | {key: False} for key in healthy),
        healthy | {"ready_current": False, "old_log_ready": True},
    ]
    results, _ = _evaluate("Get-DoctorPluginState", states)
    assert results[0]["Level"] == "PASS"
    assert all(result["Level"] != "PASS" for result in results[1:])


def test_onebot_separates_configuration_tcp_and_live_websocket() -> None:
    connected = {
        "adapter_enabled": True,
        "listening": True,
        "tcp_reachable": True,
        "reverse_configured": True,
        "qq_online": True,
        "socket_established": True,
        "websocket_connected": True,
    }
    states = [
        connected,
        *(connected | {key: False} for key in connected),
        connected | {"websocket_connected": False, "old_log_connected": True},
    ]
    results, _ = _evaluate("Get-DoctorOneBotState", states)
    assert results[0]["Level"] == "PASS"
    assert all(result["Level"] != "PASS" for result in results[1:])


def test_deepseek_requires_enabled_source_key_reference_model_and_default() -> None:
    configured = {
        "runtime_key_present": True,
        "source_enabled": True,
        "key_reference_valid": True,
        "model_enabled": True,
        "default_selected": True,
            }
    states = [configured, *(configured | {key: False} for key in configured)]
    results, _ = _evaluate("Get-DoctorDeepSeekState", states)
    assert results[0]["Level"] == "PASS"
    assert all(result["Level"] != "PASS" for result in results[1:])


def test_identity_status_requires_persistent_secret_and_healthy_loaded_store() -> None:
    configured = {
        "identity_enabled": True,
        "identity_persistence_enabled": True,
        "identity_secret_available": True,
        "identity_loaded": True,
        "identity_healthy": True,
        "identity_known_members": 8,
    }
    results, _ = _evaluate(
        "Get-DoctorIdentitySecretState",
        [configured, configured | {"identity_secret_available": False}],
    )
    assert [item["Level"] for item in results] == ["PASS", "FAIL"]
    results, output = _evaluate(
        "Get-DoctorIdentityStoreState",
        [
            configured,
            configured | {"identity_loaded": False},
            configured | {"identity_healthy": False},
            configured | {"identity_persistence_enabled": False},
        ],
    )
    assert [item["Level"] for item in results] == ["PASS", "WARN", "FAIL", "MANUAL"]
    assert "known_members=8" in output
    assert "member_" not in output


@pytest.mark.parametrize("function_name", sorted(FUNCTIONS))
def test_status_details_never_echo_secret_or_raw_config(function_name: str) -> None:
    sentinel = "DOCTOR_TEST_SECRET_9e93_DO_NOT_PRINT"
    state = {
        "mounted": True,
        "discovered": True,
        "enabled": True,
        "ready_current": True,
        "adapter_enabled": True,
        "listening": True,
        "tcp_reachable": True,
        "reverse_configured": True,
        "qq_online": True,
        "socket_established": True,
        "websocket_connected": True,
        "source_enabled": True,
        "runtime_key_present": True,
        "key_reference_valid": True,
        "model_enabled": True,
        "default_selected": True,
        "identity_enabled": True,
        "identity_persistence_enabled": True,
        "identity_secret_available": True,
        "identity_loaded": True,
        "identity_healthy": True,
        "identity_known_members": 8,
        "api_key": sentinel,
        "raw_config": {"secret": sentinel},
    }
    missing_field = {
        "Get-DoctorPluginState": "ready_current",
        "Get-DoctorOneBotState": "websocket_connected",
        "Get-DoctorDeepSeekState": "key_reference_valid",
        "Get-DoctorIdentitySecretState": "identity_secret_available",
        "Get-DoctorIdentityStoreState": "identity_healthy",
    }[function_name]
    results, output = _evaluate(
        function_name, [state, state | {missing_field: False}]
    )
    assert results[0]["Level"] == "PASS"
    assert results[1]["Level"] != "PASS"
    assert sentinel not in output


def test_napcat_login_requires_authenticated_live_status_without_leaking_data() -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required for NapCat login status tests")

    sentinel = "DOCTOR_TEST_CREDENTIAL_6b12_DO_NOT_PRINT"
    online = {
        "auth": {"code": 0, "data": {"Credential": sentinel}},
        "status": {
            "code": 0,
            "data": {"isLogin": True, "coreReady": True, "qq": sentinel},
        },
        "two_factor_enabled": False,
    }
    cases = [
        online,
        online
        | {"status": {"code": 0, "data": {"isLogin": False, "coreReady": True}}},
        online | {"two_factor_enabled": True},
        online | {"auth": {"code": 401}},
        online | {"status": {"code": 0, "data": {}}},
    ]
    script_path = str(NAPCAT_SCRIPT).replace("'", "''")
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f". '{script_path}' -ImportOnly; "
        "$cases = [Console]::In.ReadToEnd() | ConvertFrom-Json -AsHashtable; "
        "$results = @(foreach ($case in $cases) { "
        "Resolve-NapCatLoginStatus -AuthResponse $case.auth "
        "-StatusResponse $case.status "
        "-TwoFactorEnabled $case.two_factor_enabled "
        "}); "
        "[Console]::Out.WriteLine((ConvertTo-Json -InputObject $results "
        "-Compress -Depth 8))"
    )
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        input=json.dumps(cases),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    results = json.loads(completed.stdout)
    assert [result["Status"] for result in results] == [
        "PASS",
        "FAIL",
        "MANUAL",
        "MANUAL",
        "MANUAL",
    ]
    assert all(isinstance(result["Message"], str) for result in results)
    assert sentinel not in completed.stdout + completed.stderr
