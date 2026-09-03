"""Render a legacy bitmap font for Minecraft 1.12.2 from a TrueType source.

Why this exists
---------------
The reference pack `WeMine_JetBrain.zip` ships a modern TTF font provider
(`assets/minecraft/font/default.json`, `pack_format: 15`). That mechanism only
exists from Minecraft 1.13 onwards — on 1.12.2 the file is ignored outright, so
the font never applies. 1.12.2 instead reads *bitmap* glyph atlases:

    assets/minecraft/textures/font/unicode_page_XX.png   256 glyphs, 16x16 grid
    assets/minecraft/font/glyph_sizes.bin                65536 bytes, one per codepoint

This tool rasterises a TrueType source into that legacy format.

Metrics are not negotiable
--------------------------
Minecraft draws every glyph from a fixed 16x16 cell and derives spacing purely
from `glyph_sizes.bin`. A naive "centre each glyph in its cell" rasteriser
produces exactly the artefacts observed in-game: text riding above the baseline,
descenders clipped at the cell edge, and inconsistent letter spacing. Two rules
keep the output aligned with vanilla:

1. **One shared baseline.** Every glyph is positioned against a single baseline
   row measured from the vanilla unifont sheets, never centred per-glyph. Vanilla
   caps occupy rows 4..13 and descenders reach row 15, so the baseline sits at
   row 14 (exclusive), matching Mojang's own unifont rendering.
2. **One typeface for every printable UI glyph.** With `forceUnicodeFont` off,
   1.12.2 serves Basic Latin and 26 Vietnamese Latin-1 letters from Mojang's
   `ascii.png` at a larger scale, while the remaining Vietnamese letters come
   from 16x16 unicode pages at half scale. That mixes two sizes inside one word.
   The pack therefore renders printable ASCII/Latin and Vietnamese glyphs into
   unicode pages and requires `forceUnicodeFont:true`; untouched codepoints and
   widths still begin as byte-identical vanilla data.

Determinism
-----------
PNGs are written with a fixed encoder configuration and no timestamp chunks, so
repeated runs produce byte-identical output.
"""

import argparse
import io
import struct
import unicodedata
import zipfile
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Minecraft 1.12.2 renders unicode pages on a 16x16 grid of 16x16 px cells, and
# every texel of that cell is drawn — vanilla separates 'ả' from 'ã' using
# single-texel strokes, so the full resolution has to be used.
GLYPH = 16
GRID = 16
PAGE_PX = GLYPH * GRID

# Measured from the vanilla 1.12.2 unifont sheets: capitals occupy rows 4..13,
# x-height letters 6..13, descenders (g, p, q) reach row 15. Baseline is the row
# immediately below the capital/x-height body.
BASELINE = 14

# A mark row this narrow or thinner is padded; wider rows already read clearly
# and widening them merges distinct marks (breve into tilde).
TONE_MARK_THIN_ROW = 2

# Antialiased edges have no place in a bitmap atlas, so ink is thresholded on/off.
# Ink cutoff when converting the antialiased raster to a 1-bit mask. At 90 the
# faint second row of a lowercase acute/grave was discarded, leaving a single
# flat row: 'à' and 'á' then differed only by a one-column shift and read as the
# same tick in body text. 50 keeps the sloped row that gives each mark its
# direction, and every Vietnamese letter still rasterises to a unique bitmap.
INK_THRESHOLD = 50

# Extra rows rasterised below the cell, then folded into the last row so deep
# dots-below and descenders are never silently clipped away.
OVERFLOW = 4

# Extra rows rasterised ABOVE the cell. A capital carrying both a circumflex and
# a tone mark ('Ỗ', 'Ấ') stacks taller than the cell, and without headroom the
# upper mark is clipped away entirely - 'Ỗ' then rendered identically to 'Ô'.
# The ink is measured here and compressed back inside by _fit_headroom().
HEADROOM = 4

# Screen-pixel width of the redrawn dot-below. One pixel reads as no accent.
DOT_BELOW_WIDTH = 2

# Every precomposed Vietnamese letter carrying a dot below (nang).
DOT_BELOW_CHARS = frozenset(
    "ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
    "ẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ"
) & frozenset(
    chr(cp) for cp in range(0x10000)
    if "DOT BELOW" in unicodedata.name(chr(cp), "")
)

# Pages rendered from the TrueType source. Everything the UI draws must come from
# one typeface, so ASCII (page 0x00) is rendered too — see RENDER_FROM.
#   0x00 Basic Latin + Latin-1 Supplement
#   0x01 Latin Extended-A/B (d-stroke, o-horn, u-horn, ...)
#   0x1e Latin Extended Additional (the tone-marked Vietnamese block)
#   0x20 General Punctuation (en/em dash, curly quotes, ellipsis)
VIETNAMESE_PAGES = (0x00, 0x01, 0x1E, 0x20)

# First codepoint rendered from the TTF. Below this sit C0 controls only.
RENDER_FROM = 0x20

VANILLA_GLYPH_SIZES = "assets/minecraft/font/glyph_sizes.bin"
VANILLA_PAGE = "assets/minecraft/textures/font/unicode_page_{page:02x}.png"


def _png_chunk(tag, payload):
    body = tag + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def write_png_deterministic(image, path):
    """Write an RGBA PNG with no ancillary/time chunks so bytes are reproducible."""
    width, height = image.size
    raw = image.convert("RGBA").tobytes()
    stride = width * 4
    scanlines = bytearray()
    for row in range(height):
        scanlines.append(0)  # filter type 0 (None)
        scanlines.extend(raw[row * stride:(row + 1) * stride])
    blob = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), 9))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(blob)
    return len(blob)


def _thicken_tone_mark(pixels, ascent_rows=7):
    """Widen a thin tone mark until it reads as an accent, not a stray pixel.

    A bold typeface rasterised into a 16px cell puts the acute and grave down as
    a 2-texel tick, where Mojang's unifont spends 8. Against this pack's heavier
    body that tick disappears — the "accents look tiny, the nang looks missing"
    report. Widening each mark row horizontally keeps the mark's shape and angle
    (so acute still leans opposite to grave, and hook/tilde keep their profile)
    while giving it enough mass to survive at GUI scale.

    Only sparse rows are grown. A breve or tilde already spans several columns;
    padding those as well pushes different marks into the same silhouette and
    'Ă' collapses into 'Ã'. Growing only the thin rows raises the faint marks
    without touching the ones that are already legible.

    Letter bodies are never made fatter, and columns stay inside the cell so
    nothing bleeds into a neighbouring glyph.
    """
    for y in range(ascent_rows):
        row = [x for x in range(GLYPH) if pixels[x, y]]
        if not row or len(row) > TONE_MARK_THIN_ROW:
            continue
        for x in row:
            # Grow to the right where there is room, otherwise to the left, so a
            # mark already touching the cell edge still gains mass.
            if x + 1 < GLYPH and not pixels[x + 1, y]:
                pixels[x + 1, y] = 255
            elif x - 1 >= 0 and not pixels[x - 1, y]:
                pixels[x - 1, y] = 255


def _column_bounds(image, cell_x, cell_y):
    """Return (start, end_exclusive) columns of drawn pixels inside one cell."""
    left = right = None
    for x in range(GLYPH):
        if any(image.getpixel((cell_x + x, cell_y + y))[3] > 0 for y in range(GLYPH)):
            if left is None:
                left = x
            right = x
    if left is None:
        return None
    return left, right + 1


def _stamp_dot_below(pixels, columns, row):
    """Draw a deliberate two-pixel dot-below centred under the glyph body.

    Left to the rasteriser, the Vietnamese nang comes out one pixel wide — the
    same as vanilla unifont, which is what players read as "there is no dot at
    all" next to a heavy bold body. Two pixels is the narrowest mark that still
    registers as an accent at GUI scale.
    """
    if not columns:
        return
    left, right = min(columns), max(columns)
    centre = (left + right) // 2
    start = min(max(centre, 0), GLYPH - DOT_BELOW_WIDTH)
    for offset in range(DOT_BELOW_WIDTH):
        pixels[start + offset, row] = 255


def _render_master(font, char, ascent):
    """Rasterise one glyph at full 16x16 cell resolution on the shared baseline.

    The canvas is taller than the cell so a descender or dot-below is measured
    rather than silently clipped; callers decide what to do with the overflow.
    """
    master = Image.new("L", (GLYPH, HEADROOM + GLYPH + OVERFLOW), 0)
    draw = ImageDraw.Draw(master)
    left = font.getbbox(char)[0]
    draw.text((-left, HEADROOM + BASELINE - ascent), char, font=font, fill=255)
    return master.point(lambda value: 255 if value >= INK_THRESHOLD else 0)


def _fit_headroom(master):
    """Compress a too-tall stack into the cell without moving the body.

    Stacked capitals ('Ỗ', 'Ấ') rasterise above row 0. Cropping there deletes the
    upper mark and collapses the letter onto its unaccented form, and sliding the
    whole glyph down pushes the body off the shared baseline so the letter rides
    a row low next to its neighbours.

    Instead the stack is closed up from the top: every inked row above the cell is
    shifted down onto the free rows between the marks and the body, squeezing out
    the blank separator rather than the ink. The body never moves, and each mark
    keeps both its shape and its horizontal offset — the cue that separates grave
    from acute, and tilde from circumflex.
    """
    pixels = master.load()
    height = master.height
    inked = [y for y in range(height) if any(pixels[x, y] for x in range(GLYPH))]
    if not inked or inked[0] >= HEADROOM:
        return master

    rows = [
        [pixels[x, y] for x in range(GLYPH)]
        for y in range(height)
    ]
    overshoot = HEADROOM - inked[0]
    # Drop blank rows nearest the body first: those are separators, not ink.
    blanks = [
        y for y in range(inked[0], min(inked[-1], HEADROOM + GLYPH))
        if not any(rows[y])
    ]
    for y in reversed(blanks[-overshoot:] if overshoot <= len(blanks) else blanks):
        rows.pop(y)
        rows.insert(0, [0] * GLYPH)

    for y in range(height):
        for x in range(GLYPH):
            pixels[x, y] = 255 if rows[y][x] else 0
    return master


def _lift_overflow(master):
    """Pull ink that fell past the cell back inside instead of losing it.

    Runs after _fit_headroom(), so the cell occupies rows HEADROOM..HEADROOM+15
    of the taller canvas. Only the bottom rows can overflow (dots-below and
    descenders). Shifting the whole glyph up would break the shared baseline, so
    the overflowing ink is folded onto the last row of the cell, keeping the mark
    visible.
    """
    pixels = master.load()
    cell_bottom = HEADROOM + GLYPH
    for x in range(GLYPH):
        if any(pixels[x, y] for y in range(cell_bottom, cell_bottom + OVERFLOW)):
            pixels[x, cell_bottom - 1] = 255
    return master.crop((0, HEADROOM, GLYPH, cell_bottom))


def render_page(font, page, ascent, vanilla_png=None):
    """Rasterise one 256-glyph page on a shared baseline.

    Starts from the vanilla page so any codepoint this pack does not redraw keeps
    Mojang's original glyph.

    Each glyph is rasterised at the cell's full 16x16 resolution.

    renderUnicodeChar draws the 15.98-texel-tall cell into a quad 7.99 GUI units
    tall, so the texel:pixel ratio is set by guiScale: 1:1 at guiScale 2 (this
    pack's shipped default), 2:1 only at guiScale 1. Designing on a doubled 8x8
    master to survive the guiScale-1 case would throw away half the resolution in
    the case players actually run, and it collapses letters that vanilla keeps
    apart with single-texel strokes — 'ả' would equal 'ã', 'ê' would equal 'é',
    'ì' would equal 'i'. Full-resolution masters keep every letter distinct; the
    dot below is instead widened deliberately by _stamp_dot_below so it stays
    legible even when a small guiScale halves the sampling.

    Returns (image, {codepoint: (start_column, end_column_exclusive)}).
    """
    if vanilla_png is not None:
        image = Image.open(io.BytesIO(vanilla_png)).convert("RGBA")
    else:
        image = Image.new("RGBA", (PAGE_PX, PAGE_PX), (255, 255, 255, 0))
    widths = {}

    for index in range(256):
        codepoint = (page << 8) | index
        # C0/C1 controls have no glyph. Everything printable is rendered from the
        # TTF, ASCII included: Minecraft serves 26 Vietnamese letters (à á â ã è
        # é ê ì í ò ó ô õ ù ú and capitals) out of ascii.png and the rest out of
        # the unicode pages. Leaving ASCII on Mojang's sheet therefore mixes two
        # typefaces at two different sizes inside a single word.
        if codepoint < RENDER_FROM:
            continue
        char = chr(codepoint)
        if unicodedata.category(char) in ("Cn", "Cc", "Cs", "Co"):
            continue
        if not font.getmask(char).getbbox():
            continue

        # Rasterise at the cell's real 16x16 resolution. Vanilla relies on
        # single-texel strokes to separate 'ả' from 'ã' and 'ê' from 'é', so any
        # half-resolution master would collapse those letters into one shape.
        master = _lift_overflow(_fit_headroom(_render_master(font, char, ascent)))
        pixels = master.load()

        # Strengthen the tone mark before anything else looks at the glyph.
        # Decomposition is the reliable test for "this letter carries a mark" —
        # a hand-kept list drifts as coverage grows.
        if len(unicodedata.normalize("NFD", char)) > 1:
            _thicken_tone_mark(pixels)

        # Redraw the dot-below deliberately. Rasterised straight from the
        # typeface it lands as a single faint pixel that reads as no accent at
        # all under a bold body, which is the defect players reported.
        if char in DOT_BELOW_CHARS:
            for x in range(GLYPH):
                pixels[x, GLYPH - 1] = 0
            # Descenders (y, g, p, q) already occupy the row just above the dot,
            # so a mark stamped underneath fuses into the tail and the letter
            # reads unaccented — this is exactly how 'ỵ' lost its nang. Clear one
            # separating row so the dot always reads as its own mark, the way
            # vanilla spaces it.
            if any(pixels[x, GLYPH - 2] for x in range(GLYPH)):
                for x in range(GLYPH):
                    pixels[x, GLYPH - 2] = 0
            body = [
                x for x in range(GLYPH)
                if any(pixels[x, y] for y in range(GLYPH - 2))
            ]
            _stamp_dot_below(pixels, body, GLYPH - 1)

        tile = Image.new("RGBA", (GLYPH, GLYPH), (255, 255, 255, 255))
        tile.putalpha(master)

        cell_x = (index % GRID) * GLYPH
        cell_y = (index // GRID) * GLYPH
        # Replace the cell outright rather than compositing over the vanilla glyph.
        image.paste(tile, (cell_x, cell_y))

        bounds = _column_bounds(image, cell_x, cell_y)
        if bounds:
            widths[codepoint] = bounds

    return image, widths


def load_vanilla(client_jar):
    """Read vanilla glyph_sizes.bin and the pages we are about to override."""
    with zipfile.ZipFile(client_jar) as jar:
        sizes = bytearray(jar.read(VANILLA_GLYPH_SIZES))
        pages = {}
        for page in VIETNAMESE_PAGES:
            name = VANILLA_PAGE.format(page=page)
            if name in jar.namelist():
                pages[page] = jar.read(name)
    return sizes, pages


def build(ttf_path, out_dir, client_jar, size=16, pages=VIETNAMESE_PAGES):
    ttf_path = Path(ttf_path)
    out_dir = Path(out_dir)
    tex_dir = out_dir / "assets" / "minecraft" / "textures" / "font"
    font_dir = out_dir / "assets" / "minecraft" / "font"
    tex_dir.mkdir(parents=True, exist_ok=True)
    font_dir.mkdir(parents=True, exist_ok=True)

    font = ImageFont.truetype(str(ttf_path), size)
    ascent, _descent = font.getmetrics()

    # Start from the vanilla width table so untouched codepoints — all of ASCII,
    # every other script — keep their original spacing.
    glyph_sizes, vanilla_pages = load_vanilla(client_jar)

    report = {"baseline": BASELINE, "ascent": ascent, "size": size, "pages": {}}
    for page in pages:
        image, widths = render_page(font, page, ascent, vanilla_pages.get(page))
        written = write_png_deterministic(image, tex_dir / f"unicode_page_{page:02x}.png")
        for codepoint, (start, end) in widths.items():
            # The low nibble is the LAST inked column, stored inclusively —
            # verified against Mojang's own glyph_sizes.bin, where every sampled
            # glyph matches its real ink bounds exactly. FontRenderer adds the
            # +1 itself when computing the advance, so writing the exclusive
            # bound here would give every Vietnamese glyph an extra empty column
            # of width and space the text looser than the ASCII beside it.
            last_column = min(end - 1, GLYPH - 1)
            glyph_sizes[codepoint] = ((start & 0x0F) << 4) | (last_column & 0x0F)
        report["pages"][f"{page:02x}"] = {"glyphs": len(widths), "png_bytes": written}

    (font_dir / "glyph_sizes.bin").write_bytes(bytes(glyph_sizes))
    report["glyph_sizes_bytes"] = len(glyph_sizes)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ttf", required=True, help="source TrueType font")
    parser.add_argument("--out", required=True, help="output asset root")
    parser.add_argument("--client-jar", required=True, help="vanilla 1.12.2 client jar")
    parser.add_argument("--size", type=int, default=16, help="rasterisation size in px")
    args = parser.parse_args()

    import json

    print(json.dumps(build(args.ttf, args.out, args.client_jar, args.size), indent=2))


if __name__ == "__main__":
    main()
