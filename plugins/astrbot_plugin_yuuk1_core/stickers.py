"""Controlled local sticker catalog and bounded repeat suppression."""

from __future__ import annotations

import hashlib
import random
import warnings
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
STICKER_MAX_PIXELS = 16_000_000
TEXT_AND_STICKER = "text_and_sticker"
STICKER_ONLY = "sticker_only"
STICKER_SEND_MODE_IMAGE = "image"
STICKER_SEND_MODE_QQ_CUSTOM = "qq_custom"
QQ_CUSTOM_IMAGE_SUB_TYPE = 1
STICKER_CATEGORY_DESCRIPTIONS = {
    "happy": "开心、轻快、被夸或积极回应",
    "angry": "轻微生气、嘴硬或被叫大肥鱼后的抗议",
    "speechless": "无语、绷不住或不知道说什么",
    "smug": "得意、嘴硬或轻微挑衅",
    "sad": "难过、委屈或低落",
    "confused": "疑惑、没听懂或问号",
    "laugh": "大笑、觉得好玩或绷不住",
    "peek": "探头、出现或偷偷看",
    "fatfish": "大肥鱼相关自嘲、抗议或鲸鲸梗",
    "neutral": "普通、平静或低强度反应",
}


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


def inspect_sticker_asset(
    path: Path,
    root: Path,
    *,
    max_bytes: int = STICKER_MAX_BYTES,
) -> tuple[Path | None, str | None]:
    """Validate a local image again before it crosses the AstrBot send boundary.

    The returned error is a safe exception-type label. It never contains a path,
    image name, or decoder message and is suitable for a warning log.
    """
    try:
        resolved_root = root.resolve(strict=True)
        candidate = Path(path)
        if candidate.is_symlink():
            return None, "UnsafePath"
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root):
            return None, "UnsafePath"
        if not resolved.is_file():
            return None, "InvalidAsset"
        suffix = resolved.suffix.lower()
        if suffix not in STICKER_EXTENSIONS:
            return None, "UnsupportedFormat"
        size = resolved.stat().st_size
        if size <= 0:
            return None, "EmptyAsset"
        if size > max_bytes:
            return None, "AssetTooLarge"
        if not _has_supported_signature(resolved):
            return None, "InvalidSignature"

        # AstrBot's Image.fromFileSystem only constructs a message component; it
        # does not decode the image. Pillow is part of the pinned v4.28.2 runtime.
        from PIL import Image as PillowImage

        expected_format = "PNG" if suffix == ".png" else "JPEG"
        with warnings.catch_warnings():
            warnings.simplefilter("error", PillowImage.DecompressionBombWarning)
            with PillowImage.open(resolved) as image:
                if image.format != expected_format:
                    return None, "InvalidImage"
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > STICKER_MAX_PIXELS:
                    return None, "InvalidImage"
                image.verify()
            # verify() checks the container structure; load() also exercises the
            # actual pixel decoder so truncated/corrupt payloads fail closed.
            with PillowImage.open(resolved) as image:
                if image.format != expected_format:
                    return None, "InvalidImage"
                image.load()
        return resolved, None
    except FileNotFoundError:
        return None, "FileNotFoundError"
    except PermissionError:
        return None, "PermissionError"
    except Exception as exc:
        error_type = type(exc).__name__
        return None, error_type if error_type.isidentifier() else "InvalidImage"


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
        if directory.is_symlink():
            catalog[category] = ()
            rejected += sum(
                item.name.lower() not in {"readme.md", ".gitkeep"}
                and not item.name.startswith(".")
                for item in candidates
            )
            continue
        for candidate in candidates:
            if candidate.name.lower() in {"readme.md", ".gitkeep"}:
                continue
            if candidate.name.startswith("."):
                continue
            if candidate.suffix.lower() not in STICKER_EXTENSIONS:
                rejected += 1
                continue
            validated, _error = inspect_sticker_asset(
                candidate,
                resolved_root,
                max_bytes=max_bytes,
            )
            if validated is None:
                rejected += 1
                continue
            files.append(validated)
        catalog[category] = tuple(files)
    return catalog, rejected


class StickerCatalog:
    """Startup-scanned assets with bounded keyed repeat history."""

    def __init__(
        self,
        catalog: Mapping[str, tuple[Path, ...]],
        *,
        history_size: int = 4,
        max_sessions: int = 200,
        categories: tuple[str, ...] = STICKER_CATEGORIES,
    ) -> None:
        self.categories = categories
        self.assets = {
            category: tuple(catalog.get(category, ())) for category in categories
        }
        self.history_size = max(1, min(int(history_size), 5))
        self.max_sessions = max(1, min(int(max_sessions), 200))
        self._recent: OrderedDict[str, deque[str]] = OrderedDict()

    @classmethod
    def scan(
        cls, root: Path, *, history_size: int = 4
    ) -> tuple[StickerCatalog, int]:
        catalog, rejected = discover_stickers(root)
        return cls(catalog, history_size=history_size), rejected

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
        """Pick a safe allowlisted asset, falling back to neutral if empty."""
        if category not in self.categories:
            return None
        selected_category = category
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
        fresh = [path for path in candidates if _asset_fingerprint(path) not in recent_set]
        if fresh:
            available = fresh
        elif len(candidates) > 1 and recent:
            latest = recent[-1]
            available = [
                path for path in candidates if _asset_fingerprint(path) != latest
            ] or candidates
        else:
            available = candidates
        selected = (chooser or random.choice)(available)
        recent.append(_asset_fingerprint(selected))
        return selected, selected_category

    def clear(self) -> None:
        self._recent.clear()


def _asset_fingerprint(path: Path) -> str:
    """Return an in-memory-only anonymous identifier for repeat suppression."""
    return hashlib.sha256(str(path.resolve(strict=False)).encode("utf-8")).hexdigest()


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
