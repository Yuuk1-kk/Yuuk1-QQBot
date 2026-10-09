"""Runtime-independent policy and configuration helpers for Yuuk1 Core."""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite

_ID_SPLIT_RE = re.compile(r"[,;\s]+")


def normalize_ids(value: object) -> frozenset[str]:
    """Normalize QQ IDs from WebUI list values or a delimited text value."""
    if value is None:
        return frozenset()
    if isinstance(value, str):
        candidates: Iterable[object] = _ID_SPLIT_RE.split(value)
    elif isinstance(value, int) and not isinstance(value, bool):
        candidates = (value,)
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = value
    else:
        return frozenset()

    normalized: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, int):
            candidate = str(candidate)
        if not isinstance(candidate, str):
            continue
        identifier = candidate.strip()
        if identifier.isdecimal():
            normalized.add(identifier)
    return frozenset(normalized)


def is_group_allowed(group_id: object, allowed_groups: frozenset[str]) -> bool:
    """Fail closed for groups absent from the allowlist and for private chats."""
    normalized_group_id = str(group_id or "").strip()
    return bool(normalized_group_id and normalized_group_id in allowed_groups)


def is_qq_context_allowed(
    group_id: object,
    allowed_groups: frozenset[str],
    allow_private_chat: bool,
) -> bool:
    """Apply the group allowlist or the explicit private-chat opt-in."""
    if str(group_id or "").strip():
        return is_group_allowed(group_id, allowed_groups)
    return allow_private_chat


def is_configured_admin(user_id: object, admin_users: frozenset[str]) -> bool:
    """Return whether a sender ID matches a configured project administrator."""
    normalized_user_id = str(user_id or "").strip()
    return bool(normalized_user_id and normalized_user_id in admin_users)


def normalize_owner_id(value: object) -> str:
    """Accept only a configured decimal string; never coerce it through int."""
    if not isinstance(value, str):
        return ""
    normalized = value.strip()
    return normalized if normalized.isascii() and normalized.isdigit() else ""


def is_configured_owner(
    platform_name: object,
    sender_id: object,
    owner_qq_id: object,
) -> bool:
    """Identify the configured Owner only from the trusted QQ sender field."""
    return classify_owner_identity(platform_name, sender_id, owner_qq_id) == "verified_owner"


def classify_owner_identity(
    platform_name: object,
    sender_id: object,
    owner_qq_id: object,
) -> str:
    """Return a request identity state using only trusted platform/sender fields.

    The returned state is deliberately independent of display names, message
    text, mentions, replies, conversation history, and model output.
    """
    if platform_name != "aiocqhttp":
        return "unavailable"

    actual_sender_id = str(sender_id or "").strip()
    if not actual_sender_id.isascii() or not actual_sender_id.isdigit():
        return "unavailable"

    configured_owner_id = normalize_owner_id(owner_qq_id)
    if not configured_owner_id:
        return "unconfigured"
    if actual_sender_id == configured_owner_id:
        return "verified_owner"
    return "verified_non_owner"


def _positive_int(value: object, default: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(max(parsed, 1), maximum)


def _nonnegative_int(value: object, default: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(max(parsed, 0), maximum)


def _bool_value(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def _probability(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not isfinite(parsed):
        return default
    return min(max(parsed, 0.0), 1.0)


def _hour(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(max(parsed, 0), 23)


@dataclass(frozen=True, slots=True)
class CoreSettings:
    bot_name: str
    allowed_groups: frozenset[str]
    allow_private_chat: bool
    admin_users: frozenset[str]
    owner_qq_id: str
    system_prompt: str
    group_identity_enabled: bool
    group_identity_persistence_enabled: bool
    group_identity_max_aliases: int
    group_identity_max_members_per_group: int
    rate_limit_enabled: bool
    rate_limit_window: int
    rate_limit_requests: int
    user_rate_limit_window: int
    user_rate_limit_requests: int
    free_talk_enabled: bool
    engagement_enabled: bool
    engagement_timeout_seconds: int
    free_talk_min_interval_seconds: int
    free_talk_decision_interval_seconds: int
    free_talk_probability: float
    free_talk_nickname_probability: float
    free_talk_context_messages: int
    free_talk_context_ttl_seconds: int
    free_talk_min_recent_messages: int
    multi_message_enabled: bool
    multi_message_max_parts: int
    multi_message_min_chars_to_split: int
    stickers_enabled: bool
    sticker_send_mode: str
    sticker_diagnostics_enabled: bool
    owner_identity_diagnostics_enabled: bool
    sticker_repeat_window: int
    idle_speak_enabled: bool
    idle_threshold_seconds: int
    idle_check_interval_seconds: int
    idle_probability: float
    idle_min_interval_seconds: int
    idle_active_start_hour: int
    idle_active_end_hour: int


def normalize_config(config: Mapping[str, object] | None) -> CoreSettings:
    """Return bounded settings even when stored WebUI values are malformed."""
    values: Mapping[str, object] = config if isinstance(config, Mapping) else {}
    bot_name_value = values.get("bot_name", "鲸鲸")
    prompt_value = values.get("system_prompt", "")
    bot_name = bot_name_value.strip() if isinstance(bot_name_value, str) else "鲸鲸"
    system_prompt = prompt_value.strip() if isinstance(prompt_value, str) else ""
    sticker_send_mode_value = values.get("sticker_send_mode", "image")
    sticker_send_mode = (
        sticker_send_mode_value
        if isinstance(sticker_send_mode_value, str)
        and sticker_send_mode_value in {"image", "qq_custom"}
        else "image"
    )
    return CoreSettings(
        bot_name=bot_name or "鲸鲸",
        allowed_groups=normalize_ids(values.get("allowed_groups", [])),
        allow_private_chat=_bool_value(values.get("allow_private_chat", False), False),
        admin_users=normalize_ids(values.get("admin_users", [])),
        owner_qq_id=normalize_owner_id(values.get("owner_qq_id", "")),
        system_prompt=system_prompt,
        group_identity_enabled=_bool_value(
            values.get("group_identity_enabled", True), True
        ),
        group_identity_persistence_enabled=_bool_value(
            values.get("group_identity_persistence_enabled", True), True
        ),
        group_identity_max_aliases=_nonnegative_int(
            values.get("group_identity_max_aliases", 5), 5, 5
        ),
        group_identity_max_members_per_group=_positive_int(
            values.get("group_identity_max_members_per_group", 500), 500, 500
        ),
        rate_limit_enabled=_bool_value(values.get("rate_limit_enabled", True), True),
        rate_limit_window=_positive_int(values.get("rate_limit_window", 60), 60, 86_400),
        rate_limit_requests=_positive_int(values.get("rate_limit_requests", 30), 30, 10_000),
        user_rate_limit_window=_positive_int(
            values.get("user_rate_limit_window", 60), 60, 86_400
        ),
        user_rate_limit_requests=_positive_int(
            values.get("user_rate_limit_requests", 8), 8, 10_000
        ),
        free_talk_enabled=_bool_value(values.get("free_talk_enabled", False), False),
        engagement_enabled=_bool_value(
            values.get("engagement_enabled", True), True
        ),
        engagement_timeout_seconds=_positive_int(
            values.get("engagement_timeout_seconds", 300), 300, 86_400
        ),
        # Legacy fields remain readable for existing WebUI configs, but the
        # Free Talk decision path deliberately does not consume either value.
        free_talk_min_interval_seconds=_nonnegative_int(
            values.get("free_talk_min_interval_seconds", 0), 0, 86_400
        ),
        free_talk_decision_interval_seconds=_nonnegative_int(
            values.get("free_talk_decision_interval_seconds", 0), 0, 3_600
        ),
        free_talk_probability=_probability(
            values.get("free_talk_probability", 0.35), 0.35
        ),
        free_talk_nickname_probability=_probability(
            values.get("free_talk_nickname_probability", 1.0), 1.0
        ),
        free_talk_context_messages=_positive_int(
            values.get("free_talk_context_messages", 20), 20, 100
        ),
        free_talk_context_ttl_seconds=_positive_int(
            values.get("free_talk_context_ttl_seconds", 900), 900, 86_400
        ),
        free_talk_min_recent_messages=_positive_int(
            values.get("free_talk_min_recent_messages", 2), 2, 100
        ),
        multi_message_enabled=_bool_value(
            values.get("multi_message_enabled", True), True
        ),
        multi_message_max_parts=_positive_int(
            values.get("multi_message_max_parts", 3), 3, 3
        ),
        multi_message_min_chars_to_split=_positive_int(
            values.get("multi_message_min_chars_to_split", 20), 20, 1000
        ),
        stickers_enabled=_bool_value(values.get("stickers_enabled", False), False),
        sticker_send_mode=sticker_send_mode,
        sticker_diagnostics_enabled=_bool_value(
            values.get("sticker_diagnostics_enabled", False), False
        ),
        owner_identity_diagnostics_enabled=_bool_value(
            values.get("owner_identity_diagnostics_enabled", False), False
        ),
        sticker_repeat_window=_positive_int(
            values.get("sticker_repeat_window", 4), 4, 5
        ),
        idle_speak_enabled=_bool_value(values.get("idle_speak_enabled", False), False),
        idle_threshold_seconds=_positive_int(
            values.get("idle_threshold_seconds", 1800), 1800, 604_800
        ),
        idle_check_interval_seconds=_positive_int(
            values.get("idle_check_interval_seconds", 300), 300, 86_400
        ),
        idle_probability=_probability(values.get("idle_probability", 0.1), 0.1),
        idle_min_interval_seconds=_positive_int(
            values.get("idle_min_interval_seconds", 21_600), 21_600, 604_800
        ),
        idle_active_start_hour=_hour(values.get("idle_active_start_hour", 9), 9),
        idle_active_end_hour=_hour(values.get("idle_active_end_hour", 23), 23),
    )


class SlidingWindowRateLimiter:
    """Small in-memory sliding window limiter; restart clears its buckets."""

    def __init__(self, window_seconds: int, request_limit: int) -> None:
        self.window_seconds = _positive_int(window_seconds, 60, 86_400)
        self.request_limit = _positive_int(request_limit, 5, 10_000)
        self._hits: dict[str, deque[float]] = {}
        self._next_cleanup_at = 0.0

    def allow(self, scope: str, now: float | None = None) -> tuple[bool, float]:
        """Record a hit; return (allowed, retry_after_seconds)."""
        timestamp = time.monotonic() if now is None else now
        allowed, retry_after = self._check(scope, timestamp)
        if allowed:
            self._record(scope, timestamp)
        return allowed, retry_after

    def _check(self, scope: str, timestamp: float) -> tuple[bool, float]:
        """Inspect capacity without consuming it, for compound policies."""
        cutoff = timestamp - self.window_seconds
        if len(self._hits) > 256 and timestamp >= self._next_cleanup_at:
            for existing_scope, existing_hits in list(self._hits.items()):
                while existing_hits and existing_hits[0] <= cutoff:
                    existing_hits.popleft()
                if not existing_hits:
                    self._hits.pop(existing_scope, None)
            self._next_cleanup_at = timestamp + min(self.window_seconds, 60)

        hits = self._hits.get(scope)
        if hits is None:
            return True, 0.0
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if not hits:
            self._hits.pop(scope, None)
            return True, 0.0

        if len(hits) >= self.request_limit:
            retry_after = max(0.0, hits[0] + self.window_seconds - timestamp)
            return False, retry_after

        return True, 0.0

    def _record(self, scope: str, timestamp: float) -> None:
        self._hits.setdefault(scope, deque()).append(timestamp)


class TwoLevelRateLimiter:
    """Charge admitted requests to both a QQ user and its group."""

    def __init__(
        self,
        user_window_seconds: int,
        user_request_limit: int,
        group_window_seconds: int,
        group_request_limit: int,
    ) -> None:
        self.user = SlidingWindowRateLimiter(user_window_seconds, user_request_limit)
        self.group = SlidingWindowRateLimiter(group_window_seconds, group_request_limit)

    def allow(
        self,
        user_id: str,
        group_id: str,
        now: float | None = None,
    ) -> tuple[bool, float]:
        """Reject without charging either bucket; private chats use only user quota."""
        user_key = str(user_id or "").strip()
        group_key = str(group_id or "").strip()
        if not user_key:
            return False, 0.0
        timestamp = time.monotonic() if now is None else now
        user_allowed, user_retry = self.user._check(user_key, timestamp)
        if group_key:
            group_allowed, group_retry = self.group._check(group_key, timestamp)
        else:
            group_allowed, group_retry = True, 0.0
        if not user_allowed or not group_allowed:
            return False, max(user_retry, group_retry)
        self.user._record(user_key, timestamp)
        if group_key:
            self.group._record(group_key, timestamp)
        return True, 0.0
