"""Bounded, in-memory group context used by optional Jingjing features."""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any

from .group_identity import normalize_display_name, sanitize_display_name

JINGJING_ALIASES = ("鲸鲸", "大肥鱼", "蓝色大肥鱼", "小鲸", "鲸鱼娘")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_COMMAND_PREFIXES = ("/", "!")
_OPENING_DECORATION = re.compile(r"^[\s\W_]{0,5}")
_DESCRIPTION_NOUNS = (
    "表情包",
    "图片",
    "头像",
    "名字",
    "称呼",
    "设定",
    "梗",
    "截图",
    "形象",
    "角色",
    "昵称",
)
_DIRECT_ACTIONS = (
    "在吗",
    "在不在",
    "在不",
    "过来",
    "出来",
    "出列",
    "看看",
    "看下",
    "看一下",
    "快看",
    "看",
    "帮",
    "救命",
    "说话",
    "说",
    "解释",
    "告诉",
    "干嘛",
    "怎么",
    "为什么",
    "为啥",
    "觉得",
    "怎么看",
    "认为",
    "能不能",
    "能",
    "可以",
    "给我",
    "你",
    "你们",
    "别",
    "不许",
    "快",
    "赶紧",
    "速速",
    "吗",
    "呢",
    "呀",
    "啊",
)
_ROLE_PREFIXES = ("下士", "中士", "上士", "队长", "班长", "长官")
_CONTINUATION_PREFIXES = (
    "那你刚才",
    "那你现在",
    "然后怎么办",
    "那咋办",
    "真的假的",
    "怎么说",
    "所以呢",
    "然后呢",
    "还有呢",
    "你刚才",
    "你刚刚",
    "为什么",
    "为啥",
    "真的吗",
    "真的假的",
    "那你",
    "那现在呢",
    "那为什么",
    "那为啥",
    "然后你",
    "你呢",
    "怎么回事",
)
_SOFT_CONTINUATION_PREFIXES = ("那", "然后", "所以", "可是", "但是")
_NEW_TOPIC_PREFIXES = (
    "换个话题",
    "说个别的",
    "另外问一下",
    "不说这个了",
    "先不聊这个",
)
_SHORT_ANSWER_PREFIXES = (
    "不是",
    "不对",
    "没有",
    "还没",
    "不行",
    "不可以",
    "不愿意",
    "不知道",
    "是",
    "对",
    "嗯",
    "唔",
    "没",
    "有",
    "可以",
    "行",
    "好",
    "愿意",
    "因为",
    "我觉得",
    "我会",
    "不会",
    "应该",
    "可能",
    "差不多",
    "哈哈",
)
_MAX_GROUPS = 200
_MAX_ALIASES_PER_GROUP = 500
_MAX_MESSAGE_CHARS = 1000


@dataclass(frozen=True, slots=True)
class GroupMessage:
    """A redacted, in-memory message summary; it never carries platform IDs."""

    timestamp: float
    sender: str
    text: str
    mentions_jingjing: bool
    at_bot: bool
    is_bot: bool = False
    member_key: str = field(default="", repr=False)
    identity_scope_key: str = field(default="", repr=False)
    reply_target_member_key: str = field(default="", repr=False)
    reply_target_display_name: str = ""
    received_monotonic: float = field(default=0.0, repr=False)

    def as_prompt_dict(self) -> dict[str, object]:
        return {
            "role": "bot" if self.is_bot else "human",
            "sender": self.sender,
            "text": self.text,
            "reply_target": self.reply_target_display_name or None,
        }


@dataclass(slots=True)
class _GroupState:
    messages: deque[GroupMessage]
    aliases: OrderedDict[str, str] = field(default_factory=OrderedDict)
    next_alias: int = 1
    human_count: int = 0
    last_bot_human_count: int = 0
    last_activity_at: float | None = None
    last_activity_wall: float | None = None
    last_idle_attempt_at: float | None = None
    last_engaged_at: float | None = None
    last_engaged_member_key: str | None = None
    last_bot_turn_text: str = ""
    last_bot_turn_timestamp: float | None = None
    last_bot_turn_received_monotonic: float | None = None


def sanitize_text(value: object, limit: int = _MAX_MESSAGE_CHARS) -> str:
    """Remove control characters and bound text before retaining it in memory."""
    if not isinstance(value, str):
        return ""
    return _CONTROL_CHARS.sub("", value).strip()[:limit]


@dataclass(frozen=True, slots=True)
class SafeGroupMessage:
    """Sanitized message parts plus IDs retained only for local HMAC lookup."""

    text: str
    at_bot: bool
    reply_target_user_id: str = field(default="", repr=False)
    reply_target_display_name: str = ""


_FLATTENED_AT_ID = re.compile(r"@([^\s()]{1,64})\((\d{5,20}|all)\)")


def contains_flattened_at_id(value: object) -> bool:
    """Return whether adapter-flattened mention text embeds a platform ID."""
    return isinstance(value, str) and bool(_FLATTENED_AT_ID.search(value))


def _safe_flattened_at_name(match: re.Match[str]) -> str:
    target = match.group(2)
    if target == "all":
        return "@全体成员"
    name = sanitize_display_name(match.group(1), forbidden_values=(target,))
    return f"@{name or '群友'}"


def _safe_fallback_text(value: object) -> str:
    text = sanitize_text(value)
    return _FLATTENED_AT_ID.sub(_safe_flattened_at_name, text)


def sanitize_flattened_message_text(value: object) -> str:
    """Remove IDs from adapter-flattened @name(id) message text."""
    return _safe_fallback_text(value)


def extract_group_message(
    components: object,
    *,
    self_id: object,
    fallback_text: object = "",
) -> SafeGroupMessage:
    """Extract plain content, safe At names, and an optional Reply target."""
    if not isinstance(components, (list, tuple)):
        return SafeGroupMessage(_safe_fallback_text(fallback_text), False)
    if not components:
        return SafeGroupMessage("", False)

    self_value = str(self_id or "").strip()
    parts: list[str] = []
    at_bot = False
    reply_target_user_id = ""
    reply_target_display_name = ""
    for component in components:
        name = type(component).__name__.lower()
        component_type = str(getattr(component, "type", "")).lower()
        if name == "plain" or component_type == "plain":
            parts.append(sanitize_text(getattr(component, "text", "")))
        elif name == "at" or component_type in {"at", "componenttype.at"}:
            target = str(getattr(component, "qq", "") or "").strip()
            is_target_bot = bool(self_value and target == self_value)
            at_bot = at_bot or is_target_bot
            target_name = sanitize_display_name(
                getattr(component, "name", ""),
                forbidden_values=(target, self_value),
            )
            if target == "all":
                target_name = "全体成员"
            parts.append("@鲸鲸" if is_target_bot else f"@{target_name or '群友'}")
        elif name == "reply" or component_type in {"reply", "componenttype.reply"}:
            raw_sender_id = str(getattr(component, "sender_id", "") or "").strip()
            if raw_sender_id and raw_sender_id != "0":
                reply_target_user_id = raw_sender_id
            if raw_sender_id and self_value and raw_sender_id == self_value:
                reply_target_display_name = "鲸鲸"
            else:
                reply_target_display_name = sanitize_display_name(
                    getattr(component, "sender_nickname", ""),
                    forbidden_values=(raw_sender_id, self_value),
                )
            parts.append("[引用消息]")
        elif name == "image" or component_type == "image":
            parts.append("[图片]")
        elif name in {"record", "audio"} or component_type in {"record", "audio"}:
            parts.append("[语音]")
        elif name == "video" or component_type == "video":
            parts.append("[视频]")
        elif name == "file" or component_type == "file":
            parts.append("[文件]")
        elif name == "face" or component_type == "face":
            parts.append("[表情]")
        else:
            parts.append("[其他消息]")
    return SafeGroupMessage(
        text=sanitize_text(" ".join(part for part in parts if part)),
        at_bot=at_bot,
        reply_target_user_id=reply_target_user_id,
        reply_target_display_name=reply_target_display_name,
    )


def contains_jingjing_alias(text: str) -> bool:
    return any(alias in text for alias in JINGJING_ALIASES)


def is_direct_nickname_address(text: str) -> bool:
    """Recognize a nickname used as the message's addressee, not as its topic."""
    normalized = sanitize_text(text)
    opening = _OPENING_DECORATION.match(normalized)
    if opening is None:
        return False
    body = normalized[opening.end() :]
    for alias in sorted(JINGJING_ALIASES, key=len, reverse=True):
        if not body.startswith(alias):
            continue
        remainder = body[len(alias) :].lstrip()
        if not remainder or all(char in "，,。.!！?？~～…" for char in remainder):
            return True
        remainder = remainder.lstrip("，,:：、 ")
        if not remainder:
            return True
        if any(remainder.startswith(noun) for noun in _DESCRIPTION_NOUNS):
            return False
        # Description constructions such as "这个名字" are noun phrases, not
        # vocatives. Keep this exclusion ahead of the broader request cues.
        if remainder.startswith("这个") and any(
            noun in remainder[:8] for noun in _DESCRIPTION_NOUNS
        ):
            return False
        if any(remainder.startswith(cue) for cue in _DIRECT_ACTIONS):
            return True
        # A short rank/title before an imperative is a common playful direct call
        # (for example, "大肥鱼下士出列").
        if any(
            remainder.startswith(role)
            and remainder[len(role) :].startswith(("出列", "过来", "出来", "报到"))
            for role in _ROLE_PREFIXES
        ):
            return True
    return False


def reply_target_sender_id(components: object) -> str | None:
    """Return a Reply component's resolved sender ID, if AstrBot supplied one."""
    if not isinstance(components, (list, tuple)):
        return None
    for component in components:
        name = type(component).__name__.lower()
        component_type = str(getattr(component, "type", "")).lower()
        if name != "reply" and component_type not in {"reply", "componenttype.reply"}:
            continue
        sender_id = getattr(component, "sender_id", None)
        normalized = str(sender_id or "").strip()
        if normalized and normalized != "0":
            return normalized
        return None
    return None


def has_reply_component(components: object) -> bool:
    """Return whether the chain contains a resolved or unresolved Reply part."""
    if not isinstance(components, (list, tuple)):
        return False
    return any(
        type(component).__name__.lower() == "reply"
        or str(getattr(component, "type", "")).lower()
        in {"reply", "componenttype.reply"}
        for component in components
    )


def is_clear_continuation(text: str) -> bool:
    """Recognize short Chinese follow-ups that naturally refer to the last turn."""
    normalized = sanitize_text(text).lstrip(" ，,。.!！?？~～…")
    if not normalized:
        return False
    if any(normalized.startswith(prefix) for prefix in _NEW_TOPIC_PREFIXES):
        return False
    return any(
        normalized.startswith(prefix)
        for prefix in (*_CONTINUATION_PREFIXES, *_SOFT_CONTINUATION_PREFIXES)
    )


def engagement_relevance(
    *,
    text: str,
    same_as_last_engaged_user: bool,
    reply_to_bot: bool,
    reply_to_other_user: bool,
    previous_messages: tuple[GroupMessage, ...] | list[GroupMessage],
) -> str:
    """Return RELATED, UNRELATED, or AMBIGUOUS using high-confidence local cues."""
    if reply_to_bot or is_direct_nickname_address(text):
        return "RELATED"
    if reply_to_other_user:
        return "UNRELATED"
    if any(sanitize_text(text).startswith(prefix) for prefix in _NEW_TOPIC_PREFIXES):
        return "UNRELATED"
    normalized = sanitize_text(text).lstrip(" ，,。.!！?？~～…")
    if is_clear_continuation(normalized):
        if not any(
            normalized.startswith(prefix) for prefix in _SOFT_CONTINUATION_PREFIXES
        ):
            return "RELATED"
        if same_as_last_engaged_user and (
            "你" in normalized
            or any(term in normalized for term in ("为什么", "为啥", "怎么办", "怎么说"))
            or normalized.endswith(("呢", "吗", "嘛", "？", "?"))
        ):
            return "RELATED"
        return "AMBIGUOUS"
    last_bot_message = next(
        (message for message in reversed(previous_messages) if message.is_bot), None
    )
    current_normalized = sanitize_text(text)
    if (
        same_as_last_engaged_user
        and last_bot_message is not None
        and len(current_normalized) <= 32
        and any(
            current_normalized.startswith(prefix)
            for prefix in _SHORT_ANSWER_PREFIXES
        )
        and re.search(r"(?:[？?]|吗[？?！!。.]?|呢[？?！!。.]?)\s*$", last_bot_message.text)
    ):
        # A concise answer from the same user after Jingjing asked a question.
        return "RELATED"
    return "AMBIGUOUS"


def select_engagement_context(
    messages: tuple[GroupMessage, ...] | list[GroupMessage],
    *,
    recent_limit: int = 8,
) -> tuple[GroupMessage, ...]:
    """Keep the newest context plus the latest bot turn even after interleaving."""
    if not messages:
        return ()
    limit = max(1, min(int(recent_limit), 10))
    recent = list(messages[-limit:])
    last_bot = next((item for item in reversed(messages) if item.is_bot), None)
    if last_bot is not None and last_bot not in recent:
        recent.insert(0, last_bot)
    return tuple(recent)


def is_command_message(text: str) -> bool:
    normalized = text.lstrip()
    return bool(normalized and normalized.startswith(_COMMAND_PREFIXES))


def extract_safe_message(
    components: object,
    *,
    self_id: object,
    fallback_text: object = "",
) -> tuple[str, bool]:
    """Compatibility wrapper returning sanitized text and @Bot detection."""
    message = extract_group_message(
        components,
        self_id=self_id,
        fallback_text=fallback_text,
    )
    return message.text, message.at_bot


class GroupContextBuffer:
    """Keep recent bounded context and ephemeral activity per unified group session."""

    def __init__(
        self,
        *,
        max_messages: int = 20,
        ttl_seconds: int = 900,
        max_groups: int = _MAX_GROUPS,
    ) -> None:
        self.max_messages = max(1, min(int(max_messages), 100))
        self.ttl_seconds = max(1, min(int(ttl_seconds), 86_400))
        self.max_groups = max(1, min(int(max_groups), _MAX_GROUPS))
        self._groups: OrderedDict[str, _GroupState] = OrderedDict()
        self._alias_salt = secrets.token_bytes(32)

    def _state(self, session: str, *, create: bool = False) -> _GroupState | None:
        key = str(session or "").strip()
        if not key:
            return None
        state = self._groups.get(key)
        if state is None and create:
            while len(self._groups) >= self.max_groups:
                self._groups.popitem(last=False)
            state = _GroupState(messages=deque(maxlen=self.max_messages))
            self._groups[key] = state
        elif state is not None:
            self._groups.move_to_end(key)
        return state

    def _prune_messages(self, state: _GroupState, now: float) -> None:
        cutoff = now - self.ttl_seconds
        while state.messages and state.messages[0].received_monotonic < cutoff:
            state.messages.popleft()

    def _sender_label(
        self,
        state: _GroupState,
        member_key: str,
        display_name: object,
    ) -> str:
        name = sanitize_display_name(display_name)
        key = member_key
        if name:
            return name
        if key and key in state.aliases:
            state.aliases.move_to_end(key)
            return state.aliases[key]
        alias = f"群友{state.next_alias}"
        state.next_alias += 1
        if key:
            state.aliases[key] = alias
            while len(state.aliases) > _MAX_ALIASES_PER_GROUP:
                state.aliases.popitem(last=False)
        return alias

    def sender_token(self, sender_key: object) -> str:
        """Return a process-local keyed identifier for sender comparisons."""
        raw_key = str(sender_key or "").strip()
        if not raw_key:
            return ""
        return hashlib.blake2b(
            raw_key.encode("utf-8"),
            key=self._alias_salt,
            digest_size=16,
        ).hexdigest()

    def record_message(
        self,
        session: str,
        *,
        sender_key: object,
        display_name: object,
        text: object,
        timestamp: float,
        now: float,
        at_bot: bool = False,
        member_key: str = "",
        identity_scope_key: str = "",
        reply_target_member_key: str = "",
        reply_target_display_name: str = "",
    ) -> GroupMessage | None:
        state = self._state(session, create=True)
        if state is None:
            return None
        self._prune_messages(state, now)
        safe_text = sanitize_text(text)
        if not safe_text:
            return None
        safe_member_key = member_key or self.sender_token(sender_key)
        message = GroupMessage(
            timestamp=timestamp,
            sender=self._sender_label(state, safe_member_key, display_name),
            text=safe_text,
            mentions_jingjing=contains_jingjing_alias(safe_text),
            at_bot=at_bot,
            member_key=safe_member_key,
            identity_scope_key=identity_scope_key,
            reply_target_member_key=reply_target_member_key,
            reply_target_display_name=reply_target_display_name,
            received_monotonic=now,
        )
        state.messages.append(message)
        state.human_count += 1
        state.last_activity_at = now
        state.last_activity_wall = timestamp
        return message

    def record_bot_reply(
        self,
        session: str,
        *,
        timestamp: float,
        now: float,
        text: object = "",
        member_key: str = "",
        engage: bool = False,
    ) -> None:
        state = self._state(session, create=False)
        if state is None:
            return
        self._prune_messages(state, now)
        safe_text = sanitize_text(text) or "[鲸鲸刚刚回复过]"
        state.messages.append(
            GroupMessage(
                timestamp=timestamp,
                sender="鲸鲸",
                text=safe_text,
                mentions_jingjing=False,
                at_bot=False,
                is_bot=True,
                member_key="bot",
                received_monotonic=now,
            )
        )
        state.last_bot_human_count = state.human_count
        if engage:
            state.last_engaged_at = now
            state.last_engaged_member_key = member_key or None
            state.last_bot_turn_text = safe_text
            state.last_bot_turn_timestamp = timestamp
            state.last_bot_turn_received_monotonic = now

    def engagement_status(
        self,
        session: str,
        *,
        now: float,
        enabled: bool,
        timeout_seconds: int,
    ) -> tuple[bool, bool]:
        """Return (engaged, expired), lazily expiring a group's volatile state."""
        state = self._state(session)
        if state is None or state.last_engaged_at is None:
            return False, False
        if not enabled:
            return False, False
        if now - state.last_engaged_at >= max(0, int(timeout_seconds)):
            state.last_engaged_at = None
            state.last_engaged_member_key = None
            state.last_bot_turn_text = ""
            state.last_bot_turn_timestamp = None
            state.last_bot_turn_received_monotonic = None
            return False, True
        return True, False

    def engagement_context(
        self,
        session: str,
        *,
        now: float,
        timeout_seconds: int,
        recent_limit: int = 8,
    ) -> tuple[GroupMessage, ...]:
        """Retain the latest bot turn in classifier context throughout engagement."""
        state = self._state(session)
        if state is None:
            return ()
        self._prune_messages(state, now)
        recent = list(state.messages)
        last_bot = next((item for item in reversed(recent) if item.is_bot), None)
        if (
            last_bot is None
            and state.last_engaged_at is not None
            and now - state.last_engaged_at < max(0, int(timeout_seconds))
            and state.last_bot_turn_text
        ):
            last_bot = GroupMessage(
                timestamp=state.last_bot_turn_timestamp or time.time(),
                sender="鲸鲸",
                text=state.last_bot_turn_text,
                mentions_jingjing=False,
                at_bot=False,
                is_bot=True,
                member_key="bot",
                received_monotonic=state.last_bot_turn_received_monotonic or now,
            )
            recent.insert(0, last_bot)
        return select_engagement_context(recent, recent_limit=recent_limit)

    def same_as_last_engaged_user(self, session: str, member_key: str) -> bool:
        state = self._state(session)
        return bool(
            state
            and member_key
            and state.last_engaged_member_key
            and member_key == state.last_engaged_member_key
        )

    def last_bot_turn_text(self, session: str) -> str:
        state = self._state(session)
        return state.last_bot_turn_text if state else ""

    def recent(self, session: str, *, now: float) -> tuple[GroupMessage, ...]:
        state = self._state(session)
        if state is None:
            return ()
        self._prune_messages(state, now)
        return tuple(state.messages)

    def recent_human_count(self, session: str, *, now: float) -> int:
        return sum(not item.is_bot for item in self.recent(session, now=now))

    def has_unanswered_human_message(self, session: str) -> bool:
        state = self._state(session)
        return bool(state and state.human_count > state.last_bot_human_count)

    def idle_targets(self) -> tuple[tuple[str, float, float | None], ...]:
        return tuple(
            (session, state.last_activity_at, state.last_idle_attempt_at)
            for session, state in self._groups.items()
            if state.last_activity_at is not None
        )

    def mark_idle_attempt(self, session: str, *, now: float) -> bool:
        state = self._state(session)
        if state is None:
            return False
        state.last_idle_attempt_at = now
        return True

    def clear(self) -> None:
        """Drop all volatile context, aliases, and proactive targets."""
        self._groups.clear()


def is_free_talk_candidate(
    *,
    is_qq_group: bool,
    group_allowed: bool,
    is_self_message: bool,
    is_command: bool,
    is_wake_or_at: bool,
    text: str,
    recent_message_count: int,
    min_recent_messages: int,
) -> tuple[bool, bool]:
    """Return (candidate, nickname candidate) after the cheap local gate."""
    if (
        not is_qq_group
        or not group_allowed
        or is_self_message
        or is_command
        or is_wake_or_at
        or not text.strip()
    ):
        return False, False
    nickname_candidate = is_direct_nickname_address(text)
    if not nickname_candidate and recent_message_count < min_recent_messages:
        return False, False
    return True, nickname_candidate


def should_run_decision(
    *,
    nickname_candidate: bool,
    random_value: float,
    general_probability: float,
    nickname_probability: float,
) -> bool:
    probability = nickname_probability if nickname_candidate else general_probability
    return random_value < max(0.0, min(float(probability), 1.0))


def decision_says_speak(response_text: object) -> bool:
    """Fail closed unless the classifier begins with the exact SPEAK token."""
    if not isinstance(response_text, str):
        return False
    first = response_text.strip().split(maxsplit=1)
    return bool(first and first[0].strip("`*_ ").upper() == "SPEAK")


def _short_member_tag(member_key: str, used_tags: set[str]) -> str:
    digest = member_key.rsplit("_", 1)[-1]
    for length in (4, 6, 8, 12, 16):
        tag = digest[-length:].upper()
        if tag not in used_tags:
            used_tags.add(tag)
            return tag
    return digest[-16:].upper()


def format_context(
    messages: tuple[GroupMessage, ...] | list[GroupMessage],
    *,
    duplicate_member_keys: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Render a bounded speaker-attributed transcript with no platform IDs."""
    if not messages:
        return ""
    name_members: dict[str, set[str]] = {}
    for message in messages:
        if not message.is_bot and message.member_key:
            normalized = normalize_display_name(message.sender)
            if normalized:
                name_members.setdefault(normalized, set()).add(message.member_key)

    labels: dict[str, str] = {}
    used_tags: set[str] = set()
    for message in messages:
        if message.is_bot:
            continue
        member_key = message.member_key
        if member_key and member_key in labels:
            continue
        normalized = normalize_display_name(message.sender)
        duplicate_in_context = len(name_members.get(normalized, ())) > 1
        if member_key and (duplicate_in_context or member_key in duplicate_member_keys):
            labels[member_key] = (
                f"{sanitize_display_name(message.sender) or '群友'}"
                f"#{_short_member_tag(member_key, used_tags)}"
            )
        elif member_key and member_key in labels:
            continue
        elif member_key:
            labels[member_key] = sanitize_display_name(message.sender) or "群友"

    lines: list[str] = []
    for message in messages:
        if message.is_bot:
            label = "鲸鲸"
        else:
            label = labels.get(message.member_key, sanitize_display_name(message.sender) or "群友")
        # Keep each transcript entry on one line so user supplied newlines
        # cannot forge additional [speaker] records in the temporary prompt.
        text = " ".join(sanitize_text(message.text).split())
        if message.reply_target_display_name:
            target = sanitize_display_name(message.reply_target_display_name) or "群友"
            target_key = message.reply_target_member_key
            target_name_members = name_members.get(normalize_display_name(target), set())
            if (
                target_key
                and target_key != "bot"
                and target_name_members
                and (target_key not in target_name_members or len(target_name_members) > 1)
            ):
                target = f"{target}#{_short_member_tag(target_key, used_tags)}"
            elif target == "群友" and target_key and target_key != "bot":
                target = f"{target}#{_short_member_tag(target_key, used_tags)}"
            text = f"回复 [{target}]：{text}"
        lines.append(f"[{label}] {text}")
    return "\n".join(lines)


def tool_is_allowed(persona_tools: Any, tool_name: str) -> bool:
    """Mirror AstrBot v4.28.2 Persona tools semantics without mutating the Persona."""
    if persona_tools is None:
        return True
    if not isinstance(persona_tools, (list, tuple, set, frozenset)):
        return False
    return tool_name in persona_tools
