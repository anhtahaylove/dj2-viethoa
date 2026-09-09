"""Render the tone-mark reference image straight from the built font atlas.

The image in the README is the evidence a reader checks before downloading, so
it has to come from the pack that ships, not from a screenshot taken by hand.
Drawing it from build/ means it cannot drift: change the font and the picture
changes with it, or the build fails because the atlas is missing.

Each row shows one base vowel carrying every tone Vietnamese puts on it, scaled
up with nearest-neighbour so individual texels stay square and a reader can see
the blank row between a mark and the letter body.
"""
from __future__ import annotations

import io
import sys
import unicodedata
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
OUT = ROOT / "docs" / "font_tone_marks.png"

GLYPH = 16
SCALE = 4
PAD = 6
INK_ALPHA = 90

# One row per base letter, each carrying the six Vietnamese tones. The rows with
# a circumflex or a horn are the ones that stack two marks in a 16px cell, which
# is exactly where marks used to fuse into the letter.
BASES = "aâăeêioôơuưy"
TONES = ["", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323"]


def _pages() -> dict[int, Image.Image]:
    if not PACK.exists():
        raise SystemExit(f"no built pack at {PACK} -- run tools/build_pack.py first")
    pages = {}
    with zipfile.ZipFile(PACK) as pack:
        for name in pack.namelist():
            if not name.startswith("assets/minecraft/textures/font/unicode_page_"):
                continue
            quadrant = int(Path(name).stem.split("_")[-1], 16)
            pages[quadrant] = Image.open(io.BytesIO(pack.read(name))).convert("RGBA")
    if not pages:
        raise SystemExit(f"{PACK.name} carries no font atlas")
    return pages


def _cell(pages: dict[int, Image.Image], char: str) -> Image.Image | None:
    code = ord(char)
    page = pages.get(code >> 8)
    if page is None:
        return None
    index = code & 0xFF
    col, row = index % 16, index // 16
    return page.crop(
        (col * GLYPH, row * GLYPH, col * GLYPH + GLYPH, row * GLYPH + GLYPH)
    )


def _compose(base: str, tone: str) -> str | None:
    if not tone:
        return base
    composed = unicodedata.normalize("NFC", base + tone)
    return composed if len(composed) == 1 else None


def main() -> int:
    pages = _pages()

    rows: list[list[Image.Image]] = []
    for base in BASES:
        row = []
        for tone in TONES:
            char = _compose(base, tone)
            cell = _cell(pages, char) if char else None
            row.append(cell if cell is not None else Image.new("RGBA", (GLYPH, GLYPH)))
        rows.append(row)

    cell_px = GLYPH * SCALE
    width = PAD + len(TONES) * (cell_px + PAD)
    height = PAD + len(rows) * (cell_px + PAD)
    # Dark background, not transparency. The glyphs are white, so a transparent
    # sheet is invisible against GitHub's light theme and against any viewer that
    # flattens onto white -- the picture read as an empty frame.
    sheet = Image.new("RGBA", (width, height), (24, 26, 31, 255))

    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            # Nearest neighbour keeps every texel a hard square; any smoothing
            # would blur the one blank row this image exists to show.
            big = cell.resize((cell_px, cell_px), Image.NEAREST)
            sheet.paste(big, (PAD + c * (cell_px + PAD), PAD + r * (cell_px + PAD)), big)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)

    touching = []
    for base in BASES:
        for tone in TONES:
            char = _compose(base, tone)
            if not char or not tone:
                continue
            cell = _cell(pages, char)
            if cell is None:
                continue
            alpha = cell.getchannel("A").load()
            inked = [
                y for y in range(GLYPH)
                if any(alpha[x, y] > INK_ALPHA for x in range(GLYPH))
            ]
            if not inked:
                continue
            y = inked[0]
            while y < GLYPH and any(alpha[x, y] > INK_ALPHA for x in range(GLYPH)):
                y += 1
            if y > inked[-1]:
                touching.append(char)

    print(f"wrote {OUT.relative_to(ROOT).as_posix()} ({width}x{height})")
    # ơ and ư carry their tone beside the horn, so their ink runs unbroken from
    # top to bottom in Mojang's font too. Report them rather than treating them
    # as a defect.
    if touching:
        print("continuous ink (expected for ơ/ư): " + " ".join(touching))
    return 0


if __name__ == "__main__":
    sys.exit(main())
