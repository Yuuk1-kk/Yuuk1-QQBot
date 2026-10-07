"""Private, bounded per-group member identity storage for Jingjing context."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
import stat
import tempfile
import threading
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

IDENTITY_SECRET_FILENAME = "identity_secret"
IDENTITY_STORE_FILENAME = "group_identity.json"
IDENTITY_SCHEMA_VERSION = 1
MAX_IDENTITY_GROUPS = 200
MAX_IDENTITY_MEMBERS_PER_GROUP = 500
MAX_IDENTITY_ALIASES = 5
MAX_DISPLAY_NAME_CHARS = 64
MAX_IDENTITY_STORE_BYTES = 64 * 1024 * 1024
_PRIVATE_UNICODE_CATEGORIES = {"Cc", "Cf", "Cs", "Zl", "Zp"}


def _bounded_int(value: object, default: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(max(number, 0), maximum)


def sanitize_display_name(
    value: object,
    *,
    forbidden_values: tuple[object, ...] = (),
    limit: int = MAX_DISPLAY_NAME_CHARS,
) -> str:
    """Bound names and remove controls / formatting delimiters before prompting."""
    if not isinstance(value, str):
        return ""
    raw_normalized = " ".join(value.split())
    forbidden = {str(item or "").strip() for item in forbidden_values}
    text = "".join(
        " "
        if unicodedata.category(character) in {"Cc", "Zl", "Zp"}
        and character.isspace()
        else ""
        if unicodedata.category(character) in _PRIVATE_UNICODE_CATEGORIES
        else character
        for character in value
    )
    text = re.sub(r"(?<!\d)\d{5,20}(?!\d)", "", text)
    text = " ".join(text.split()).replace("[", "［").replace("]", "］")
    if not text or raw_normalized in forbidden or text in forbidden:
        return ""
    return text[: max(1, limit)].strip()


def normalize_display_name(value: object) -> str:
    """Return a comparison-only form for alias and collision checks."""
    return " ".join(sanitize_display_name(value).split()).casefold()


def _timestamp(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if math.isfinite(parsed) and parsed >= 0 else default


def _valid_digest_key(value: object, prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    digest = value[len(prefix) :]
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


@dataclass(frozen=True, slots=True)
class IdentityObservation:
    """Safe identity output for one observed, allowed group sender."""

    group_scope_key: str
    member_key: str
    display_name: str
    first_seen: bool
    name_updated: bool
    persisted: bool


@dataclass(slots=True)
class _MemberRecord:
    current_name: str
    aliases: list[str]
    first_seen_at: float
    last_seen_at: float


class GroupIdentityStore:
    """Store HMAC-scoped member names without persisting QQ or group IDs."""

    def __init__(
        self,
        data_dir: Path | str | None,
        *,
        enabled: bool = True,
        persistence_enabled: bool = True,
        max_aliases: int = MAX_IDENTITY_ALIASES,
        max_members_per_group: int = MAX_IDENTITY_MEMBERS_PER_GROUP,
        max_groups: int = MAX_IDENTITY_GROUPS,
    ) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else None
        self.enabled = bool(enabled)
        self.persistence_enabled = bool(persistence_enabled)
        self.max_aliases = _bounded_int(max_aliases, 5, MAX_IDENTITY_ALIASES)
        self.max_members_per_group = max(
            1, _bounded_int(max_members_per_group, 500, MAX_IDENTITY_MEMBERS_PER_GROUP)
        )
        self.max_groups = max(1, _bounded_int(max_groups, 200, MAX_IDENTITY_GROUPS))
        self._lock = threading.RLock()
        self._secret = secrets.token_bytes(32)
        self._groups: OrderedDict[str, OrderedDict[str, _MemberRecord]] = OrderedDict()
        self._dirty = False
        self._generation = 0
        self._loaded = False
        self._healthy = False
        self._secret_available = False
        self._persistent_ready = False
        self._degraded_reason = "not_initialized"

    @classmethod
    def ephemeral(
        cls,
        *,
        enabled: bool = True,
        max_aliases: int = MAX_IDENTITY_ALIASES,
        max_members_per_group: int = MAX_IDENTITY_MEMBERS_PER_GROUP,
    ) -> GroupIdentityStore:
        """Create an in-memory fallback which never reads or writes a data file."""
        store = cls(
            None,
            enabled=enabled,
            persistence_enabled=False,
            max_aliases=max_aliases,
            max_members_per_group=max_members_per_group,
        )
        store._loaded = True
        store._healthy = True
        store._degraded_reason = "persistence_disabled"
        return store

    @property
    def secret_path(self) -> Path | None:
        return self.data_dir / IDENTITY_SECRET_FILENAME if self.data_dir else None

    @property
    def store_path(self) -> Path | None:
        return self.data_dir / IDENTITY_STORE_FILENAME if self.data_dir else None

    def initialize(self) -> bool:
        """Load durable data or establish a new secret only for an empty store."""
        with self._lock:
            if self._loaded:
                return self._healthy
            if not self.enabled:
                self._loaded = True
                self._healthy = True
                self._degraded_reason = "feature_disabled"
                return True
            if not self.persistence_enabled:
                self._loaded = True
                self._healthy = True
                self._degraded_reason = "persistence_disabled"
                return True
            if self.data_dir is None:
                return self._degrade("data_dir_unavailable")

            try:
                self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                self._secure_directory_permissions()
                secret_path = self.data_dir / IDENTITY_SECRET_FILENAME
                store_path = self.data_dir / IDENTITY_STORE_FILENAME
                if secret_path.exists():
                    secret = self._read_secret(secret_path)
                elif store_path.exists():
                    # Without the original HMAC key the persisted member keys
                    # cannot be mapped. Never create a replacement silently.
                    return self._degrade("secret_missing_with_store")
                else:
                    secret = self._create_secret(secret_path)
                self._secret = secret
                self._secret_available = True
                if store_path.exists():
                    self._load_store(store_path)
                self._persistent_ready = True
                self._healthy = True
                self._loaded = True
                self._degraded_reason = ""
                return True
            except (OSError, ValueError, TypeError, json.JSONDecodeError, UnicodeError) as exc:
                reason = self._safe_failure_reason(exc)
                return self._degrade(reason)

    def _degrade(self, reason: str) -> bool:
        self._healthy = False
        self._loaded = True
        self._persistent_ready = False
        self._degraded_reason = reason
        self._groups.clear()
        return False

    @staticmethod
    def _safe_failure_reason(exc: Exception) -> str:
        if isinstance(exc, PermissionError):
            return "permission_denied"
        if isinstance(exc, json.JSONDecodeError):
            return "store_invalid"
        if isinstance(exc, UnicodeError):
            return "invalid_encoding"
        if isinstance(exc, ValueError):
            return "invalid_data"
        return "storage_error"

    def _secure_directory_permissions(self) -> None:
        if os.name == "nt" or self.data_dir is None:
            return
        os.chmod(self.data_dir, 0o700)
        if stat.S_IMODE(self.data_dir.stat().st_mode) & 0o077:
            raise PermissionError("private directory permissions unavailable")

    @staticmethod
    def _secure_file_permissions(path: Path) -> None:
        if os.name == "nt":
            return
        os.chmod(path, 0o600)
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PermissionError("private file permissions unavailable")

    def _read_secret(self, path: Path) -> bytes:
        data = path.read_text(encoding="ascii").strip()
        if len(data) != 64:
            raise ValueError("invalid identity secret")
        secret = bytes.fromhex(data)
        if len(secret) != 32:
            raise ValueError("invalid identity secret")
        self._secure_file_permissions(path)
        return secret

    def _create_secret(self, path: Path) -> bytes:
        secret = secrets.token_bytes(32)
        encoded = secret.hex() + "\n"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as target:
            target.write(encoded)
            target.flush()
            os.fsync(target.fileno())
        self._secure_file_permissions(path)
        return secret

    def _load_store(self, path: Path) -> None:
        size = path.stat().st_size
        if size > MAX_IDENTITY_STORE_BYTES:
            raise ValueError("identity store too large")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != IDENTITY_SCHEMA_VERSION:
            raise ValueError("unsupported identity store")
        groups = raw.get("groups")
        if not isinstance(groups, dict) or len(groups) > self.max_groups:
            raise ValueError("invalid identity groups")
        loaded: OrderedDict[str, OrderedDict[str, _MemberRecord]] = OrderedDict()
        for scope_key, group_data in groups.items():
            if not _valid_digest_key(scope_key, "group_") or not isinstance(group_data, dict):
                raise ValueError("invalid identity group key")
            members_data = group_data.get("members")
            if not isinstance(members_data, dict) or len(members_data) > self.max_members_per_group:
                raise ValueError("invalid identity member list")
            members: OrderedDict[str, _MemberRecord] = OrderedDict()
            for member_key, member_data in members_data.items():
                if not _valid_digest_key(member_key, "member_") or not isinstance(member_data, dict):
                    raise ValueError("invalid identity member key")
                current_name = sanitize_display_name(member_data.get("current_name"))
                aliases_value = member_data.get("aliases", [])
                if not isinstance(aliases_value, list):
                    raise ValueError("invalid identity aliases")
                aliases = self._clean_aliases(aliases_value, current_name)
                now = time.time()
                members[member_key] = _MemberRecord(
                    current_name=current_name,
                    aliases=aliases,
                    first_seen_at=_timestamp(member_data.get("first_seen_at"), now),
                    last_seen_at=_timestamp(member_data.get("last_seen_at"), now),
                )
            loaded[scope_key] = members
        self._groups = loaded

    def _clean_aliases(self, values: list[object], current_name: str) -> list[str]:
        current_normalized = normalize_display_name(current_name)
        result: list[str] = []
        seen = {current_normalized} if current_normalized else set()
        for value in values:
            alias = sanitize_display_name(value)
            normalized = normalize_display_name(alias)
            if not alias or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(alias)
        return result[-self.max_aliases :] if self.max_aliases else []

    def _digest(self, domain: bytes, *parts: object) -> str:
        payload = b"\0".join(
            [domain, *(str(part or "").strip().encode("utf-8") for part in parts)]
        )
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def group_scope_key(self, platform_id: object, group_id: object) -> str:
        return "group_" + self._digest(
            b"yuuk1-group-scope-v1", platform_id, group_id
        )

    def member_key_for(
        self, platform_id: object, group_id: object, user_id: object
    ) -> str:
        return "member_" + self._digest(
            b"yuuk1-group-member-v1", platform_id, group_id, user_id
        )

    def observe(
        self,
        *,
        platform_id: object,
        group_id: object,
        user_id: object,
        display_name: object,
        now: float | None = None,
    ) -> IdentityObservation | None:
        """Update identity metadata for one allowed, non-bot group sender."""
        platform = str(platform_id or "").strip()
        group = str(group_id or "").strip()
        user = str(user_id or "").strip()
        if not self.enabled or not platform or not group or not user:
            return None
        timestamp = time.time() if now is None else float(now)
        safe_name = sanitize_display_name(
            display_name,
            forbidden_values=(group, user),
        )
        scope_key = self.group_scope_key(platform, group)
        member_key = self.member_key_for(platform, group, user)
        persisted = bool(self._persistent_ready)
        with self._lock:
            members = self._groups.get(scope_key)
            first_seen = False
            name_updated = False
            if members is None:
                if len(self._groups) >= self.max_groups:
                    return IdentityObservation(
                        scope_key,
                        member_key,
                        safe_name or "群友",
                        False,
                        False,
                        False,
                    )
                members = OrderedDict()
                self._groups[scope_key] = members
            record = members.get(member_key)
            if record is None:
                if len(members) >= self.max_members_per_group:
                    return IdentityObservation(
                        scope_key,
                        member_key,
                        safe_name or "群友",
                        False,
                        False,
                        False,
                    )
                record = _MemberRecord(
                    current_name=safe_name,
                    aliases=[],
                    first_seen_at=timestamp,
                    last_seen_at=timestamp,
                )
                members[member_key] = record
                first_seen = True
                name_updated = bool(safe_name)
            else:
                if safe_name:
                    old_name = record.current_name
                    old_normalized = normalize_display_name(old_name)
                    new_normalized = normalize_display_name(safe_name)
                    if new_normalized and new_normalized != old_normalized:
                        if old_name and old_normalized:
                            aliases = self._clean_aliases(
                                [*record.aliases, old_name], safe_name
                            )
                            record.aliases = aliases
                        record.current_name = safe_name
                        name_updated = True
                record.last_seen_at = timestamp
            if persisted:
                self._dirty = True
                self._generation += 1
            return IdentityObservation(
                group_scope_key=scope_key,
                member_key=member_key,
                display_name=record.current_name or safe_name or "群友",
                first_seen=first_seen,
                name_updated=name_updated,
                persisted=persisted,
            )

    def aliases_for(self, group_scope_key: str, member_key: str) -> tuple[str, ...]:
        with self._lock:
            record = self._groups.get(group_scope_key, {}).get(member_key)
            return tuple(record.aliases) if record else ()

    def name_is_ambiguous(
        self, group_scope_key: str, member_key: str, display_name: str
    ) -> bool:
        normalized = normalize_display_name(display_name)
        if not normalized:
            return False
        with self._lock:
            members = self._groups.get(group_scope_key, {})
            return sum(
                normalize_display_name(record.current_name) == normalized
                for key, record in members.items()
                if key != member_key
            ) > 0

    def known_member_count(self) -> int:
        with self._lock:
            return sum(len(members) for members in self._groups.values())

    def known_group_count(self) -> int:
        with self._lock:
            return len(self._groups)

    def status(self) -> dict[str, Any]:
        """Return safe health metadata with no names, keys, or secret material."""
        return {
            "enabled": self.enabled,
            "persistence_enabled": self.persistence_enabled,
            "secret_available": self._secret_available,
            "loaded": self._loaded,
            "healthy": self._healthy,
            "known_members": self.known_member_count(),
            "known_groups": self.known_group_count(),
            "reason": self._degraded_reason,
        }

    @property
    def dirty(self) -> bool:
        return self._dirty

    def flush(self) -> bool:
        """Atomically write one batched snapshot; never fsync per incoming message."""
        if not self.enabled or not self.persistence_enabled:
            return True
        if not self._persistent_ready or self.data_dir is None or self.store_path is None:
            return False
        with self._lock:
            if not self._dirty:
                return self._healthy
            generation = self._generation
            snapshot = {
                "schema_version": IDENTITY_SCHEMA_VERSION,
                "groups": {
                    scope_key: {
                        "members": {
                            member_key: {
                                "current_name": record.current_name,
                                "aliases": list(record.aliases),
                                "first_seen_at": record.first_seen_at,
                                "last_seen_at": record.last_seen_at,
                            }
                            for member_key, record in members.items()
                        }
                    }
                    for scope_key, members in self._groups.items()
                },
            }
        temporary_path: Path | None = None
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=".group_identity-",
                suffix=".tmp",
                dir=self.data_dir,
                delete=False,
            ) as target:
                temporary_path = Path(target.name)
                if os.name != "nt":
                    os.chmod(temporary_path, 0o600)
                json.dump(snapshot, target, ensure_ascii=False, separators=(",", ":"))
                target.write("\n")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary_path, self.store_path)
            self._secure_file_permissions(self.store_path)
            if os.name != "nt":
                directory_fd = os.open(self.data_dir, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            with self._lock:
                if self._generation == generation:
                    self._dirty = False
                self._healthy = True
                self._degraded_reason = ""
            return True
        except (OSError, TypeError, ValueError, UnicodeError):
            with self._lock:
                self._healthy = False
                self._degraded_reason = "store_write_failed"
            return False
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
