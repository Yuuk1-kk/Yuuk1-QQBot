# Jingjing sticker assets

Put user-provided Jingjing images in one of the category directories below.
The plugin scans this folder once when AstrBot loads it; restart AstrBot only
after adding or removing images. The NapCat container does not need to be
recreated.

Supported formats are PNG, JPG, and JPEG, limited to 8 MiB per image. GIF,
WebP, SVG, remote URLs, symlinks, and files outside this folder are not loaded.
The OneBot v11 adapter in AstrBot v4.28.2 serializes Image components as an
image segment; real QQ delivery still needs an E2E check with the provided
assets.

Categories: happy, angry, speechless, smug, sad, confused, laugh, peek, fatfish,
and neutral. If a requested category is empty, the plugin tries neutral; if
that is empty too, the assistant keeps its text reply.

These folders contain no generated or downloaded images. Add only images that
the account owner has permission to use.
