from __future__ import annotations

from pathlib import Path

from PIL import Image

from plugins.astrbot_plugin_yuuk1_core.stickers import (
    STICKER_CATEGORIES,
    STICKER_CATEGORY_DESCRIPTIONS,
    STICKER_MAX_BYTES,
    STICKER_ONLY,
    TEXT_AND_STICKER,
    StickerCatalog,
    decoration_action,
    discover_stickers,
    inspect_sticker_asset,
    normalize_sticker_mode,
    remove_sticker_tool_when_disabled,
)


def _write_image(path: Path, image_format: str = "PNG") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (3, 2), color=(64, 128, 192)).save(path, format=image_format)
    return path


def test_discovery_decodes_png_jpg_and_jpeg_and_rejects_other_formats(
    tmp_path: Path,
) -> None:
    root = tmp_path / "stickers"
    png = _write_image(root / "happy" / "valid.png", "PNG")
    jpg = _write_image(root / "happy" / "valid.jpg", "JPEG")
    jpeg = _write_image(root / "happy" / "valid.JPEG", "JPEG")
    (root / "happy" / "wrong-signature.png").write_bytes(b"not-an-image")
    (root / "happy" / "unsupported.webp").write_bytes(b"RIFFxxxxWEBP")
    (root / "happy" / "unsupported.gif").write_bytes(b"GIF89a")
    (root / "happy" / "unsupported.svg").write_text("<svg/>", encoding="utf-8")
    (root / "happy" / "notes.txt").write_text("not an image", encoding="utf-8")
    (root / "happy" / "corrupt.png").write_bytes(b"\x89PNG\r\n\x1a\ninvalid")

    catalog, rejected = discover_stickers(root, categories=("happy",))

    assert catalog["happy"] == tuple(sorted((png.resolve(), jpg.resolve(), jpeg.resolve())))
    assert rejected == 6


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


def test_invalid_category_is_rejected_but_empty_supported_category_uses_neutral(
    tmp_path: Path,
) -> None:
    neutral = _write_image(tmp_path / "neutral" / "ok.png").resolve()
    catalog = StickerCatalog(
        {"happy": (), "neutral": (neutral,)},
        categories=("happy", "neutral"),
    )
    assert catalog.select("../../outside", "global") is None
    assert catalog.select("happy", "global") == (neutral, "neutral")

    empty = StickerCatalog({"happy": (), "neutral": ()}, categories=("happy", "neutral"))
    assert empty.select("happy", "global") is None
    assert empty.asset_count == 0


def test_send_boundary_validation_rejects_outside_corrupt_empty_and_oversized_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "stickers"
    valid = _write_image(root / "happy" / "valid.png")
    corrupt = root / "happy" / "corrupt.png"
    corrupt.write_bytes(b"\x89PNG\r\n\x1a\nnot-decodable")
    empty = root / "happy" / "empty.jpg"
    empty.write_bytes(b"")
    missing = root / "happy" / "missing.png"
    oversized = root / "happy" / "large.jpg"
    oversized.write_bytes(b"\xff\xd8\xff" + b"x" * STICKER_MAX_BYTES)
    outside = _write_image(tmp_path / "outside.png")

    assert inspect_sticker_asset(valid, root) == (valid.resolve(), None)
    assert inspect_sticker_asset(corrupt, root)[0] is None
    assert inspect_sticker_asset(empty, root) == (None, "EmptyAsset")
    assert inspect_sticker_asset(missing, root) == (None, "FileNotFoundError")
    assert inspect_sticker_asset(oversized, root) == (None, "AssetTooLarge")
    escaped, reason = inspect_sticker_asset(outside, root)
    assert escaped is None
    assert reason == "UnsafePath"


def test_repeat_suppression_rotates_assets_and_keeps_only_anonymous_ids(
    tmp_path: Path,
) -> None:
    first = _write_image(tmp_path / "happy" / "one.png").resolve()
    second = _write_image(tmp_path / "happy" / "two.png").resolve()
    catalog = StickerCatalog(
        {"happy": (first, second), "neutral": ()},
        history_size=1,
        categories=("happy", "neutral"),
    )

    def chooser(options: list[Path]) -> Path:
        return options[0]

    assert catalog.select("happy", "global", chooser=chooser) == (first, "happy")
    assert catalog.select("happy", "global", chooser=chooser) == (second, "happy")
    assert catalog.select("happy", "another-call", chooser=chooser) == (first, "happy")
    assert all(str(first) not in key and str(second) not in key for key in catalog._recent["global"])

    single = StickerCatalog(
        {"happy": (first,), "neutral": ()},
        categories=("happy", "neutral"),
    )
    assert single.select("happy", "global", chooser=chooser) == (first, "happy")
    assert single.select("happy", "global", chooser=chooser) == (first, "happy")

    two_assets = StickerCatalog(
        {"happy": (first, second), "neutral": ()},
        history_size=4,
        categories=("happy", "neutral"),
    )
    assert two_assets.select("happy", "global", chooser=chooser) == (first, "happy")
    assert two_assets.select("happy", "global", chooser=chooser) == (second, "happy")
    assert two_assets.select("happy", "global", chooser=chooser) == (first, "happy")


def test_recent_history_is_bounded_by_session_count_and_window(tmp_path: Path) -> None:
    image = _write_image(tmp_path / "happy" / "one.png").resolve()
    catalog = StickerCatalog(
        {"happy": (image,), "neutral": ()},
        history_size=99,
        max_sessions=1,
        categories=("happy", "neutral"),
    )
    assert catalog.history_size == 5
    catalog.select("happy", "group-a")
    catalog.select("happy", "group-b")
    assert list(catalog._recent) == ["group-b"]


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


def test_catalog_has_all_documented_categories_and_empty_gallery_is_valid(
    tmp_path: Path,
) -> None:
    for category in STICKER_CATEGORIES:
        (tmp_path / category).mkdir(parents=True)
    catalog, rejected = discover_stickers(tmp_path)
    assert set(catalog) == set(STICKER_CATEGORIES)
    assert set(STICKER_CATEGORY_DESCRIPTIONS) == set(STICKER_CATEGORIES)
    assert all(STICKER_CATEGORY_DESCRIPTIONS.values())
    assert rejected == 0
    assert not any(catalog.values())
