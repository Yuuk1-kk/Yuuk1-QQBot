"""Conservative, request-local identity questions and deterministic replies."""

from __future__ import annotations

import re

from .group_chat import JINGJING_ALIASES

_BOT_MENTION = "\ufff0"
_QUESTION_END = "？?。"
_QUOTE_OR_CODE = frozenset("\n\r`'\"“”‘’「」『』《》<>[]【】")
_WHO = frozenset(
    {
        "我是谁",
        "我是誰",
        "那我是谁",
        "你看看我是谁",
        "那你看看我是谁",
        "看看我是谁",
        "你知道我是谁吗",
    }
)
_KNOW = frozenset({"你认识我吗", "你認識我嗎", "你认得我吗", "你还认得我吗"})
_DISPLAY_NAME = frozenset(
    {
        "读一遍我的名字",
        "你看看我名字",
        "那你看看我名字",
        "你看我名字",
        "我现在叫什么",
        "你看我现在叫什么",
    }
)
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
_SELF_REFERENCE_CUES = (
    "我是谁",
    "我是誰",
    "我名字",
    "我的名字",
    "我是你的主人",
    "我是鲸鲸的主人",
    "叫我",
    "称呼我",
    "认得我",
    "认识我",
    "看看我是谁",
)
_REPORTED_SPEECH = re.compile(r"(?:他|她|别人|有人).{0,8}(?:说|问|叫|提)")
_OWNER_DENIAL = re.compile(
    r"你(?:并|才|根本)?不是(?:我|鲸鲸)?(?:的)?主人"
    r"|真要是(?:我|鲸鲸)?(?:的)?主人"
    r"|(?:如果|要是)你(?:真|真的)?是(?:我|鲸鲸)?(?:的)?主人"
)
_NON_OWNER_GRANT = re.compile(
    r"你(?:就|才|正)?是(?:我|鲸鲸)的主人"
    r"|(?:我|鲸鲸)的主人(?:就|正)?是你"
    r"|^主人[，,!！：:]"
)
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

    body = "".join(raw.split()).rstrip(_QUESTION_END).removesuffix("呢")
    if body in _WHO:
        return "who"
    if body in _DISPLAY_NAME:
        return "display_name"
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
    if kind == "display_name":
        return f"你现在叫{display_name}呀。" if display_name else "我还不知道该怎么称呼你呢。"
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


def owner_response_correction(
    components: object,
    *,
    self_id: object,
    classification: str,
    response_text: object,
    is_group: bool = True,
) -> tuple[str, str] | None:
    """Correct only short, direct self-referential Owner contradictions.

    The current event supplies classification; no name, quote, or model text
    can grant Owner status. The caller must also verify a plain final response
    can be updated together with its persisted assistant message.
    """
    if not isinstance(components, (list, tuple)) or not components:
        return None
    if not isinstance(response_text, str) or not response_text.strip():
        return None
    if len(response_text) > 120 or any(char in response_text for char in _QUOTE_OR_CODE):
        return None

    self_value = str(self_id or "").strip()
    request_parts: list[str] = []
    for index, component in enumerate(components):
        kind = type(component).__name__.lower().lstrip("_")
        if kind == "plain" and isinstance(getattr(component, "text", None), str):
            request_parts.append(component.text)
        elif kind == "at" and index == 0 and self_value:
            if str(getattr(component, "qq", "") or "").strip() != self_value:
                return None
        else:
            return None
    request = "".join(request_parts).strip()
    if not request or len(request) > 96 or any(char in request for char in _QUOTE_OR_CODE):
        return None
    request = "".join(request.split())
    if _REPORTED_SPEECH.search(request) or not any(
        cue in request for cue in _SELF_REFERENCE_CUES
    ):
        return None

    answer = response_text.strip()
    if classification == "verified_owner" and _OWNER_DENIAL.search(answer):
        correction = (
            "好呀，老大。你是 Yuuk1，鲸鲸当然认得你。"
            if "叫我老大" in request
            else "你是 Yuuk1，鲸鲸的主人呀。"
        )
        return "owner_denied", correction
    if classification in {"verified_non_owner", "unconfigured", "unavailable"}:
        if _NON_OWNER_GRANT.search(answer):
            if classification == "verified_non_owner":
                correction = (
                    "鲸鲸的主人是 Yuuk1，咱们是群友呀。"
                    if is_group
                    else "鲸鲸的主人是 Yuuk1，我们是聊天的朋友呀。"
                )
            else:
                correction = "这个嘛，鲸鲸现在不能确认主人关系。"
            return "unverified_granted", correction
    return None
