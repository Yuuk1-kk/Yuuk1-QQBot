"""Scoped, non-destructive AstrBot Conversation selection helpers.

AstrBot v4.28.2 does not check ownership in ``switch_conversation``. Keep the
authorization check here, using records returned for the current event's UMO.
Never format or log a Conversation's ``history`` field.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

_FULL_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_SHORT_ID = re.compile(r"[0-9a-f]{8,32}", re.IGNORECASE)


class ConversationTargetError(ValueError):
    """A supplied ID is invalid, absent from the UMO, or ambiguous."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SwitchResult:
    status: str
    target_id: str | None = None
    current_id: str | None = None


@dataclass(frozen=True)
class CreateResult:
    status: str
    conversation_id: str | None = None
    previous_id: str | None = None


def _scoped_conversations(conversations: Iterable[Any], umo: str) -> list[Any]:
    """Keep only records with the exact trusted message origin."""
    return [
        conversation
        for conversation in conversations
        if getattr(conversation, "user_id", None) == umo
        and isinstance(getattr(conversation, "cid", None), str)
    ]


def resolve_scoped_target(
    conversations: Iterable[Any], umo: str, supplied_id: str
) -> Any:
    """Resolve a full UUID or an unambiguous 8+ hex-digit prefix within UMO."""
    if not isinstance(supplied_id, str):
        raise ConversationTargetError("invalid")
    requested = supplied_id.strip().lower()
    full = _FULL_ID.fullmatch(requested) is not None
    short = _SHORT_ID.fullmatch(requested) is not None
    if not full and not short:
        raise ConversationTargetError("invalid")
    scoped = _scoped_conversations(conversations, umo)
    matches = [
        conversation
        for conversation in scoped
        if (
            conversation.cid.lower() == requested
            if full
            else conversation.cid.replace("-", "").lower().startswith(requested)
        )
    ]
    if not matches:
        raise ConversationTargetError("not_found")
    if len(matches) != 1:
        raise ConversationTargetError("ambiguous")
    return matches[0]


def page_scoped_conversations(
    conversations: Iterable[Any], umo: str, page: int, page_size: int = 5
) -> tuple[list[Any], int]:
    """Return one bounded, newest-first page without touching message bodies."""
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be positive")
    scoped = sorted(
        _scoped_conversations(conversations, umo),
        key=lambda conversation: (
            getattr(conversation, "created_at", 0) or 0,
            conversation.cid,
        ),
        reverse=True,
    )
    total_pages = max(1, (len(scoped) + page_size - 1) // page_size)
    start = (page - 1) * page_size
    return scoped[start : start + page_size], total_pages


async def _selection_state(
    manager: Any,
    persisted_reader: Callable[[str], Awaitable[str | None]],
    umo: str,
) -> tuple[str | None, str | None]:
    return (
        await manager.get_curr_conversation_id(umo),
        await persisted_reader(umo),
    )


async def create_scoped_conversation(
    manager: Any,
    persisted_reader: Callable[[str], Awaitable[str | None]],
    busy_checker: Callable[[], bool | None],
    umo: str,
    platform_id: str,
) -> CreateResult:
    """Create and select a new Conversation without removing scoped history.

    Uses AstrBot's public ``new_conversation`` API, which creates a new record
    and updates the selected pointer. A busy or indeterminate active-event
    snapshot refuses the operation. AstrBot exposes no atomic lock spanning
    event registration and this API call, so callers still need a quiet UMO.
    """
    try:
        before = await manager.get_conversations(umo)
        previous, persisted = await _selection_state(manager, persisted_reader, umo)
    except Exception:
        return CreateResult("failed_uncertain")

    scoped = _scoped_conversations(before, umo)
    before_ids = {conversation.cid for conversation in scoped}
    if previous != persisted:
        return CreateResult("state_mismatch", previous_id=previous)

    current = None
    if previous is not None:
        current = next(
            (conversation for conversation in scoped if conversation.cid == previous),
            None,
        )
        if current is None:
            return CreateResult("state_mismatch", previous_id=previous)
    persona_id = getattr(current, "persona_id", None)

    try:
        busy = busy_checker()
    except Exception:
        busy = None
    if busy is not False:
        return CreateResult("busy", previous_id=previous)

    try:
        current_again, persisted_again = await _selection_state(
            manager, persisted_reader, umo
        )
    except Exception:
        return CreateResult("failed_uncertain", previous_id=previous)
    if current_again != previous or persisted_again != previous:
        return CreateResult("changed", previous_id=current_again)

    # Recheck after the awaited pointer reads, immediately before creating.
    try:
        busy = busy_checker()
    except Exception:
        busy = None
    if busy is not False:
        return CreateResult("busy", previous_id=previous)

    try:
        conversation_id = await manager.new_conversation(
            umo,
            platform_id,
            persona_id=persona_id,
        )
    except Exception:
        return CreateResult("failed_uncertain", previous_id=previous)
    if not isinstance(conversation_id, str) or not conversation_id:
        return CreateResult("failed_uncertain", previous_id=previous)

    try:
        after = await manager.get_conversations(umo)
        selected, persisted_after = await _selection_state(
            manager, persisted_reader, umo
        )
    except Exception:
        return CreateResult("failed_uncertain", conversation_id, previous)

    scoped_after = _scoped_conversations(after, umo)
    after_ids = {conversation.cid for conversation in scoped_after}
    created_is_owned = any(
        conversation.cid == conversation_id for conversation in scoped_after
    )
    if (
        selected != conversation_id
        or persisted_after != conversation_id
        or not created_is_owned
        or not before_ids.issubset(after_ids)
        or conversation_id in before_ids
    ):
        return CreateResult("failed_uncertain", conversation_id, previous)
    return CreateResult("created", conversation_id, previous)


async def _restore_previous_selection(
    manager: Any,
    persisted_reader: Callable[[str], Awaitable[str | None]],
    umo: str,
    previous_id: str,
    target_id: str,
) -> SwitchResult:
    # The upstream manager may change its memory pointer before persistence
    # raises. Do not overwrite a third-party selection observed during the
    # attempt; this is best effort because AstrBot has no atomic CAS API.
    try:
        selected, persisted = await _selection_state(manager, persisted_reader, umo)
    except Exception:
        return SwitchResult("failed_uncertain", target_id)
    if selected == previous_id and persisted == previous_id:
        return SwitchResult("failed_rolled_back", target_id, previous_id)
    if selected not in (previous_id, target_id) or persisted not in (
        previous_id,
        target_id,
    ):
        return SwitchResult("failed_uncertain", target_id, selected)
    try:
        await manager.switch_conversation(umo, previous_id)
        selected, persisted = await _selection_state(manager, persisted_reader, umo)
    except Exception:
        return SwitchResult("failed_uncertain", target_id)
    if selected == previous_id and persisted == previous_id:
        return SwitchResult("failed_rolled_back", target_id, previous_id)
    return SwitchResult("failed_uncertain", target_id, selected)


async def switch_scoped_conversation(
    manager: Any,
    persisted_reader: Callable[[str], Awaitable[str | None]],
    busy_checker: Callable[[], bool | None],
    umo: str,
    supplied_id: str,
) -> SwitchResult:
    """Select only an owned Conversation and verify its durable pointer.

    ``busy_checker`` is conservative: True or None both refuse the switch.
    It cannot lock AstrBot's message scheduler; a new event can still register
    immediately after the check. An in-flight Agent writes its captured CID.
    """
    try:
        conversations = await manager.get_conversations(umo)
        selected, persisted = await _selection_state(manager, persisted_reader, umo)
    except Exception:
        return SwitchResult("failed_uncertain")

    scoped = _scoped_conversations(conversations, umo)
    if not selected or selected != persisted or selected not in {
        conversation.cid for conversation in scoped
    }:
        return SwitchResult("state_mismatch", current_id=selected)

    try:
        target = resolve_scoped_target(scoped, umo, supplied_id)
    except ConversationTargetError as exc:
        return SwitchResult(exc.reason, current_id=selected)
    target_id = target.cid
    if target_id == selected:
        return SwitchResult("unchanged", target_id, selected)

    # get_conversation itself has no UMO authorization. Use it only after the
    # UMO-filtered listing, and check its owner again before the write.
    try:
        detail = await manager.get_conversation(umo, target_id)
    except Exception:
        return SwitchResult("failed_uncertain", target_id, selected)
    if detail is None or getattr(detail, "user_id", None) != umo:
        return SwitchResult("not_found", target_id, selected)

    try:
        busy = busy_checker()
    except Exception:
        busy = None
    if busy is not False:
        return SwitchResult("busy", target_id, selected)

    try:
        selected_again, persisted_again = await _selection_state(
            manager, persisted_reader, umo
        )
    except Exception:
        return SwitchResult("failed_uncertain", target_id, selected)
    if selected_again != selected or persisted_again != selected:
        return SwitchResult("changed", target_id, selected_again)

    try:
        await manager.switch_conversation(umo, target_id)
        selected_after, persisted_after = await _selection_state(
            manager, persisted_reader, umo
        )
    except Exception:
        return await _restore_previous_selection(
            manager, persisted_reader, umo, selected, target_id
        )
    if selected_after == target_id and persisted_after == target_id:
        return SwitchResult("switched", target_id, target_id)
    return await _restore_previous_selection(
        manager, persisted_reader, umo, selected, target_id
    )
