"""Read-only AstrBot v4.28.2 state probe, run inside the AstrBot container.

Only fixed boolean fields are written to stdout. Runtime config, database values,
network addresses, and credentials stay inside the process.
"""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import time
from pathlib import Path

DATA = Path("/AstrBot/data")
PLUGIN = DATA / "plugins/astrbot_plugin_yuuk1_core"
MARKER = Path("/tmp/yuuk1-core-ready.json")
ONEBOT_MARKER = Path("/tmp/yuuk1-core-onebot.json")
IDENTITY_MARKER = Path("/tmp/yuuk1-core-identity.json")
MODULE = "data.plugins.astrbot_plugin_yuuk1_core.main"


def current_marker(marker_path: Path = MARKER, proc_root: Path = Path("/proc")) -> bool:
    """Accept a marker only for a process with the same PID and start tick."""
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        pid = marker["pid"]
        # The pinned AstrBot container executes main.py as PID 1.
        if not isinstance(pid, int) or pid != 1:
            return False
        stat = (proc_root / str(pid) / "stat").read_text(encoding="utf-8")
        start_ticks = stat.rsplit(") ", 1)[1].split()[19]
        return marker["start_ticks"] == start_ticks
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return False


def current_connection_marker(
    marker_path: Path = ONEBOT_MARKER,
    proc_root: Path = Path("/proc"),
    now_ns: int | None = None,
) -> bool:
    """Read the adapter's post-handshake client registry sample while fresh."""
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        sampled = marker["sampled_monotonic_ns"]
        if type(sampled) is not int or marker["connected"] is not True:
            return False
        age_ns = (time.monotonic_ns() if now_ns is None else now_ns) - sampled
        return 0 <= age_ns <= 5_000_000_000 and current_marker(marker_path, proc_root)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def current_identity_marker(
    marker_path: Path = IDENTITY_MARKER,
    proc_root: Path = Path("/proc"),
) -> dict[str, bool | int]:
    """Return only current-process identity health booleans and a safe count."""
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if not current_marker(marker_path, proc_root):
            return {}
        count = marker.get("known_members", 0)
        if type(count) is not int or not 0 <= count <= 100_000:
            count = 0
        return {
            "identity_enabled": marker.get("identity_enabled") is True,
            "identity_persistence_enabled": marker.get("persistence_enabled") is True,
            "identity_loaded": marker.get("loaded") is True,
            "identity_healthy": marker.get("healthy") is True,
            "identity_secret_available": marker.get("secret_available") is True,
            "identity_known_members": count,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def plugin_enabled(db_path: Path = DATA / "data_v4.db") -> bool:
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2) as db:
            row = db.execute(
                "SELECT value FROM preferences WHERE scope = ? AND scope_id = ? AND key = ?",
                ("global", "global", "inactivated_plugins"),
            ).fetchone()
        disabled = json.loads(row[0]).get("val", []) if row else []
        return isinstance(disabled, list) and MODULE not in disabled
    except (OSError, sqlite3.Error, ValueError, TypeError, AttributeError):
        return False


def tcp_state(
    port: int,
    peer: str | None = None,
    tables: tuple[Path, ...] = (Path("/proc/net/tcp"), Path("/proc/net/tcp6")),
) -> tuple[bool, bool]:
    """Inspect persistent sockets, not a fresh TCP dial made by this probe."""
    listening = False
    established = False
    for path in tables:
        try:
            lines = path.read_text(encoding="ascii").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 4:
                continue
            try:
                _local_addr, local_port_hex = fields[1].split(":")
                remote_addr, _ = fields[2].split(":")
                if int(local_port_hex, 16) != port:
                    continue
                state = fields[3]
                if state == "0A":
                    listening = True
                if state != "01" or peer is None:
                    continue
                if len(remote_addr) == 8:
                    remote_ip = socket.inet_ntoa(bytes.fromhex(remote_addr)[::-1])
                    established |= remote_ip == peer
                # Linux may represent an IPv4 peer as an IPv4-mapped IPv6 socket.
                elif len(remote_addr) == 32 and remote_addr[16:24] == "0000FFFF":
                    remote_ip = socket.inet_ntoa(bytes.fromhex(remote_addr[24:])[::-1])
                    established |= remote_ip == peer
            except (ValueError, OSError):
                continue
    return listening, established


def config_state(config: dict) -> dict[str, bool]:
    models = [
        model
        for model in config.get("provider", [])
        if isinstance(model, dict)
        and model.get("id") == "deepseek/deepseek-flash"
        and model.get("model") == "deepseek-flash"
        and model.get("enable") is True
    ]
    model = models[0] if len(models) == 1 else {}
    sources = [
        source
        for source in config.get("provider_sources", [])
        if isinstance(source, dict)
        and source.get("id") == model.get("provider_source_id")
        and source.get("provider") == "deepseek"
        and source.get("type") == "openai_chat_completion"
        and source.get("enable") is True
    ]
    source = sources[0] if len(sources) == 1 else {}
    key_reference_valid = source.get("key") == ["$DEEPSEEK_API_KEY"]
    runner = config.get("agent_runner", {})
    platforms = [
        platform
        for platform in config.get("platform", [])
        if isinstance(platform, dict)
        and platform.get("type") == "aiocqhttp"
        and platform.get("enable") is True
        and platform.get("ws_reverse_port") == 6199
        and platform.get("ws_reverse_host") in ("0.0.0.0", "::")
    ]
    return {
        "runtime_key_present": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
        "source_enabled": bool(source) and config.get("provider_settings", {}).get("enable") is True,
        "key_reference_valid": key_reference_valid,
        "model_enabled": bool(model) and bool(source),
        "default_selected": (
            runner.get("runner_type") == "local"
            and runner.get("config", {}).get("model", {}).get("provider_id")
            == "deepseek/deepseek-flash"
        ),
        "adapter_enabled": bool(platforms),
    }


def main() -> None:
    result = {
        "mounted": False,
        "discovered": False,
        "enabled": False,
        "ready_current": False,
        "runtime_key_present": False,
        "source_enabled": False,
        "key_reference_valid": False,
        "model_enabled": False,
        "default_selected": False,
        "adapter_enabled": False,
        "listening": False,
        "websocket_socket": False,
        "websocket_registry_connected": False,
        "identity_enabled": False,
        "identity_persistence_enabled": False,
        "identity_loaded": False,
        "identity_healthy": False,
        "identity_secret_available": False,
        "identity_known_members": 0,
    }
    try:
        result["mounted"] = all(
            path.is_file() and path.stat().st_size > 0
            for path in (PLUGIN / "main.py", PLUGIN / "metadata.yaml")
        )
        metadata = (PLUGIN / "metadata.yaml").read_text(encoding="utf-8")
        result["discovered"] = result["mounted"] and any(
            line.strip() == "name: astrbot_plugin_yuuk1_core"
            for line in metadata.splitlines()
        )
        result["enabled"] = plugin_enabled()
        result["ready_current"] = current_marker()
        result["websocket_registry_connected"] = current_connection_marker()
        result.update(current_identity_marker())
        config = json.loads((DATA / "cmd_config.json").read_text(encoding="utf-8-sig"))
        result.update(config_state(config))
        try:
            napcat_ip = socket.gethostbyname("napcat")
        except OSError:
            napcat_ip = None
        first_listening, first_connected = tcp_state(6199, napcat_ip)
        time.sleep(0.6)
        second_listening, second_connected = tcp_state(6199, napcat_ip)
        result["listening"] = first_listening and second_listening
        result["websocket_socket"] = first_connected and second_connected
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        pass
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
