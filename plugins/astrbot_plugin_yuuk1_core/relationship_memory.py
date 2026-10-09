"""Scoped SQLite storage primitives for future relationship-memory features.

This module deliberately provides no LLM tool, chat command, extraction, or
prompt-injection path. Callers must pass an IdentityObservation created for an
authorized current event by GroupIdentityStore.
"""

from __future__ import annotations

import os
import re
import sqlite3
import stat
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .group_identity import IdentityObservation

SCHEMA_VERSION = 1
DATABASE_FILENAME = "relationship_memory.sqlite3"
MAX_FACT_TEXT_CHARS = 1000
_MEMORY_TYPES = frozenset({"preferred_name", "preference", "relationship"})
_SOURCE_TYPES = frozenset({"manual", "user_confirmed", "owner_curated", "imported"})
_VISIBILITIES = frozenset({"subject_only", "group_shared"})
_STATUSES = frozenset({"active", "superseded", "deleted"})
_FACT_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_GROUP_KEY_RE = re.compile(r"^group_[0-9a-f]{64}$")
_MEMBER_KEY_RE = re.compile(r"^member_[0-9a-f]{64}$")


class RelationshipMemoryStoreError(RuntimeError):
    """Safe, content-free storage failure suitable for a generic log entry."""


class RelationshipMemoryValidationError(RelationshipMemoryStoreError):
    """A value or identity scope does not meet the store contract."""


class RelationshipMemoryNotFoundError(RelationshipMemoryStoreError):
    """A requested active row does not exist in the caller's identity scope."""


class RelationshipMemoryConflictError(RelationshipMemoryStoreError):
    """An active fact already exists for the deterministic fact key."""


@dataclass(frozen=True, slots=True)
class RelationshipMemory:
    memory_id: str
    group_key: str
    subject_member_key: str
    memory_type: str
    fact_key: str
    fact_text: str
    source_type: str
    visibility: str
    status: str
    created_at: float
    updated_at: float
    revision: int
    supersedes_memory_id: str | None


class RelationshipMemoryStore:
    """A small, transactional store scoped to Group Identity HMAC keys."""

    def __init__(self, database_path: Path | str, *, timeout_seconds: float = 5.0):
        self.database_path = Path(database_path)
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self._lock = threading.RLock()
        self._initialized = False
        self._closed = False

    @property
    def initialized(self) -> bool:
        return self._initialized and not self._closed

    def initialize(self) -> None:
        """Create a new schema or verify an existing database without migration."""
        with self._lock:
            self._ensure_open()
            if self._initialized:
                return
            try:
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
                if self.database_path.exists():
                    self._verify_existing_database()
                else:
                    self._secure_data_directory()
                    self._create_database_if_still_new()
                self._secure_storage_permissions()
                self._initialized = True
            except RelationshipMemoryStoreError:
                raise
            except (OSError, sqlite3.Error, ValueError) as exc:
                raise self._safe_storage_error(exc) from None

    def _create_database_if_still_new(self) -> None:
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            user_objects = connection.execute(
                "SELECT count(*) FROM sqlite_master "
                "WHERE type IN ('table', 'index', 'trigger', 'view') "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
            if version != 0 or user_objects:
                connection.rollback()
                self._verify_existing_database()
                return
            self._create_schema(connection)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE relationship_memories (
                memory_id TEXT PRIMARY KEY,
                group_key TEXT NOT NULL,
                subject_member_key TEXT NOT NULL,
                memory_type TEXT NOT NULL CHECK (
                    memory_type IN ('preferred_name', 'preference', 'relationship')
                ),
                fact_key TEXT NOT NULL,
                fact_text TEXT NOT NULL CHECK (length(fact_text) <= 1000),
                source_type TEXT NOT NULL CHECK (
                    source_type IN ('manual', 'user_confirmed', 'owner_curated', 'imported')
                ),
                visibility TEXT NOT NULL CHECK (
                    visibility IN ('subject_only', 'group_shared')
                ),
                status TEXT NOT NULL CHECK (
                    status IN ('active', 'superseded', 'deleted')
                ),
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                revision INTEGER NOT NULL CHECK (revision > 0),
                supersedes_memory_id TEXT,
                FOREIGN KEY (supersedes_memory_id)
                    REFERENCES relationship_memories(memory_id)
            )
            """
        )
        connection.execute(
            "CREATE UNIQUE INDEX relationship_memory_active_fact "
            "ON relationship_memories "
            "(group_key, subject_member_key, memory_type, fact_key) "
            "WHERE status = 'active'"
        )
        connection.execute(
            "CREATE INDEX relationship_memory_scope "
            "ON relationship_memories (group_key, subject_member_key, status)"
        )

    def _verify_existing_database(self) -> None:
        uri = self.database_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(
            uri, uri=True, timeout=self.timeout_seconds, isolation_level=None
        )
        try:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise RelationshipMemoryStoreError(
                    "relationship memory database schema is newer than this plugin"
                )
            if version != SCHEMA_VERSION:
                raise RelationshipMemoryStoreError(
                    "relationship memory database schema is unsupported"
                )
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise RelationshipMemoryStoreError(
                    "relationship memory database integrity check failed"
                )
            connection.execute(
                "SELECT memory_id, group_key, subject_member_key, memory_type, "
                "fact_key, fact_text, source_type, visibility, status, created_at, "
                "updated_at, revision, supersedes_memory_id "
                "FROM relationship_memories LIMIT 0"
            )
            indexes = {
                row[1]: (bool(row[2]), row[4])
                for row in connection.execute(
                    "PRAGMA index_list('relationship_memories')"
                )
            }
            if indexes.get("relationship_memory_active_fact") != (
                True,
                True,
            ):
                raise RelationshipMemoryStoreError(
                    "relationship memory database constraints are incomplete"
                )
        except RelationshipMemoryStoreError:
            raise
        except sqlite3.Error as exc:
            raise self._safe_storage_error(exc) from None
        finally:
            connection.close()

    @contextmanager
    def _connection(self, *, write: bool) -> Iterator[sqlite3.Connection]:
        self._ensure_ready()
        if write:
            connection = sqlite3.connect(
                str(self.database_path),
                timeout=self.timeout_seconds,
                isolation_level=None,
            )
        else:
            uri = self.database_path.resolve().as_uri() + "?mode=ro"
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=self.timeout_seconds,
                isolation_level=None,
            )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            if write:
                connection.execute("PRAGMA secure_delete = ON")
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except RelationshipMemoryStoreError:
            if write and connection.in_transaction:
                connection.rollback()
            raise
        except sqlite3.Error as exc:
            if write and connection.in_transaction:
                connection.rollback()
            raise self._safe_storage_error(exc) from None
        except Exception:
            if write and connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def create(
        self,
        subject: IdentityObservation,
        *,
        memory_type: str,
        fact_key: str,
        fact_text: str,
        source_type: str = "manual",
        visibility: str = "subject_only",
    ) -> RelationshipMemory:
        group_key, member_key = self._scope(subject)
        memory_type = self._choice(memory_type, _MEMORY_TYPES, "memory_type")
        fact_key = self._fact_key(fact_key)
        fact_text = self._fact_text(fact_text)
        source_type = self._choice(source_type, _SOURCE_TYPES, "source_type")
        visibility = self._choice(visibility, _VISIBILITIES, "visibility")
        memory_id = str(uuid.uuid4())
        timestamp = time.time()
        with self._lock, self._connection(write=True) as connection:
            existing = connection.execute(
                "SELECT 1 FROM relationship_memories WHERE group_key = ? "
                "AND subject_member_key = ? AND memory_type = ? AND fact_key = ? "
                "AND status = 'active' LIMIT 1",
                (group_key, member_key, memory_type, fact_key),
            ).fetchone()
            if existing:
                raise RelationshipMemoryConflictError(
                    "an active memory already exists for this fact key"
                )
            connection.execute(
                "INSERT INTO relationship_memories "
                "(memory_id, group_key, subject_member_key, memory_type, fact_key, "
                "fact_text, source_type, visibility, status, created_at, updated_at, "
                "revision, supersedes_memory_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 1, NULL)",
                (
                    memory_id,
                    group_key,
                    member_key,
                    memory_type,
                    fact_key,
                    fact_text,
                    source_type,
                    visibility,
                    timestamp,
                    timestamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM relationship_memories WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
        return self._from_row(row)

    def get(
        self,
        subject: IdentityObservation,
        memory_id: str,
        *,
        include_inactive: bool = False,
    ) -> RelationshipMemory | None:
        group_key, member_key = self._scope(subject)
        memory_id = self._memory_id(memory_id)
        status_clause = "" if include_inactive else " AND status = 'active'"
        with self._lock, self._connection(write=False) as connection:
            row = connection.execute(
                "SELECT * FROM relationship_memories WHERE memory_id = ? "
                "AND group_key = ? AND subject_member_key = ?" + status_clause,
                (memory_id, group_key, member_key),
            ).fetchone()
        return self._from_row(row) if row else None

    def list(
        self,
        subject: IdentityObservation,
        *,
        include_inactive: bool = False,
    ) -> tuple[RelationshipMemory, ...]:
        group_key, member_key = self._scope(subject)
        status_clause = "" if include_inactive else " AND status = 'active'"
        with self._lock, self._connection(write=False) as connection:
            rows = connection.execute(
                "SELECT * FROM relationship_memories WHERE group_key = ? "
                "AND subject_member_key = ?" + status_clause +
                " ORDER BY created_at, memory_id",
                (group_key, member_key),
            ).fetchall()
        return tuple(self._from_row(row) for row in rows)

    def replace(
        self,
        subject: IdentityObservation,
        memory_id: str,
        *,
        fact_text: str,
        source_type: str | None = None,
        visibility: str | None = None,
    ) -> RelationshipMemory:
        """Create a new revision and supersede the active scoped record."""
        group_key, member_key = self._scope(subject)
        memory_id = self._memory_id(memory_id)
        fact_text = self._fact_text(fact_text)
        timestamp = time.time()
        new_memory_id = str(uuid.uuid4())
        with self._lock, self._connection(write=True) as connection:
            old = connection.execute(
                "SELECT * FROM relationship_memories WHERE memory_id = ? "
                "AND group_key = ? AND subject_member_key = ? AND status = 'active'",
                (memory_id, group_key, member_key),
            ).fetchone()
            if old is None:
                raise RelationshipMemoryNotFoundError(
                    "active memory was not found in this identity scope"
                )
            next_source = self._choice(
                source_type if source_type is not None else old["source_type"],
                _SOURCE_TYPES,
                "source_type",
            )
            next_visibility = self._choice(
                visibility if visibility is not None else old["visibility"],
                _VISIBILITIES,
                "visibility",
            )
            connection.execute(
                "UPDATE relationship_memories SET status = 'superseded', "
                "updated_at = ? WHERE memory_id = ? AND group_key = ? "
                "AND subject_member_key = ? AND status = 'active'",
                (timestamp, memory_id, group_key, member_key),
            )
            connection.execute(
                "INSERT INTO relationship_memories "
                "(memory_id, group_key, subject_member_key, memory_type, fact_key, "
                "fact_text, source_type, visibility, status, created_at, updated_at, "
                "revision, supersedes_memory_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)",
                (
                    new_memory_id,
                    group_key,
                    member_key,
                    old["memory_type"],
                    old["fact_key"],
                    fact_text,
                    next_source,
                    next_visibility,
                    timestamp,
                    timestamp,
                    int(old["revision"]) + 1,
                    memory_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM relationship_memories WHERE memory_id = ?",
                (new_memory_id,),
            ).fetchone()
        return self._from_row(row)

    def delete(self, subject: IdentityObservation, memory_id: str) -> bool:
        """Tombstone one logical fact and clear every stored revision body."""
        group_key, member_key = self._scope(subject)
        memory_id = self._memory_id(memory_id)
        timestamp = time.time()
        with self._lock, self._connection(write=True) as connection:
            row = connection.execute(
                "SELECT memory_type, fact_key FROM relationship_memories "
                "WHERE memory_id = ? AND group_key = ? AND subject_member_key = ? "
                "AND status != 'deleted'",
                (memory_id, group_key, member_key),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "UPDATE relationship_memories SET status = 'deleted', fact_text = '', "
                "updated_at = ? WHERE group_key = ? "
                "AND subject_member_key = ? AND memory_type = ? AND fact_key = ?",
                (timestamp, group_key, member_key, row["memory_type"], row["fact_key"]),
            )
        return True

    def close(self) -> None:
        """Prevent later operations; connections are short-lived per operation."""
        with self._lock:
            self._closed = True
            self._initialized = False

    def _secure_storage_permissions(self) -> None:
        """Restrict the plugin data directory and database on POSIX hosts."""
        if os.name == "nt":
            return
        self._secure_data_directory()
        file_mode = stat.S_IMODE(self.database_path.stat().st_mode)
        if file_mode & 0o077:
            self.database_path.chmod(0o600)

    def _secure_data_directory(self) -> None:
        if os.name == "nt":
            return
        directory_mode = stat.S_IMODE(self.database_path.parent.stat().st_mode)
        if directory_mode & 0o077:
            self.database_path.parent.chmod(0o700)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RelationshipMemoryStoreError("relationship memory store is closed")

    def _ensure_ready(self) -> None:
        self._ensure_open()
        if not self._initialized:
            raise RelationshipMemoryStoreError("relationship memory store is unavailable")

    @staticmethod
    def _scope(subject: IdentityObservation) -> tuple[str, str]:
        if not isinstance(subject, IdentityObservation) or not subject.persisted:
            raise RelationshipMemoryValidationError(
                "a persisted Group Identity observation is required"
            )
        group_key = subject.group_scope_key
        member_key = subject.member_key
        if not _GROUP_KEY_RE.fullmatch(group_key) or not _MEMBER_KEY_RE.fullmatch(
            member_key
        ):
            raise RelationshipMemoryValidationError("identity scope is invalid")
        return group_key, member_key

    @staticmethod
    def _choice(value: object, choices: frozenset[str], field: str) -> str:
        if not isinstance(value, str) or value not in choices:
            raise RelationshipMemoryValidationError(f"{field} is unsupported")
        return value

    @staticmethod
    def _fact_key(value: object) -> str:
        if not isinstance(value, str):
            raise RelationshipMemoryValidationError("fact_key is invalid")
        normalized = value.strip()
        if not _FACT_KEY_RE.fullmatch(normalized):
            raise RelationshipMemoryValidationError("fact_key is invalid")
        return normalized

    @staticmethod
    def _fact_text(value: object) -> str:
        if not isinstance(value, str):
            raise RelationshipMemoryValidationError("fact_text is invalid")
        normalized = value.strip()
        if not normalized or len(normalized) > MAX_FACT_TEXT_CHARS:
            raise RelationshipMemoryValidationError("fact_text length is invalid")
        return normalized

    @staticmethod
    def _memory_id(value: object) -> str:
        if not isinstance(value, str):
            raise RelationshipMemoryValidationError("memory_id is invalid")
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError, TypeError):
            raise RelationshipMemoryValidationError("memory_id is invalid") from None

    @staticmethod
    def _from_row(row: sqlite3.Row) -> RelationshipMemory:
        return RelationshipMemory(
            memory_id=row["memory_id"],
            group_key=row["group_key"],
            subject_member_key=row["subject_member_key"],
            memory_type=row["memory_type"],
            fact_key=row["fact_key"],
            fact_text=row["fact_text"],
            source_type=row["source_type"],
            visibility=row["visibility"],
            status=row["status"],
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            revision=int(row["revision"]),
            supersedes_memory_id=row["supersedes_memory_id"],
        )

    @staticmethod
    def _safe_storage_error(exc: Exception) -> RelationshipMemoryStoreError:
        if isinstance(exc, sqlite3.DatabaseError):
            return RelationshipMemoryStoreError(
                "relationship memory database operation failed"
            )
        return RelationshipMemoryStoreError(
            "relationship memory storage is unavailable"
        )
