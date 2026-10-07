# Jingjing sticker assets

Put user-provided Jingjing images in one of the category directories below.
The plugin scans this folder once when AstrBot loads it; restart AstrBot only
after adding or removing images. The NapCat container does not need to be
recreated.

Supported formats are PNG, JPG, and JPEG, limited to 8 MiB and 16 million pixels
per image. The plugin checks the file signature and decodes the image with
Pillow both during catalog scan and again before sending. GIF, WebP, SVG, remote
URLs, symlinks, and files outside this folder are not loaded.
The OneBot v11 adapter in AstrBot v4.28.2 serializes Image components as an
image segment. Jingjing Stickers v1 is VERIFIED by user-confirmed QQ E2E for
image, text + sticker, image-only, and multi-message + sticker delivery.

Categories and intended tone:

- `happy`: cheerful, light, praised, positive
- `angry`: mildly annoyed, playful protest, mock indignation
- `speechless`: speechless, exasperated, at a loss for words
- `smug`: proud, cheeky, mildly provocative
- `sad`: sad, hurt, or low-spirited
- `confused`: puzzled, unsure, or questioning
- `laugh`: laughing, amused, or cracking up
- `peek`: appearing, peeking in, or watching quietly
- `fatfish`: the “大肥鱼” joke, self-mockery, or playful protest
- `neutral`: calm, ordinary, low-intensity reaction

Only these categories are accepted; if a supported category is empty, the
plugin tries neutral. If that is empty too, the tool is hidden when the whole
gallery is empty, or the assistant keeps its text reply when a specific category
cannot be selected.

The per-category directories may remain empty. `sticker_repeat_window` defaults
to 4 (bounded from 1 to 5) and keeps only anonymous image fingerprints in
memory; it is global and clears on AstrBot restart. The model receives a
category-only tool argument and never receives a path or filename. Each bot
turn queues at most one image. Text is sent before an optional sticker; an
empty final text result can be sent as image-only.

These folders contain no generated or downloaded images. Add only images that
the account owner has permission to use.
