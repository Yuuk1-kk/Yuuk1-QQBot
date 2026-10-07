"""Controlled local sticker catalog and per-group repeat suppression."""

from __future__ import annotations

import random
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from pathlib import Path

STICKER_CATEGORIES = (
    "happy",
    "angry",
    "speechless",
    "smug",
    "sad",
    "confused",
    "laugh",
    "peek",
    "fatfish",
    "neutral",
)
STICKER_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
STICKER_MAX_BYTES = 8 * 1024 * 1024
TEXT_AND_STICKER = "text_and_sticker"
STICKER_ONLY = "sticker_only"


def _has_supported_signature(path: Path) -> bool:
    try:
        with path.open("rb") as image_file:
            header = image_file.read(8)
    except OSError:
        return False
    suffix = path.suffix.lower()
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    return False


def discover_stickers(
    root: Path,
    *,
    categories: tuple[str, ...] = STICKER_CATEGORIES,
    max_bytes: int = STICKER_MAX_BYTES,
) -> tuple[dict[str, tuple[Path, ...]], int]:
    """Return valid direct-child assets and the number of rejected candidates.

    Markdown and `.gitkeep` are documentation placeholders and are ignored. Paths
    are resolved under the controlled root; symlinks and oversized/invalid files
    are rejected before they can be handed to the OneBot serializer.
    """
    resolved_root = root.resolve(strict=False)
    catalog: dict[str, tuple[Path, ...]] = {}
    rejected = 0
    for category in categories:
        directory = resolved_root / category
        files: list[Path] = []
        try:
            candidates = sorted(directory.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            catalog[category] = ()
            continue
        for candidate in candidates:
            if candidate.name.lower() in {"readme.md", ".gitkeep"}:
                continue
            if candidate.name.startswith("."):
                continue
            if candidate.suffix.lower() not in STICKER_EXTENSIONS:
                rejected += 1
                continue
            try:
                resolved = candidate.resolve(strict=True)
                if (
                    candidate.is_symlink()
                    or not resolved.is_relative_to(resolved_root)
                    or not resolved.is_file()
                ):
                    rejected += 1
                    continue
                size = resolved.stat().st_size
            except OSError:
                rejected += 1
                continue
            if size <= 0 or size > max_bytes or not _has_supported_signature(resolved):
                rejected += 1
                continue
            files.append(resolved)
        catalog[category] = tuple(files)
    return catalog, rejected


class StickerCatalog:
    """Startup-scanned local assets with bounded per-session repeat history."""

    def __init__(
        self,
        catalog: Mapping[str, tuple[Path, ...]],
        *,
        history_size: int = 5,
        max_sessions: int = 200,
        categories: tuple[str, ...] = STICKER_CATEGORIES,
    ) -> None:
        self.categories = categories
        self.assets = {
            category: tuple(catalog.get(category, ())) for category in categories
        }
        self.history_size = max(1, min(int(history_size), 10))
        self.max_sessions = max(1, min(int(max_sessions), 200))
        self._recent: OrderedDict[str, deque[str]] = OrderedDict()

    @classmethod
    def scan(cls, root: Path) -> tuple[StickerCatalog, int]:
        catalog, rejected = discover_stickers(root)
        return cls(catalog), rejected

    @property
    def asset_count(self) -> int:
        return sum(len(items) for items in self.assets.values())

    def category_count(self, category: str) -> int:
        return len(self.assets.get(category, ()))

    def select(
        self,
        category: str,
        session: str,
        *,
        chooser: Callable[[list[Path]], Path] | None = None,
    ) -> tuple[Path, str] | None:
        """Pick a category asset, falling back to neutral and avoiding recent files."""
        selected_category = category if category in self.categories else "neutral"
        candidates = list(self.assets.get(selected_category, ()))
        if not candidates and selected_category != "neutral":
            selected_category = "neutral"
            candidates = list(self.assets.get(selected_category, ()))
        if not candidates:
            return None

        key = str(session or "")
        recent = self._recent.get(key)
        if recent is None:
            while len(self._recent) >= self.max_sessions:
                self._recent.popitem(last=False)
            recent = deque(maxlen=self.history_size)
            self._recent[key] = recent
        else:
            self._recent.move_to_end(key)
        recent_set = set(recent)
        fresh = [path for path in candidates if str(path) not in recent_set]
        available = fresh or candidates
        selected = (chooser or random.choice)(available)
        recent.append(str(selected))
        return selected, selected_category

    def clear(self) -> None:
        self._recent.clear()


def normalize_sticker_mode(mode: object) -> str:
    if isinstance(mode, str) and mode in {TEXT_AND_STICKER, STICKER_ONLY}:
        return mode
    return TEXT_AND_STICKER


def decoration_action(mode: str, image_available: bool) -> str:
    """Describe safe result handling without involving AstrBot message objects."""
    if not image_available:
        return "text_fallback"
    if normalize_sticker_mode(mode) == STICKER_ONLY:
        return "image_only"
    return "send_after_text"


def remove_sticker_tool_when_disabled(request: object, *, enabled: bool) -> bool:
    """Hide the sticker tool from this ProviderRequest without changing Persona."""
    if enabled:
        return False
    tool_set = getattr(request, "func_tool", None)
    remove_tool = getattr(tool_set, "remove_tool", None)
    if not callable(remove_tool):
        return False
    remove_tool("jingjing_sticker")
    return True
