# Bitmap font source

`JetBrainsMono-Bold.ttf` is extracted from the user-supplied reference pack
`Reference/WeMine_JetBrain.zip` (JetBrains Mono Bold, Apache License 2.0 — see
`JetBrainsMono-LICENSE.txt`).

That reference pack targets `pack_format: 15` and declares a TTF font provider in
`assets/minecraft/font/default.json`. TTF providers only exist from Minecraft 1.13
onwards, so on 1.12.2 the file is ignored and the font never applies. `tools/build_bitmap_font.py`
rasterises this same typeface into the legacy bitmap format 1.12.2 actually reads
(`unicode_page_XX.png` + `glyph_sizes.bin`).

Verified coverage: all 134 precomposed Vietnamese letters plus full ASCII and the
section sign are present in the source font's cmap.
