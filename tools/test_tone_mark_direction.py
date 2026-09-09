"""Tone marks must carry direction, not just presence.

The size 13 / threshold 90 build rasterised lowercase grave and acute into a
single flat row each, so they differed only by a one-column horizontal shift and
a player reading body text saw the same tick on 'à' and 'á'. Capitals were fine
because their marks kept two rows. These tests fail on that build and pass once
the raster keeps real vertical structure.
"""
import io
import unicodedata
import unittest
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
GLYPH = 16
INK_ALPHA = 90

VOWELS = "aăâeêioôơuưy"
GRAVE = "\u0300"
ACUTE = "\u0301"
HOOK = "\u0309"
TILDE = "\u0303"


def _pages():
    pages = {}
    with zipfile.ZipFile(PACK) as pack:
        for quadrant in (0x00, 0x01, 0x1E, 0x20):
            name = f"assets/minecraft/textures/font/unicode_page_{quadrant:02x}.png"
            pages[quadrant] = Image.open(io.BytesIO(pack.read(name))).convert("RGBA")
    return pages


# This module reads the built pack, and building it needs the vanilla client
# jar for font metrics -- available on a workstation with the game installed,
# not on CI. Skip there rather than erroring at import time, so the rest of
# the suite still runs. Every other test works from sources in the repository.
if PACK.exists():
    PAGES = _pages()
else:
    PAGES = None
    raise unittest.SkipTest(f"pack not built: {PACK}")


def mask(char):
    """Boolean ink mask of one glyph cell."""
    code = ord(char)
    page = PAGES[code >> 8]
    index = code & 0xFF
    x0, y0 = (index % 16) * GLYPH, (index // 16) * GLYPH
    cell = page.crop((x0, y0, x0 + GLYPH, y0 + GLYPH))
    return [
        [cell.getpixel((x, y))[3] > INK_ALPHA for x in range(GLYPH)]
        for y in range(GLYPH)
    ]


def compose(base, mark):
    combined = unicodedata.normalize("NFC", base + mark)
    return combined if len(combined) == 1 else None


def mark_band_centre(char):
    """Horizontal centre of the topmost accent row.

    Compares two accented siblings against each other rather than against a base
    glyph: subtracting the base is unreliable because adding a tone mark can push
    a breve or circumflex down a row, and the diff then reports that displaced
    mark instead of the accent under test.

    Only the single topmost inked row is measured. On a stacked letter such as
    'ầ' the tone mark sits on top and the circumflex directly beneath it, so
    averaging both rows blends the two marks and hides the difference.
    """
    bitmap = mask(char)
    for y in range(GLYPH):
        columns = [x for x in range(GLYPH) if bitmap[y][x]]
        if columns:
            return (min(columns) + max(columns)) / 2
    return None


class ToneMarkDirectionTests(unittest.TestCase):
    """Grave and acute must lean in opposite directions on every vowel."""

    def test_lowercase_marks_have_vertical_structure(self):
        """Every accent must occupy at least two rows above the letter body.

        Measured on the glyph itself: the ink above the x-height gap is the mark.
        Subtracting the base letter cannot be used here because a mark often
        shifts the body or the dot of an 'i' by a row.
        """
        flat = []
        for vowel in VOWELS:
            for mark in (GRAVE, ACUTE, HOOK, TILDE):
                char = compose(vowel, mark)
                if char is None:
                    continue
                bitmap = mask(char)
                inked = [
                    y for y in range(GLYPH)
                    if any(bitmap[y][x] for x in range(GLYPH))
                ]
                if not inked:
                    flat.append(f"{char} renders blank")
                    continue
                band = []
                for y in inked:
                    if band and y > band[-1] + 1:
                        break
                    band.append(y)
                if len(band) < 2:
                    flat.append(f"{char} has a {len(band)}-row accent")
        self.assertEqual(
            flat,
            [],
            "a one-row tone mark reads as a stray tick and cannot show direction, "
            "so the reader cannot tell one accent from another: " + "; ".join(flat),
        )

    def test_grave_and_acute_lean_opposite_ways(self):
        wrong = []
        for vowel in VOWELS:
            low_grave = compose(vowel, GRAVE)
            low_acute = compose(vowel, ACUTE)
            if low_grave is None or low_acute is None:
                continue
            grave_centre = mark_band_centre(low_grave)
            acute_centre = mark_band_centre(low_acute)
            if grave_centre is None or acute_centre is None:
                continue
            if not grave_centre < acute_centre:
                wrong.append(
                    f"{low_grave}={grave_centre:.1f} {low_acute}={acute_centre:.1f}"
                )
        self.assertEqual(
            wrong,
            [],
            "the grave must sit further left than the acute or the two accents "
            "are indistinguishable: " + "; ".join(wrong),
        )

    def test_uppercase_marks_keep_direction_too(self):
        wrong = []
        for vowel in VOWELS:
            upper = vowel.upper()
            cap_grave = compose(upper, GRAVE)
            cap_acute = compose(upper, ACUTE)
            if cap_grave is None or cap_acute is None:
                continue
            grave_centre = mark_band_centre(cap_grave)
            acute_centre = mark_band_centre(cap_acute)
            if grave_centre is None or acute_centre is None:
                continue
            if not grave_centre < acute_centre:
                wrong.append(
                    f"{cap_grave}={grave_centre:.1f} {cap_acute}={acute_centre:.1f}"
                )
        self.assertEqual(wrong, [], "; ".join(wrong))

    def test_every_accented_letter_stays_distinct(self):
        seen = {}
        collisions = []
        for vowel in VOWELS:
            for base in (vowel, vowel.upper()):
                for mark in ("", GRAVE, ACUTE, HOOK, TILDE, "\u0323"):
                    char = base if mark == "" else compose(base, mark)
                    if char is None:
                        continue
                    key = tuple(tuple(row) for row in mask(char))
                    if key in seen and seen[key] != char:
                        collisions.append(f"{seen[key]} == {char}")
                    seen[key] = char
        self.assertEqual(
            collisions,
            [],
            "two different letters render as the same bitmap: " + "; ".join(collisions),
        )

    def test_stacked_marks_keep_a_gap_above_the_letter(self):
        """A tone stacked over a circumflex must not fuse into the letter body.

        'Ấ' is a capital A, a circumflex and an acute in a 16px cell. Rasterised
        one point too large the three run together and the screenshot reads as a
        bold blob with no accent — the "dấu dính vào chữ" report. The letters
        listed below each carry a two-mark stack, and every one of them must show
        at least one blank row between the marks and the body.

        ơ/ư are excluded on purpose: their tone sits beside the horn rather than
        above it, so their ink is continuous top to bottom in Mojang's font too.
        """
        fused = []
        for char in "ẢẦẤẨẪẬỀẾỂỄỆỒỐỔỖỘàáảãạẦẤỀẾỒỐ":
            rows = mask(char)
            inked = [y for y, row in enumerate(rows) if any(row)]
            if not inked:
                continue
            y = inked[0]
            while y < len(rows) and any(rows[y]):
                y += 1
            if y > inked[-1]:
                fused.append(char)
        self.assertEqual(
            fused,
            [],
            "tone mark touches the letter body: " + " ".join(fused),
        )


if __name__ == "__main__":
    unittest.main()
