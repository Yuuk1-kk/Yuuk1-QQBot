"""Conservative post-generation text splitting for natural QQ message sequences."""

from __future__ import annotations

import re

_PROTECTED_MARKDOWN = re.compile(
    r"```|`[^`\n]+`|https?://\S+|www\.\S+|"
    r"!?\[[^\]]+\]\([^)]*\)|"
    r"^\s{0,3}(?:#{1,6}\s|>\s|[-*+]\s|\d+[.)]\s)|"
    r"\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~",
    re.MULTILINE,
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?；;])\s*")


def split_natural_messages(
    text: str,
    *,
    enabled: bool = True,
    max_parts: int = 3,
    min_chars: int = 20,
) -> list[str]:
    """Split only explicit paragraphs or complete sentences, keeping order."""
    normalized = text.strip()
    if not normalized:
        return []
    limit = min(max(int(max_parts), 1), 3)
    if (
        not enabled
        or limit == 1
        or len(normalized) < max(0, int(min_chars))
        or _PROTECTED_MARKDOWN.search(normalized)
    ):
        return [normalized]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", normalized) if part.strip()]
    if len(paragraphs) == 1:
        lines = [part.strip() for part in normalized.splitlines() if part.strip()]
        if len(lines) > 1:
            paragraphs = lines
    if len(paragraphs) == 1:
        paragraphs = [
            part.strip()
            for part in _SENTENCE_BOUNDARY.split(normalized)
            if part.strip()
        ]
    if len(paragraphs) <= 1:
        return [normalized]

    if len(paragraphs) > limit:
        paragraphs = [
            *paragraphs[: limit - 1],
            "\n".join(paragraphs[limit - 1 :]),
        ]
    return paragraphs
