"""Conservative, request-local identity questions and deterministic replies."""

from __future__ import annotations

import re

from .group_chat import JINGJING_ALIASES

_BOT_MENTION = "\ufff0"
_QUESTION_END = "？?。"
_QUOTE_OR_CODE = frozenset("\n\r`'\"“”‘’「」『』《》<>[]【】")
_WHO = frozenset({"我是谁", "我是誰"})
_KNOW = frozenset({"你认识我吗", "你認識我嗎", "你认得我吗", "你还认得我吗"})
_OWNER = frozenset(
    {
        "我是你的主人吗",
        "我是鲸鲸的主人吗",
        "我是不是你的主人",
        "我是不是鲸鲸的主人",
    }
)
_RELATION = frozenset(
    {
        "我和你是什么关系",
        "我跟你是什么关系",
        "我们是什么关系",
        "我和鲸鲸是什么关系",
    }
)
_WHO_RELATION = re.compile(r"^(?:我是谁|我是誰)[，,？?](?:我)?和你是什么关系$")


def recognize_identity_question(
    components: object, *, self_id: object, is_group: bool
) -> str | None:
    """Accept only short direct questions made of Plain and optional bot At parts.

    Any Reply, forwarded/media component, quoted text, or ambiguous address
    leaves the message to AstrBot's ordinary chat path.
    """
    if not isinstance(components, (list, tuple)) or not components:
        return None
    self_value = str(self_id or "").strip()
    parts: list[str] = []
    mentions = 0
    for component in components:
        kind = type(component).__name__.lower().lstrip("_")
        if kind == "plain":
            text = getattr(component, "text", None)
            if not isinstance(text, str):
                return None
            parts.append(text)
        elif kind == "at":
            if (
                not self_value
                or str(getattr(component, "qq", "") or "").strip() != self_value
            ):
                return None
            mentions += 1
            parts.append(_BOT_MENTION)
        else:
            return None
    if mentions > 1:
        return None
    raw = "".join(parts).strip()
    if not raw or len(raw) > 64 or any(char in raw for char in _QUOTE_OR_CODE):
        return None
    if _BOT_MENTION in raw:
        if not raw.startswith(_BOT_MENTION):
            return None
        raw = raw[len(_BOT_MENTION) :].strip()
        if raw.startswith(tuple(JINGJING_ALIASES)):
            raw = _strip_vocative(raw)
    elif is_group:
        stripped = _strip_vocative(raw)
        if stripped == raw:
            return None
        raw = stripped
    else:
        raw = _strip_vocative(raw)

    body = "".join(raw.split()).rstrip(_QUESTION_END)
    if body in _WHO:
        return "who"
    if body in _KNOW:
        return "know"
    if body in _OWNER:
        return "owner"
    if body in _RELATION:
        return "relationship"
    if _WHO_RELATION.fullmatch(body):
        return "who_relationship"
    return None


def _strip_vocative(text: str) -> str:
    for alias in sorted(JINGJING_ALIASES, key=len, reverse=True):
        if text.startswith(alias):
            return text[len(alias) :].lstrip(" ，,、:：")
    return text


def identity_reply(
    kind: str, classification: str, display_name: str, *, is_group: bool = True
) -> str:
    """Return an identity fact without delegating it to a model."""
    if classification == "verified_owner":
        if kind == "owner":
            return "是呀，Yuuk1。主人还要鲸鲸认几遍？"
        if kind == "relationship":
            return "你是 Yuuk1，鲸鲸的主人和项目维护者呀。"
        if kind == "who_relationship":
            return "是你呀，Yuuk1。你是鲸鲸的主人，也是项目维护者。"
        return "是你呀，Yuuk1。还要鲸鲸认几遍？"

    if classification == "verified_non_owner":
        if kind == "owner":
            return "才不是呢，你不是鲸鲸的主人。"
        if kind in {"relationship", "who_relationship"}:
            relationship = "咱们是群友。" if is_group else "咱们是聊天的朋友。"
            if kind == "who_relationship" and display_name:
                return f"你现在叫{display_name}呀。{relationship}"
            return relationship
        if display_name:
            return f"你现在叫{display_name}呀。"
        return "我还不知道该怎么称呼你呢。"

    if kind in {"owner", "relationship"}:
        return "这个嘛，鲸鲸还不能确定。"
    if kind == "who_relationship":
        if display_name:
            return f"你现在叫{display_name}呀。至于咱们的关系，鲸鲸还不能确定。"
        return "鲸鲸还不能确定你的名字和咱们的关系呢。"
    if display_name:
        return f"你现在叫{display_name}呀。"
    return "鲸鲸还不知道该怎么称呼你呢。"
