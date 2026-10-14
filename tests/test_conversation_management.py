"""Conversation selection tests using synthetic AstrBot manager state only."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass

from plugins.astrbot_plugin_yuuk1_core.conversation_management import (
    ConversationTargetError,
    create_scoped_conversation,
    page_scoped_conversations,
    resolve_scoped_target,
    switch_scoped_conversation,
)

GROUP = "aiocqhttp:GroupMessage:12345"
OTHER_GROUP = "aiocqhttp:GroupMessage:54321"
PRIVATE = "aiocqhttp:FriendMessage:67890"

OLD = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"
THIRD = "33333333-3333-4333-8333-333333333333"
FOREIGN = "44444444-4444-4444-8444-444444444444"
PRIVATE_ID = "55555555-5555-4555-8555-555555555555"
CREATED = "66666666-6666-4666-8666-666666666666"
AMBIGUOUS_A = "aaaaaaaa-1111-4111-8111-111111111111"
AMBIGUOUS_B = "aaaaaaaa-2222-4222-8222-222222222222"


@dataclass(frozen=True)
class _Conversation:
    cid: str
    user_id: str
    created_at: int
    history: str
    persona_id: str | None = None


def _rows() -> list[_Conversation]:
    return [
        _Conversation(OLD, GROUP, 100, '[{"role":"old-sentinel"}]'),
        _Conversation(NEW, GROUP, 200, '[{"role":"new-sentinel"}]'),
        _Conversation(FOREIGN, OTHER_GROUP, 300, '[{"role":"foreign-sentinel"}]'),
        _Conversation(PRIVATE_ID, PRIVATE, 400, '[{"role":"private-sentinel"}]'),
    ]


class _FakeManager:
    """Model the upstream manager's deliberately weak CID ownership checks."""

    def __init__(
        self,
        conversations: list[_Conversation] | None = None,
        persisted: dict[str, str] | None = None,
    ) -> None:
        self.rows = {item.cid: item for item in (conversations or _rows())}
        self.persisted = persisted if persisted is not None else {GROUP: OLD}
        self.current = dict(self.persisted)
        self.switch_calls: list[tuple[str, str]] = []
        self.detail_calls: list[tuple[str, str]] = []
        self.fail_on_switch: dict[int, str] = {}
        self.skip_persistence_on_switch: set[int] = set()
        self.detail_override: _Conversation | None = None
        self.create_calls: list[tuple[str, str, str | None]] = []

    async def new_conversation(
        self,
        umo: str,
        platform_id: str,
        *,
        persona_id: str | None = None,
    ) -> str:
        self.create_calls.append((umo, platform_id, persona_id))
        self.rows[CREATED] = _Conversation(
            CREATED,
            umo,
            500,
            history="",
            persona_id=persona_id,
        )
        self.current[umo] = CREATED
        self.persisted[umo] = CREATED
        return CREATED

    async def get_conversations(self, _umo: str) -> list[_Conversation]:
        # Deliberately include other scopes to prove the helper checks user_id.
        return list(self.rows.values())

    async def get_conversation(self, umo: str, cid: str) -> _Conversation | None:
        self.detail_calls.append((umo, cid))
        return self.detail_override if self.detail_override is not None else self.rows.get(cid)

    async def get_curr_conversation_id(self, umo: str) -> str | None:
        return self.current.get(umo)

    async def read_persisted(self, umo: str) -> str | None:
        return self.persisted.get(umo)

    async def switch_conversation(self, umo: str, cid: str) -> None:
        # The real API accepts an arbitrary CID; authorization belongs to caller.
        self.switch_calls.append((umo, cid))
        call_number = len(self.switch_calls)
        failure = self.fail_on_switch.get(call_number)
        if failure == "before":
            raise RuntimeError("synthetic pre-write failure")
        self.current[umo] = cid
        if failure == "after_memory":
            raise RuntimeError("synthetic partial failure")
        if call_number not in self.skip_persistence_on_switch:
            self.persisted[umo] = cid


class ResolveAndPageTests(unittest.TestCase):
    def test_canonical_full_id_and_unique_short_id_resolve_inside_group(self) -> None:
        rows = _rows()
        self.assertEqual(resolve_scoped_target(rows, GROUP, OLD).cid, OLD)
        self.assertEqual(resolve_scoped_target(rows, GROUP, "22222222").cid, NEW)
        self.assertEqual(resolve_scoped_target(rows, GROUP, NEW.upper()).cid, NEW)
        self.assertEqual(resolve_scoped_target(rows, GROUP, "  11111111  ").cid, OLD)

    def test_invalid_ids_are_rejected_before_lookup(self) -> None:
        for supplied in ("", "1234567", "1111111z", "../11111111", "11111111-", None):
            with self.subTest(supplied=supplied):
                with self.assertRaises(ConversationTargetError) as raised:
                    resolve_scoped_target(_rows(), GROUP, supplied)  # type: ignore[arg-type]
                self.assertEqual(raised.exception.reason, "invalid")

    def test_unknown_id_is_not_found(self) -> None:
        with self.assertRaises(ConversationTargetError) as raised:
            resolve_scoped_target(_rows(), GROUP, "deadbeef")
        self.assertEqual(raised.exception.reason, "not_found")

    def test_other_group_and_private_conversations_are_not_found(self) -> None:
        for cid in (FOREIGN, PRIVATE_ID, "44444444", "55555555"):
            with self.subTest(cid=cid):
                with self.assertRaises(ConversationTargetError) as raised:
                    resolve_scoped_target(_rows(), GROUP, cid)
                self.assertEqual(raised.exception.reason, "not_found")

    def test_ambiguous_short_id_never_selects_arbitrary_record(self) -> None:
        rows = _rows() + [
            _Conversation(AMBIGUOUS_A, GROUP, 500, "first"),
            _Conversation(AMBIGUOUS_B, GROUP, 600, "second"),
        ]
        with self.assertRaises(ConversationTargetError) as raised:
            resolve_scoped_target(rows, GROUP, "aaaaaaaa")
        self.assertEqual(raised.exception.reason, "ambiguous")
        self.assertEqual(resolve_scoped_target(rows, GROUP, AMBIGUOUS_A).cid, AMBIGUOUS_A)

    def test_foreign_prefix_collision_does_not_create_group_ambiguity(self) -> None:
        rows = _rows() + [
            _Conversation("22222222-aaaa-4aaa-8aaa-aaaaaaaaaaaa", OTHER_GROUP, 500, "x")
        ]
        self.assertEqual(resolve_scoped_target(rows, GROUP, "22222222").cid, NEW)

    def test_pagination_is_bounded_newest_first_and_group_scoped(self) -> None:
        rows = _rows() + [
            _Conversation(THIRD, GROUP, 300, "third"),
        ]
        first, total = page_scoped_conversations(rows, GROUP, 1, page_size=2)
        second, second_total = page_scoped_conversations(rows, GROUP, 2, page_size=2)
        self.assertEqual([item.cid for item in first], [THIRD, NEW])
        self.assertEqual([item.cid for item in second], [OLD])
        self.assertEqual((total, second_total), (2, 2))
        self.assertNotIn(FOREIGN, [item.cid for item in first + second])
        self.assertNotIn(PRIVATE_ID, [item.cid for item in first + second])

    def test_empty_and_out_of_range_pages_return_no_foreign_data(self) -> None:
        entries, pages = page_scoped_conversations(_rows(), "unknown-umo", 1)
        self.assertEqual(entries, [])
        self.assertEqual(pages, 1)
        entries, pages = page_scoped_conversations(_rows(), GROUP, 99)
        self.assertEqual(entries, [])
        self.assertEqual(pages, 1)
        with self.assertRaises(ValueError):
            page_scoped_conversations(_rows(), GROUP, 0)


class SwitchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = _FakeManager()

    def _switch(
        self,
        cid: str,
        *,
        manager: _FakeManager | None = None,
        busy_checker=None,
        umo: str = GROUP,
    ):
        selected_manager = manager or self.manager
        return asyncio.run(
            switch_scoped_conversation(
                selected_manager,
                selected_manager.read_persisted,
                busy_checker if busy_checker is not None else (lambda: False),
                umo,
                cid,
            )
        )

    def test_switch_to_old_then_back_to_new_preserves_all_histories(self) -> None:
        self.manager.current[GROUP] = NEW
        self.manager.persisted[GROUP] = NEW
        histories = {cid: item.history for cid, item in self.manager.rows.items()}

        old_result = self._switch(OLD)
        self.assertEqual(old_result.status, "switched")
        self.assertEqual((self.manager.current[GROUP], self.manager.persisted[GROUP]), (OLD, OLD))
        new_result = self._switch("22222222")
        self.assertEqual(new_result.status, "switched")
        self.assertEqual((self.manager.current[GROUP], self.manager.persisted[GROUP]), (NEW, NEW))
        self.assertEqual({cid: item.history for cid, item in self.manager.rows.items()}, histories)
        self.assertEqual(self.manager.switch_calls, [(GROUP, OLD), (GROUP, NEW)])

    def test_same_conversation_returns_unchanged_without_write(self) -> None:
        result = self._switch(OLD)
        self.assertEqual(result.status, "unchanged")
        self.assertEqual(result.current_id, OLD)
        self.assertEqual(self.manager.switch_calls, [])

    def test_invalid_unknown_and_ambiguous_targets_do_not_write(self) -> None:
        self.manager.rows[AMBIGUOUS_A] = _Conversation(AMBIGUOUS_A, GROUP, 300, "a")
        self.manager.rows[AMBIGUOUS_B] = _Conversation(AMBIGUOUS_B, GROUP, 400, "b")
        for supplied, expected in (
            ("bad", "invalid"),
            ("deadbeef", "not_found"),
            ("aaaaaaaa", "ambiguous"),
        ):
            with self.subTest(supplied=supplied):
                self.assertEqual(self._switch(supplied).status, expected)
        self.assertEqual(self.manager.switch_calls, [])
        self.assertEqual(self.manager.detail_calls, [])
        self.assertEqual((self.manager.current[GROUP], self.manager.persisted[GROUP]), (OLD, OLD))

    def test_other_group_and_private_ids_do_not_write(self) -> None:
        for cid in (FOREIGN, PRIVATE_ID):
            with self.subTest(cid=cid):
                self.assertEqual(self._switch(cid).status, "not_found")
        self.assertEqual(self.manager.switch_calls, [])
        self.assertEqual(self.manager.detail_calls, [])

    def test_detail_owner_is_checked_again_after_scoped_listing(self) -> None:
        self.manager.detail_override = _Conversation(NEW, OTHER_GROUP, 200, "wrong-owner")
        self.assertEqual(self._switch(NEW).status, "not_found")
        self.assertEqual(self.manager.switch_calls, [])

    def test_busy_true_unknown_or_error_refuses_switch(self) -> None:
        def raises():
            raise RuntimeError("activity query unavailable")

        for checker in (lambda: True, lambda: None, raises):
            with self.subTest(checker=checker):
                self.assertEqual(self._switch(NEW, busy_checker=checker).status, "busy")
        self.assertEqual(self.manager.switch_calls, [])

    def test_persisted_pointer_mismatch_refuses_switch(self) -> None:
        self.manager.persisted[GROUP] = NEW
        self.assertEqual(self._switch(NEW).status, "state_mismatch")
        self.assertEqual(self.manager.switch_calls, [])

    def test_unowned_current_pointer_refuses_switch(self) -> None:
        self.manager.current[GROUP] = FOREIGN
        self.manager.persisted[GROUP] = FOREIGN
        self.assertEqual(self._switch(NEW).status, "state_mismatch")
        self.assertEqual(self.manager.switch_calls, [])

    def test_pointer_changed_between_validation_and_write_is_detected(self) -> None:
        def concurrent_change() -> bool:
            self.manager.current[GROUP] = NEW
            self.manager.persisted[GROUP] = NEW
            return False

        self.assertEqual(self._switch(NEW, busy_checker=concurrent_change).status, "changed")
        self.assertEqual(self.manager.switch_calls, [])

    def test_failure_after_memory_update_rolls_back_both_pointers(self) -> None:
        self.manager.fail_on_switch[1] = "after_memory"
        result = self._switch(NEW)
        self.assertEqual(result.status, "failed_rolled_back")
        self.assertEqual((self.manager.current[GROUP], self.manager.persisted[GROUP]), (OLD, OLD))
        self.assertEqual(self.manager.switch_calls, [(GROUP, NEW), (GROUP, OLD)])

    def test_post_switch_persistence_mismatch_rolls_back(self) -> None:
        self.manager.skip_persistence_on_switch.add(1)
        result = self._switch(NEW)
        self.assertEqual(result.status, "failed_rolled_back")
        self.assertEqual((self.manager.current[GROUP], self.manager.persisted[GROUP]), (OLD, OLD))
        self.assertEqual(self.manager.switch_calls, [(GROUP, NEW), (GROUP, OLD)])

    def test_rollback_failure_reports_uncertain_state(self) -> None:
        self.manager.fail_on_switch[1] = "after_memory"
        self.manager.fail_on_switch[2] = "before"
        result = self._switch(NEW)
        self.assertEqual(result.status, "failed_uncertain")
        self.assertEqual(self.manager.current[GROUP], NEW)
        self.assertEqual(self.manager.persisted[GROUP], OLD)

    def test_rollback_does_not_overwrite_detected_third_party_selection(self) -> None:
        class ConcurrentManager(_FakeManager):
            async def switch_conversation(self, umo: str, cid: str) -> None:
                self.switch_calls.append((umo, cid))
                self.current[umo] = THIRD
                self.persisted[umo] = THIRD
                raise RuntimeError("synthetic concurrent /new")

        manager = ConcurrentManager()
        manager.rows[THIRD] = _Conversation(THIRD, GROUP, 500, "third-history")
        result = self._switch(NEW, manager=manager)
        self.assertEqual(result.status, "failed_uncertain")
        self.assertEqual(manager.current[GROUP], THIRD)
        self.assertEqual(manager.persisted[GROUP], THIRD)
        self.assertEqual(manager.switch_calls, [(GROUP, NEW)])

    def test_one_groups_selection_does_not_change_another(self) -> None:
        self.manager.current[OTHER_GROUP] = FOREIGN
        self.manager.persisted[OTHER_GROUP] = FOREIGN
        result = self._switch(NEW)
        self.assertEqual(result.status, "switched")
        self.assertEqual(self.manager.current[OTHER_GROUP], FOREIGN)
        self.assertEqual(self.manager.persisted[OTHER_GROUP], FOREIGN)

    def test_selection_survives_simulated_manager_reload(self) -> None:
        self.assertEqual(self._switch(NEW).status, "switched")
        reloaded = _FakeManager(list(self.manager.rows.values()), self.manager.persisted)
        self.assertEqual(asyncio.run(reloaded.get_curr_conversation_id(GROUP)), NEW)
        self.assertEqual(asyncio.run(reloaded.read_persisted(GROUP)), NEW)
        self.assertEqual(self._switch(OLD, manager=reloaded).status, "switched")
        self.assertEqual(self.manager.persisted[GROUP], OLD)


class CreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = _FakeManager()
        self.manager.rows[OLD] = _Conversation(
            OLD,
            GROUP,
            100,
            history='[{"role":"private-old-history"}]',
            persona_id="persona-v1.1",
        )

    def _create(self, *, busy_checker=lambda: False, manager=None, umo=GROUP):
        selected_manager = manager or self.manager
        return asyncio.run(
            create_scoped_conversation(
                selected_manager,
                selected_manager.read_persisted,
                busy_checker,
                umo,
                "napcat",
            )
        )

    def test_create_uses_official_manager_semantics_and_preserves_history(self) -> None:
        histories = {cid: row.history for cid, row in self.manager.rows.items()}
        self.manager.current[OTHER_GROUP] = FOREIGN
        self.manager.persisted[OTHER_GROUP] = FOREIGN
        other_selection = self.manager.current[OTHER_GROUP]
        result = self._create()
        self.assertEqual(result.status, "created")
        self.assertEqual(result.previous_id, OLD)
        self.assertEqual(result.conversation_id, CREATED)
        self.assertEqual(self.manager.create_calls, [(GROUP, "napcat", "persona-v1.1")])
        self.assertEqual(self.manager.current[GROUP], CREATED)
        self.assertEqual(self.manager.persisted[GROUP], CREATED)
        self.assertEqual(
            {cid: row.history for cid, row in self.manager.rows.items() if cid in histories},
            histories,
        )
        self.assertEqual(self.manager.current[OTHER_GROUP], other_selection)
        self.assertEqual(self.manager.persisted[OTHER_GROUP], other_selection)

        # The durable selection remains available after a manager/process reload.
        reloaded = _FakeManager(list(self.manager.rows.values()), self.manager.persisted)
        self.assertEqual(asyncio.run(reloaded.get_curr_conversation_id(GROUP)), CREATED)
        self.assertEqual(asyncio.run(reloaded.read_persisted(GROUP)), CREATED)

    def test_busy_true_unknown_or_error_refuses_creation(self) -> None:
        def raises():
            raise RuntimeError("active event state unavailable")

        for checker in (lambda: True, lambda: None, raises):
            with self.subTest(checker=checker):
                self.assertEqual(self._create(busy_checker=checker).status, "busy")
        self.assertEqual(self.manager.create_calls, [])
        self.assertEqual(self.manager.current[GROUP], OLD)

    def test_selection_mismatch_or_unowned_pointer_refuses_creation(self) -> None:
        self.manager.persisted[GROUP] = NEW
        self.assertEqual(self._create().status, "state_mismatch")
        self.assertEqual(self.manager.create_calls, [])

        self.manager.current[GROUP] = FOREIGN
        self.manager.persisted[GROUP] = FOREIGN
        self.assertEqual(self._create().status, "state_mismatch")
        self.assertEqual(self.manager.create_calls, [])

    def test_pointer_change_during_busy_check_refuses_creation(self) -> None:
        def concurrent_change():
            self.manager.current[GROUP] = NEW
            self.manager.persisted[GROUP] = NEW
            return False

        self.assertEqual(
            self._create(busy_checker=concurrent_change).status,
            "changed",
        )
        self.assertEqual(self.manager.create_calls, [])

    def test_new_conversation_keeps_other_scope_ids_out_of_the_new_record(self) -> None:
        result = self._create()
        self.assertEqual(result.status, "created")
        created = self.manager.rows[CREATED]
        self.assertEqual(created.user_id, GROUP)
        self.assertNotEqual(created.user_id, OTHER_GROUP)


if __name__ == "__main__":
    unittest.main()
