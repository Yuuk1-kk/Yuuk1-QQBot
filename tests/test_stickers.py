from __future__ import annotations

from pathlib import Path

from plugins.astrbot_plugin_yuuk1_core.stickers import (
    STICKER_CATEGORIES,
    STICKER_ONLY,
    TEXT_AND_STICKER,
    StickerCatalog,
    decoration_action,
    discover_stickers,
    normalize_sticker_mode,
    remove_sticker_tool_when_disabled,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff\xe0"


def _write_image(path: Path, signature: bytes = PNG_SIGNATURE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(signature + b"synthetic-image-data")
    return path


def test_discovery_accepts_only_supported_signature_and_bounded_assets(
    tmp_path: Path,
) -> None:
    root = tmp_path / "stickers"
    png = _write_image(root / "happy" / "valid.png")
    jpeg = _write_image(root / "happy" / "valid.JPEG", JPEG_SIGNATURE)
    _write_image(root / "happy" / "wrong-signature.png", b"not-an-image")
    _write_image(root / "happy" / "unsupported.webp", b"RIFFxxxxWEBP")
    (root / "happy" / "notes.txt").write_text("not an image", encoding="utf-8")
    oversized = root / "happy" / "large.jpg"
    oversized.write_bytes(JPEG_SIGNATURE + b"x" * 100)
    catalog, rejected = discover_stickers(
        root,
        categories=("happy",),
        max_bytes=32,
    )
    assert catalog["happy"] == (jpeg.resolve(), png.resolve())
    assert rejected == 4


def test_discovery_skips_symlinks_and_files_outside_controlled_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "stickers"
    external = _write_image(tmp_path / "outside.png")
    category = root / "happy"
    category.mkdir(parents=True)
    link = category / "external.png"
    try:
        link.symlink_to(external)
    except (OSError, NotImplementedError):
        return
    catalog, rejected = discover_stickers(root, categories=("happy",))
    assert catalog["happy"] == ()
    assert rejected == 1


def test_category_falls_back_to_neutral_or_none_when_empty(tmp_path: Path) -> None:
    neutral = _write_image(tmp_path / "neutral" / "ok.png")
    catalog = StickerCatalog(
        {"happy": (), "neutral": (neutral.resolve(),)},
        categories=("happy", "neutral"),
    )
    selected = catalog.select("happy", "qq:group:a")
    assert selected == (neutral.resolve(), "neutral")

    empty = StickerCatalog({"happy": (), "neutral": ()}, categories=("happy", "neutral"))
    assert empty.select("happy", "qq:group:a") is None
    assert empty.asset_count == 0


def test_repeat_suppression_avoids_recent_files_and_handles_single_asset(
    tmp_path: Path,
) -> None:
    first = _write_image(tmp_path / "happy" / "one.png").resolve()
    second = _write_image(tmp_path / "happy" / "two.png").resolve()
    catalog = StickerCatalog(
        {"happy": (first, second), "neutral": ()},
        history_size=1,
        categories=("happy", "neutral"),
    )

    def chooser(options):
        return options[0]

    assert catalog.select("happy", "qq:group:a", chooser=chooser) == (
        first,
        "happy",
    )
    assert catalog.select("happy", "qq:group:a", chooser=chooser) == (
        second,
        "happy",
    )
    assert catalog.select("happy", "qq:group:b", chooser=chooser) == (
        first,
        "happy",
    )

    single = StickerCatalog(
        {"happy": (first,), "neutral": ()},
        categories=("happy", "neutral"),
    )
    assert single.select("happy", "qq:group:a", chooser=chooser) == (
        first,
        "happy",
    )
    assert single.select("happy", "qq:group:a", chooser=chooser) == (
        first,
        "happy",
    )


def test_recent_history_is_bounded_by_session_count(tmp_path: Path) -> None:
    image = _write_image(tmp_path / "happy" / "one.png").resolve()
    catalog = StickerCatalog(
        {"happy": (image,), "neutral": ()},
        max_sessions=1,
        categories=("happy", "neutral"),
    )
    catalog.select("happy", "qq:group:a")
    catalog.select("happy", "qq:group:b")
    assert list(catalog._recent) == ["qq:group:b"]


def test_modes_cover_text_only_image_only_text_plus_image_and_failure_fallback() -> None:
    assert normalize_sticker_mode(TEXT_AND_STICKER) == TEXT_AND_STICKER
    assert normalize_sticker_mode(STICKER_ONLY) == STICKER_ONLY
    assert normalize_sticker_mode([]) == TEXT_AND_STICKER
    assert decoration_action(TEXT_AND_STICKER, False) == "text_fallback"
    assert decoration_action(STICKER_ONLY, False) == "text_fallback"
    assert decoration_action(TEXT_AND_STICKER, True) == "send_after_text"
    assert decoration_action(STICKER_ONLY, True) == "image_only"


def test_disabled_sticker_tool_is_removed_only_from_current_request() -> None:
    class ToolSet:
        def __init__(self) -> None:
            self.tools = {"jingjing_sticker", "web_search"}

        def remove_tool(self, name: str) -> None:
            self.tools.discard(name)

    request = type("Request", (), {})()
    request.func_tool = ToolSet()
    assert remove_sticker_tool_when_disabled(request, enabled=False)
    assert request.func_tool.tools == {"web_search"}
    assert not remove_sticker_tool_when_disabled(request, enabled=True)
    assert request.func_tool.tools == {"web_search"}

    unsupported_request = type("Request", (), {"func_tool": None})()
    assert not remove_sticker_tool_when_disabled(unsupported_request, enabled=False)


def test_catalog_has_all_documented_categories(tmp_path: Path) -> None:
    for category in STICKER_CATEGORIES:
        (tmp_path / category).mkdir(parents=True)
    catalog, rejected = discover_stickers(tmp_path)
    assert set(catalog) == set(STICKER_CATEGORIES)
    assert rejected == 0
    assert not any(catalog.values())
