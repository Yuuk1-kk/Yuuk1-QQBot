"""Trusted OneBot metadata helpers for quoted-message authorship."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ReplyOrigin(str, Enum):
    VERIFIED_BOT = "verified_bot"
    VERIFIED_MEMBER = "verified_member"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReplyQuestion:
    message_id: str
    adapter_sender_id: str


_WHO_SENT_QUESTION = re.compile(
    r"^(?:(?:那)?这|那)(?:句话|条消息|条|句)?(?:是)?(?:谁)(?:发|说)(?:的)?$"
)
_ASKS_BOT_AUTHORSHIP = re.compile(
    r"^(?:(?:那)?这|那)(?:句话|条消息|条|句)?"
    r"(?:(?:是)?你(?:刚才)?(?:发|说)(?:的)?吗|是不是你(?:刚才)?(?:发|说)(?:的)?|"
    r"(?:你(?:刚才)?(?:发|说)(?:的)?吗))$"
)
_ID = re.compile(r"^-?\d{1,20}$")
_UNTRUSTED_NESTED_COMPONENTS = frozenset({"reply", "forward", "node"})


def _normalize_id(value: object) -> str:
    if isinstance(value, bool):
        return ""
    normalized = str(value or "").strip()
    return normalized if _ID.fullmatch(normalized) and normalized != "0" else ""


def recognize_reply_sender_question(
    components: object,
    *,
    self_id: object,
) -> ReplyQuestion | None:
    """Recognize a short, direct source question attached to one QQ Reply.

    This is intentionally a small grammar tied to a platform Reply component.
    Names and quoted text are never used as source evidence.
    """
    if not isinstance(components, (list, tuple)) or not components:
        return None
    bot_id = _normalize_id(self_id)
    reply_components: list[object] = []
    text_parts: list[str] = []
    for component in components:
        kind = type(component).__name__.lower().lstrip("_")
        if kind == "reply":
            reply_components.append(component)
        elif kind == "plain":
            text = getattr(component, "text", None)
            if not isinstance(text, str):
                return None
            text_parts.append(text)
        elif kind == "at":
            if not bot_id or _normalize_id(getattr(component, "qq", None)) != bot_id:
                return None
        else:
            return None
    if len(reply_components) != 1:
        return None

    request = "".join("".join(text_parts).split()).rstrip("？?。！!")
    if len(request) > 48 or not (
        _WHO_SENT_QUESTION.fullmatch(request)
        or _ASKS_BOT_AUTHORSHIP.fullmatch(request)
    ):
        return None
    reply = reply_components[0]
    message_id = _normalize_id(getattr(reply, "id", None))
    if not message_id:
        return ReplyQuestion(message_id="", adapter_sender_id="")
    return ReplyQuestion(
        message_id=message_id,
        adapter_sender_id=_normalize_id(getattr(reply, "sender_id", None)),
    )


def classify_get_msg_result(
    response: object,
    *,
    requested_message_id: object,
    current_group_id: object,
    current_self_id: object,
    adapter_sender_id: object = "",
) -> tuple[ReplyOrigin, str]:
    """Classify a quoted message only when OneBot metadata is internally consistent."""
    requested_id = _normalize_id(requested_message_id)
    expected_group = _normalize_id(current_group_id)
    self_id = _normalize_id(current_self_id)
    adapter_sender = _normalize_id(adapter_sender_id)
    if not requested_id or not expected_group or not self_id:
        return ReplyOrigin.UNKNOWN, "missing_current_metadata"
    if not isinstance(response, dict):
        return ReplyOrigin.UNKNOWN, "invalid_response"
    if response.get("status", "ok") != "ok" or str(response.get("retcode", 0)) != "0":
        return ReplyOrigin.UNKNOWN, "action_failed"
    payload = response.get("data", response)
    if not isinstance(payload, dict):
        return ReplyOrigin.UNKNOWN, "invalid_payload"
    if _normalize_id(payload.get("message_id")) != requested_id:
        return ReplyOrigin.UNKNOWN, "message_id_mismatch"
    if str(payload.get("message_type", "")).strip().lower() != "group":
        return ReplyOrigin.UNKNOWN, "not_group_message"
    if _normalize_id(payload.get("group_id")) != expected_group:
        return ReplyOrigin.UNKNOWN, "group_mismatch_or_missing"
    payload_self_id = payload.get("self_id")
    if payload_self_id is not None and _normalize_id(payload_self_id) != self_id:
        return ReplyOrigin.UNKNOWN, "bot_mismatch"

    sender = payload.get("sender")
    sender_id = _normalize_id(sender.get("user_id")) if isinstance(sender, dict) else ""
    if not sender_id:
        return ReplyOrigin.UNKNOWN, "sender_missing"
    if adapter_sender and adapter_sender != sender_id:
        return ReplyOrigin.UNKNOWN, "sender_mismatch"

    message = payload.get("message")
    if not isinstance(message, (list, tuple)):
        return ReplyOrigin.UNKNOWN, "message_shape_unknown"
    for segment in message:
        if isinstance(segment, dict) and str(segment.get("type", "")).lower() in (
            _UNTRUSTED_NESTED_COMPONENTS
        ):
            return ReplyOrigin.UNKNOWN, "nested_or_forwarded_message"

    if sender_id == self_id:
        return ReplyOrigin.VERIFIED_BOT, "verified"
    return ReplyOrigin.VERIFIED_MEMBER, "verified"


async def fetch_reply_origin(
    call_action: Callable[..., Awaitable[Any]],
    *,
    message_id: object,
    current_group_id: object,
    current_self_id: object,
    adapter_sender_id: object = "",
) -> tuple[ReplyOrigin, str]:
    """Query the platform's official OneBot get_msg action without logging payloads."""
    normalized_id = _normalize_id(message_id)
    if not normalized_id:
        return ReplyOrigin.UNKNOWN, "reply_id_missing"
    try:
        response = await call_action(
            "get_msg",
            message_id=int(normalized_id),
            self_id=int(_normalize_id(current_self_id))
            if _normalize_id(current_self_id)
            else None,
        )
    except Exception:
        return ReplyOrigin.UNKNOWN, "lookup_failed"
    return classify_get_msg_result(
        response,
        requested_message_id=normalized_id,
        current_group_id=current_group_id,
        current_self_id=current_self_id,
        adapter_sender_id=adapter_sender_id,
    )


async def send_group_text_with_receipt(
    call_action: Callable[..., Awaitable[Any]],
    *,
    group_id: object,
    self_id: object,
    text: str,
) -> str | None:
    """Send one plain-text OneBot group message and require its returned message ID."""
    normalized_group = _normalize_id(group_id)
    normalized_self = _normalize_id(self_id)
    if not normalized_group or not normalized_self or not isinstance(text, str) or not text:
        return None
    response = await call_action(
        "send_group_msg",
        group_id=int(normalized_group),
        self_id=int(normalized_self),
        message=[{"type": "text", "data": {"text": text}}],
    )
    if not isinstance(response, dict):
        return None
    if response.get("status", "ok") != "ok" or str(response.get("retcode", 0)) != "0":
        return None
    payload = response.get("data", response)
    if not isinstance(payload, dict):
        return None
    return _normalize_id(payload.get("message_id")) or None
