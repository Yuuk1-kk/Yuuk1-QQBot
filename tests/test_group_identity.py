from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from plugins.astrbot_plugin_yuuk1_core.group_identity import (
    GroupIdentityStore,
    sanitize_display_name,
)


def test_identity_secret_is_not_exposed_in_webui_schema() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "plugins/astrbot_plugin_yuuk1_core/_conf_schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert "identity_secret" not in schema
    assert "group_identity_enabled" in schema
    assert "group_identity_persistence_enabled" in schema


def test_identity_scope_and_member_keys_are_stable_and_group_scoped(tmp_path: Path) -> None:
    store = GroupIdentityStore(tmp_path)
    assert store.initialize()

    first = store.observe(
        platform_id="aiocqhttp",
        group_id="group-private-1001",
        user_id="user-private-2002",
        display_name="奶龙鉴赏家",
        now=100,
    )
    assert first is not None
    store.flush()

    recovered = GroupIdentityStore(tmp_path)
    assert recovered.initialize()
    after_restart = recovered.observe(
        platform_id="aiocqhttp",
        group_id="group-private-1001",
        user_id="user-private-2002",
        display_name="",
        now=200,
    )
    assert after_restart is not None
    assert after_restart.member_key == first.member_key
    assert after_restart.group_scope_key == first.group_scope_key
    assert after_restart.display_name == "奶龙鉴赏家"
    assert recovered.member_key_for("aiocqhttp", "other-group", "user-private-2002") != first.member_key
    assert recovered.member_key_for("aiocqhttp", "group-private-1001", "other-user") != first.member_key


def test_name_rename_alias_deduplication_and_limit_survive_reload(tmp_path: Path) -> None:
    store = GroupIdentityStore(tmp_path, max_aliases=3)
    assert store.initialize()

    def observe(name: str, now: int):
        return store.observe(
            platform_id="aiocqhttp",
            group_id="private-group-id",
            user_id="private-user-id",
            display_name=name,
            now=now,
        )

    first = observe("  奶龙鉴赏家  ", 1)
    assert first is not None and first.display_name == "奶龙鉴赏家"
    assert observe("奶龙鉴赏家", 2).name_updated is False
    observe("Yuuk1", 3)
    observe("Whale", 4)
    observe("Jingjing", 5)
    observe("鲸鲸", 6)
    store.flush()

    recovered = GroupIdentityStore(tmp_path, max_aliases=3)
    assert recovered.initialize()
    updated = recovered.observe(
        platform_id="aiocqhttp",
        group_id="private-group-id",
        user_id="private-user-id",
        display_name="",
        now=7,
    )
    assert updated is not None
    assert updated.display_name == "鲸鲸"
    assert recovered.aliases_for(updated.group_scope_key, updated.member_key) == ("Yuuk1", "Whale", "Jingjing")
    assert recovered.aliases_for(updated.group_scope_key, updated.member_key) == ("Yuuk1", "Whale", "Jingjing")
    aliases = recovered.aliases_for(updated.group_scope_key, updated.member_key)
    assert len(aliases) == 3
    assert "奶龙鉴赏家" not in aliases
    assert len({alias.casefold() for alias in aliases}) == 3


def test_persisted_files_contain_only_hmac_keys_and_safe_name_metadata(tmp_path: Path) -> None:
    raw_group = "raw-group-775533"
    raw_user = "raw-user-991177"
    store = GroupIdentityStore(tmp_path)
    assert store.initialize()
    observation = store.observe(
        platform_id="aiocqhttp",
        group_id=raw_group,
        user_id=raw_user,
        display_name=raw_user,
        now=123,
    )
    assert observation is not None
    assert observation.display_name == "群友"
    assert store.flush()

    secret_path = tmp_path / "identity_secret"
    store_path = tmp_path / "group_identity.json"
    secret = secret_path.read_text(encoding="ascii").strip()
    persisted = store_path.read_text(encoding="utf-8")
    parsed = json.loads(persisted)
    assert len(secret) == 64
    assert raw_group not in persisted and raw_group not in secret
    assert raw_user not in persisted and raw_user not in secret
    assert observation.group_scope_key in parsed["groups"]
    assert observation.member_key in parsed["groups"][observation.group_scope_key]["members"]
    assert secret not in persisted
    assert parsed["groups"][observation.group_scope_key]["members"][observation.member_key] == {
        "current_name": "",
        "aliases": [],
        "first_seen_at": 123.0,
        "last_seen_at": 123.0,
    }
    if os.name != "nt":
        assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(store_path.stat().st_mode) == 0o600


def test_aliases_are_bounded_and_names_are_sanitized() -> None:
    assert sanitize_display_name("  A\n[B]\u200b ", limit=20) == "A ［B］"
    assert sanitize_display_name("987654321", forbidden_values=("987654321",)) == ""
    assert sanitize_display_name("123456789") == ""
    assert sanitize_display_name("玩家123456789") == "玩家"
    assert sanitize_display_name("x" * 100, limit=12) == "x" * 12


def test_missing_secret_with_existing_store_never_generates_replacement(tmp_path: Path) -> None:
    store = GroupIdentityStore(tmp_path)
    assert store.initialize()
    store.observe(
        platform_id="aiocqhttp",
        group_id="persisted-group",
        user_id="persisted-user",
        display_name="鲸鲸群友",
        now=1,
    )
    assert store.flush()
    original_store = (tmp_path / "group_identity.json").read_bytes()
    (tmp_path / "identity_secret").unlink()

    recovered = GroupIdentityStore(tmp_path)
    assert not recovered.initialize()
    assert not (tmp_path / "identity_secret").exists()
    assert (tmp_path / "group_identity.json").read_bytes() == original_store
    status = recovered.status()
    assert status["secret_available"] is False
    assert status["healthy"] is False
    assert status["reason"] == "secret_missing_with_store"


def test_invalid_store_is_not_overwritten_and_group_capacity_is_bounded(tmp_path: Path) -> None:
    store = GroupIdentityStore(tmp_path, max_members_per_group=1)
    assert store.initialize()
    first = store.observe(
        platform_id="aiocqhttp",
        group_id="bounded-group",
        user_id="first-user",
        display_name="甲",
        now=1,
    )
    second = store.observe(
        platform_id="aiocqhttp",
        group_id="bounded-group",
        user_id="second-user",
        display_name="乙",
        now=2,
    )
    assert first is not None and second is not None
    assert second.persisted is False
    assert store.known_member_count() == 1
    assert store.flush()

    store_path = tmp_path / "group_identity.json"
    store_path.write_text("{invalid", encoding="utf-8")
    original = store_path.read_bytes()
    recovered = GroupIdentityStore(tmp_path)
    assert not recovered.initialize()
    assert store_path.read_bytes() == original
    assert recovered.status()["reason"] == "store_invalid"


def test_secret_and_store_are_stable_across_reload(tmp_path: Path) -> None:
    first = GroupIdentityStore(tmp_path)
    assert first.initialize()
    observation = first.observe(
        platform_id="aiocqhttp",
        group_id="group",
        user_id="user",
        display_name="旧名",
        now=10,
    )
    assert observation is not None
    first.flush()
    original_secret = (tmp_path / "identity_secret").read_text(encoding="ascii")

    second = GroupIdentityStore(tmp_path)
    assert second.initialize()
    assert (tmp_path / "identity_secret").read_text(encoding="ascii") == original_secret
    restored = second.observe(
        platform_id="aiocqhttp",
        group_id="group",
        user_id="user",
        display_name="新名",
        now=20,
    )
    assert restored is not None
    assert restored.member_key == observation.member_key
    assert second.aliases_for(restored.group_scope_key, restored.member_key) == ("旧名",)
