"""Read-only runtime probe rules using synthetic files and configuration."""

from __future__ import annotations

import json
import runpy
import socket
import sqlite3
from pathlib import Path

import pytest

PROBE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/astrbot-runtime-status.py")
)


def test_ready_marker_requires_the_current_process_start_tick(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    process = proc / "1"
    process.mkdir(parents=True)
    (process / "stat").write_text(
        "1 (AstrBot runtime) S " + " ".join(["0"] * 18 + ["12345"]),
        encoding="utf-8",
    )
    marker = tmp_path / "ready.json"
    marker.write_text(json.dumps({"pid": 1, "start_ticks": "12345"}), encoding="utf-8")
    assert PROBE["current_marker"](marker, proc)

    marker.write_text(json.dumps({"pid": 1, "start_ticks": "old"}), encoding="utf-8")
    assert not PROBE["current_marker"](marker, proc)
    marker.write_text(json.dumps({"pid": 43, "start_ticks": "12345"}), encoding="utf-8")
    assert not PROBE["current_marker"](marker, proc)

    marker.write_text(
        json.dumps(
            {
                "pid": 1,
                "start_ticks": "12345",
                "sampled_monotonic_ns": 10_000_000_000,
                "connected": True,
            }
        ),
        encoding="utf-8",
    )
    assert PROBE["current_connection_marker"](marker, proc, 12_000_000_000)
    assert not PROBE["current_connection_marker"](marker, proc, 16_000_000_000)
    marker.write_text(
        json.dumps(
            {
                "pid": 1,
                "start_ticks": "12345",
                "sampled_monotonic_ns": 10_000_000_000,
                "connected": False,
            }
        ),
        encoding="utf-8",
    )
    assert not PROBE["current_connection_marker"](marker, proc, 12_000_000_000)


def test_identity_marker_returns_only_current_process_safe_status(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    process = proc / "1"
    process.mkdir(parents=True)
    (process / "stat").write_text(
        "1 (AstrBot runtime) S " + " ".join(["0"] * 18 + ["12345"]),
        encoding="utf-8",
    )
    marker = tmp_path / "identity.json"
    marker.write_text(
        json.dumps(
            {
                "pid": 1,
                "start_ticks": "12345",
                "identity_enabled": True,
                "persistence_enabled": True,
                "loaded": True,
                "healthy": True,
                "secret_available": True,
                "known_members": 8,
                "secret": "runtime-private-secret",
                "member_key": "raw-private-member-id",
            }
        ),
        encoding="utf-8",
    )
    status = PROBE["current_identity_marker"](marker, proc)
    assert status == {
        "identity_enabled": True,
        "identity_persistence_enabled": True,
        "identity_loaded": True,
        "identity_healthy": True,
        "identity_secret_available": True,
        "identity_known_members": 8,
    }
    assert "runtime-private-secret" not in json.dumps(status)
    assert "raw-private-member-id" not in json.dumps(status)
    marker.write_text(
        json.dumps({"pid": 9, "start_ticks": "12345", "healthy": True}),
        encoding="utf-8",
    )
    assert not PROBE["current_identity_marker"](marker, proc)


def test_deepseek_and_onebot_probe_checks_links_without_returning_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "DOCTOR_SECRET_SENTINEL_DO_NOT_PRINT"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    config = {
        "provider_settings": {"enable": True},
        "provider_sources": [
            {
                "id": "source",
                "provider": "deepseek",
                "type": "openai_chat_completion",
                "enable": True,
                "key": ["$DEEPSEEK_API_KEY"],
                "other_secret": secret,
            }
        ],
        "provider": [
            {
                "id": "deepseek/deepseek-flash",
                "model": "deepseek-flash",
                "enable": True,
                "provider_source_id": "source",
            }
        ],
        "agent_runner": {
            "runner_type": "local",
            "config": {"model": {"provider_id": "deepseek/deepseek-flash"}},
        },
        "platform": [
            {
                "type": "aiocqhttp",
                "enable": True,
                "ws_reverse_host": "0.0.0.0",
                "ws_reverse_port": 6199,
            }
        ],
    }
    healthy = PROBE["config_state"](config)
    assert all(healthy.values())
    assert secret not in json.dumps(healthy)

    monkeypatch.delenv("DEEPSEEK_API_KEY")
    assert not PROBE["config_state"](config)["runtime_key_present"]
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    config["provider_sources"].append(
        {
            "id": "another-deepseek-source",
            "provider": "deepseek",
            "type": "openai_chat_completion",
            "enable": True,
            "key": ["$DEEPSEEK_API_KEY"],
        }
    )
    assert all(PROBE["config_state"](config).values())

    config["provider_sources"][0]["key"] = [secret]
    assert not PROBE["config_state"](config)["key_reference_valid"]
    config["provider_sources"][0]["key"] = ["$DEEPSEEK_API_KEY"]
    config["provider"][0]["provider_source_id"] = "wrong"
    assert not PROBE["config_state"](config)["model_enabled"]
    config["platform"][0]["enable"] = False
    assert not PROBE["config_state"](config)["adapter_enabled"]


def test_onebot_socket_probe_requires_current_peer_not_just_listener(tmp_path: Path) -> None:
    peer = "172.18.0.3"
    remote = socket.inet_aton(peer)[::-1].hex().upper()
    table = tmp_path / "tcp"
    table.write_text(
        "sl local_address rem_address st\n"
        "0: 00000000:1837 00000000:0000 0A\n"
        f"1: 020012AC:1837 {remote}:BEEF 01\n",
        encoding="ascii",
    )
    assert PROBE["tcp_state"](6199, peer, (table,)) == (True, True)
    assert PROBE["tcp_state"](6199, "172.18.0.4", (table,)) == (True, False)
    assert PROBE["tcp_state"](6199, None, (table,)) == (True, False)


def test_plugin_enabled_reads_the_real_preference_shape(tmp_path: Path) -> None:
    db_path = tmp_path / "data_v4.db"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE preferences (scope TEXT, scope_id TEXT, key TEXT, value TEXT)"
        )
        assert PROBE["plugin_enabled"](db_path)
        db.execute(
            "INSERT INTO preferences VALUES (?, ?, ?, ?)",
            (
                "global",
                "global",
                "inactivated_plugins",
                json.dumps({"val": ["data.plugins.other.main"]}),
            ),
        )
        db.commit()
        assert PROBE["plugin_enabled"](db_path)
        db.execute(
            "UPDATE preferences SET value = ?",
            (
                json.dumps(
                    {"val": ["data.plugins.astrbot_plugin_yuuk1_core.main"]}
                ),
            ),
        )
        db.commit()
        assert not PROBE["plugin_enabled"](db_path)
