from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from plugins.astrbot_plugin_yuuk1_core.group_identity import (
    GroupIdentityStore,
    IdentityObservation,
)
from plugins.astrbot_plugin_yuuk1_core.relationship_memory import (
    DATABASE_FILENAME,
    MAX_FACT_TEXT_CHARS,
    SCHEMA_VERSION,
    RelationshipMemoryConflictError,
    RelationshipMemoryStore,
    RelationshipMemoryStoreError,
    RelationshipMemoryValidationError,
)


def _identity_observations(tmp_path: Path):
    identities = GroupIdentityStore(tmp_path / "identity")
    assert identities.initialize()
    first = identities.observe(
        platform_id="aiocqhttp",
        group_id="test-group-1",
        user_id="test-user-1",
        display_name="测试成员一",
    )
    other_member = identities.observe(
        platform_id="aiocqhttp",
        group_id="test-group-1",
        user_id="test-user-2",
        display_name="测试成员二",
    )
    other_group = identities.observe(
        platform_id="aiocqhttp",
        group_id="test-group-2",
        user_id="test-user-1",
        display_name="测试成员一",
    )
    assert first and other_member and other_group
    assert first.persisted and other_member.persisted and other_group.persisted
    return identities, first, other_member, other_group


def test_schema_initialization_is_versioned_idempotent_and_persistent(
    tmp_path: Path,
) -> None:
    _, subject, _, _ = _identity_observations(tmp_path)
    database_path = tmp_path / DATABASE_FILENAME
    store = RelationshipMemoryStore(database_path)
    store.initialize()
    initial_database = database_path.read_bytes()
    store.initialize()
    assert database_path.read_bytes() == initial_database

    created = store.create(
        subject,
        memory_type="preference",
        fact_key="tea.preference",
        fact_text="喜欢清淡的茶",
    )
    store.close()

    recovered = RelationshipMemoryStore(database_path)
    before_reopen = database_path.read_bytes()
    recovered.initialize()
    assert database_path.read_bytes() == before_reopen
    assert recovered.get(subject, created.memory_id) == created
    assert recovered.list(subject) == (created,)
    recovered.close()

    with sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    database_bytes = database_path.read_bytes()
    assert b"test-user-1" not in database_bytes
    assert b"test-group-1" not in database_bytes


def test_reads_and_writes_are_scoped_to_group_and_subject(tmp_path: Path) -> None:
    _, subject, other_member, other_group = _identity_observations(tmp_path)
    store = RelationshipMemoryStore(tmp_path / DATABASE_FILENAME)
    store.initialize()
    created = store.create(
        subject,
        memory_type="preferred_name",
        fact_key="preferred_name",
        fact_text="阿鲸",
        visibility="group_shared",
    )

    assert store.get(other_member, created.memory_id) is None
    assert store.get(other_group, created.memory_id) is None
    assert store.list(other_member) == ()
    assert store.list(other_group) == ()
    with pytest.raises(RelationshipMemoryConflictError):
        store.create(
            subject,
            memory_type="preferred_name",
            fact_key="preferred_name",
            fact_text="另一个名称",
        )
    store.close()


def test_replace_is_atomic_and_keeps_one_active_fact_revision(tmp_path: Path) -> None:
    _, subject, _, _ = _identity_observations(tmp_path)
    store = RelationshipMemoryStore(tmp_path / DATABASE_FILENAME)
    store.initialize()
    original = store.create(
        subject,
        memory_type="preference",
        fact_key="drink",
        fact_text="偏好茶",
    )

    corrected = store.replace(
        subject,
        original.memory_id,
        fact_text="偏好无糖茶",
        source_type="user_confirmed",
    )

    assert corrected.memory_id != original.memory_id
    assert corrected.revision == original.revision + 1
    assert corrected.supersedes_memory_id == original.memory_id
    assert corrected.status == "active"
    assert corrected.fact_text == "偏好无糖茶"
    assert store.get(subject, original.memory_id) is None
    assert store.get(subject, original.memory_id, include_inactive=True).status == (
        "superseded"
    )
    active = store.list(subject)
    assert active == (corrected,)
    with pytest.raises(RelationshipMemoryConflictError):
        store.create(
            subject,
            memory_type="preference",
            fact_key="drink",
            fact_text="冲突记录",
        )
    with pytest.raises(RelationshipMemoryValidationError):
        store.replace(
            subject,
            corrected.memory_id,
            fact_text="无效更正",
            source_type="unsupported",
        )
    assert store.list(subject) == (corrected,)
    store.close()


def test_delete_clears_fact_text_for_entire_revision_chain(tmp_path: Path) -> None:
    _, subject, _, _ = _identity_observations(tmp_path)
    database_path = tmp_path / DATABASE_FILENAME
    store = RelationshipMemoryStore(database_path)
    store.initialize()
    original = store.create(
        subject,
        memory_type="relationship",
        fact_key="relation.friendship",
        fact_text="已确认的虚构测试事实",
    )
    current = store.replace(
        subject,
        original.memory_id,
        fact_text="修正后的虚构测试事实",
    )

    assert store.delete(subject, current.memory_id)
    assert store.list(subject) == ()
    history = store.list(subject, include_inactive=True)
    assert len(history) == 2
    assert all(row.status == "deleted" and row.fact_text == "" for row in history)
    assert not store.delete(subject, current.memory_id)
    store.close()

    with sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT status, fact_text FROM relationship_memories"
        ).fetchall()
    assert rows == [("deleted", ""), ("deleted", "")]


def test_failed_revision_insert_rolls_back_supersede_update(tmp_path: Path) -> None:
    _, subject, _, _ = _identity_observations(tmp_path)
    database_path = tmp_path / DATABASE_FILENAME
    store = RelationshipMemoryStore(database_path)
    store.initialize()
    original = store.create(
        subject,
        memory_type="preference",
        fact_key="tea.preference",
        fact_text="偏好原茶",
    )
    with sqlite3.connect(database_path) as db:
        db.execute(
            "CREATE TRIGGER reject_test_revision BEFORE INSERT ON "
            "relationship_memories WHEN NEW.fact_text = 'force-failure' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
        )

    with pytest.raises(RelationshipMemoryStoreError):
        store.replace(
            subject,
            original.memory_id,
            fact_text="force-failure",
        )

    assert store.list(subject) == (original,)
    store.close()


def test_validation_rejects_unscoped_identity_and_oversized_facts(
    tmp_path: Path,
) -> None:
    _, subject, _, _ = _identity_observations(tmp_path)
    ephemeral = GroupIdentityStore.ephemeral()
    nonpersistent = ephemeral.observe(
        platform_id="aiocqhttp",
        group_id="test-group-3",
        user_id="test-user-3",
        display_name="测试成员三",
    )
    assert nonpersistent and not nonpersistent.persisted

    store = RelationshipMemoryStore(tmp_path / DATABASE_FILENAME)
    store.initialize()
    with pytest.raises(RelationshipMemoryValidationError):
        store.create(
            nonpersistent,
            memory_type="preference",
            fact_key="tea",
            fact_text="偏好茶",
        )
    with pytest.raises(RelationshipMemoryValidationError):
        store.create(
            subject,
            memory_type="preference",
            fact_key="tea",
            fact_text="x" * (MAX_FACT_TEXT_CHARS + 1),
        )
    with pytest.raises(RelationshipMemoryValidationError):
        store.create(
            subject,
            memory_type="unknown",
            fact_key="tea",
            fact_text="偏好茶",
        )
    with pytest.raises(RelationshipMemoryValidationError):
        store.create(
            IdentityObservation(
                group_scope_key="group_raw-id",
                member_key="member_raw-id",
                display_name="测试成员",
                first_seen=False,
                name_updated=False,
                persisted=True,
            ),
            memory_type="preference",
            fact_key="tea",
            fact_text="偏好茶",
        )
    store.close()


def test_corrupt_database_is_not_replaced(tmp_path: Path) -> None:
    database_path = tmp_path / DATABASE_FILENAME
    original = b"not a valid sqlite database"
    database_path.write_bytes(original)
    store = RelationshipMemoryStore(database_path)

    with pytest.raises(RelationshipMemoryStoreError):
        store.initialize()

    assert database_path.read_bytes() == original


def test_future_schema_is_rejected_without_modifying_database(tmp_path: Path) -> None:
    database_path = tmp_path / DATABASE_FILENAME
    with sqlite3.connect(database_path) as db:
        db.execute("PRAGMA user_version = 2")
    original = database_path.read_bytes()
    store = RelationshipMemoryStore(database_path)

    with pytest.raises(RelationshipMemoryStoreError, match="newer"):
        store.initialize()

    assert database_path.read_bytes() == original


def test_concurrent_create_keeps_only_one_active_fact(tmp_path: Path) -> None:
    _, subject, _, _ = _identity_observations(tmp_path)
    store = RelationshipMemoryStore(tmp_path / DATABASE_FILENAME)
    store.initialize()

    def create_candidate(index: int) -> bool:
        try:
            store.create(
                subject,
                memory_type="preference",
                fact_key="one-deterministic-fact",
                fact_text=f"虚构候选事实 {index}",
            )
        except RelationshipMemoryConflictError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(create_candidate, range(8)))

    assert sum(outcomes) == 1
    assert len(store.list(subject)) == 1
    store.close()
