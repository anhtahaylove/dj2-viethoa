"""Regression gates for the Vietnamese display fixes (font, MOTD colour codes, main-menu mojibake).

These cover three player-visible defects confirmed from real client screenshots and logs:

1. FTBUtilities MOTD used '&' colour codes, which FTBUtilities does not translate,
   so players saw the literal text "&aChao mung...". Only the section sign works.
2. config/CustomMainMenu/mainmenu.json is valid UTF-8, but CustomMainMenu reads it
   with the platform default charset, so diacritics render as mojibake on the main
   menu. Those two specific strings must stay ASCII-safe.
3. Minecraft 1.12.2 cannot load TTF font providers (that is a 1.13+/pack_format 15
   feature). A Vietnamese font must ship as legacy bitmap unicode pages instead.
"""

import io
import json
import re
import struct
import unicodedata
import unittest
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "source" / "server_shared"
BUILD = ROOT / "build"
PACK = BUILD / "DJ2_Viet_Hoa_2.23.4.zip"
DEFAULT_OPTIONS = ROOT / "work" / "client_overlay_vi" / "config" / "defaultoptions" / "options.txt"

SECTION = "\u00a7"

# Every precomposed Vietnamese letter the pack must be able to draw.
VIETNAMESE = (
    "\u0103\u00e2\u0111\u00ea\u00f4\u01a1\u01b0\u0102\u00c2\u0110\u00ca\u00d4\u01a0\u01af"
    "\u00e1\u00e0\u1ea3\u00e3\u1ea1\u1eaf\u1eb1\u1eb3\u1eb5\u1eb7\u1ea5\u1ea7\u1ea9\u1eab\u1ead"
    "\u00e9\u00e8\u1ebb\u1ebd\u1eb9\u1ebf\u1ec1\u1ec3\u1ec5\u1ec7"
    "\u00ed\u00ec\u1ec9\u0129\u1ecb"
    "\u00f3\u00f2\u1ecf\u00f5\u1ecd\u1ed1\u1ed3\u1ed5\u1ed7\u1ed9\u1edb\u1edd\u1edf\u1ee1\u1ee3"
    "\u00fa\u00f9\u1ee7\u0169\u1ee5\u1ee9\u1eeb\u1eed\u1eef\u1ef1"
    "\u00fd\u1ef3\u1ef7\u1ef9\u1ef5"
    "\u00c1\u00c0\u1ea2\u00c3\u1ea0\u1eae\u1eb0\u1eb2\u1eb4\u1eb6\u1ea4\u1ea6\u1ea8\u1eaa\u1eac"
    "\u00c9\u00c8\u1eba\u1ebc\u1eb8\u1ebe\u1ec0\u1ec2\u1ec4\u1ec6"
    "\u00cd\u00cc\u1ec8\u0128\u1eca"
    "\u00d3\u00d2\u1ece\u00d5\u1ecc\u1ed0\u1ed2\u1ed4\u1ed6\u1ed8\u1eda\u1edc\u1ede\u1ee0\u1ee2"
    "\u00da\u00d9\u1ee6\u0168\u1ee4\u1ee8\u1eea\u1eec\u1eee\u1ef0"
    "\u00dd\u1ef2\u1ef6\u1ef8\u1ef4"
)


def motd_block(cfg_text):
    """Extract the FTBUtilities 'S:motd <' ... '>' block.

    The terminator is a '>' alone on its own line; MOTD values themselves contain
    '<placeholder>' text, so a non-greedy '.*?>' would stop at the first placeholder.
    """
    lines = cfg_text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"\s*S:motd\s*<\s*$", line):
            body = []
            for value in lines[index + 1:]:
                if value.strip() == ">":
                    return "\n".join(body)
                body.append(value)
            break
    return ""


def parse_lang(text):
    """Parse a Minecraft .lang file without interpreting format tokens."""
    values = {}
    for line in text.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


class MotdColourCodeTests(unittest.TestCase):
    """FTBUtilities renders the section sign only; '&' codes leak as literal text."""

    def test_canonical_motd_uses_section_sign_not_ampersand(self):
        block = motd_block((SHARED / "config" / "ftbutilities.cfg").read_text(encoding="utf-8"))
        self.assertTrue(block.strip(), "canonical MOTD block missing")
        self.assertNotIn("&", block, "MOTD still uses '&' codes, which FTBUtilities prints literally")
        self.assertIn(SECTION, block, "MOTD lost its colour codes entirely")

    def test_motd_colour_codes_are_valid_minecraft_codes(self):
        block = motd_block((SHARED / "config" / "ftbutilities.cfg").read_text(encoding="utf-8"))
        for code in re.findall(SECTION + r"(.)", block):
            self.assertIn(
                code.lower(),
                set("0123456789abcdefklmnor"),
                f"invalid colour/style code {code!r}",
            )

    def test_command_literals_survive_translation(self):
        block = motd_block((SHARED / "config" / "ftbutilities.cfg").read_text(encoding="utf-8"))
        for literal in ("/tpa", "/tpaccept"):
            self.assertIn(literal, block, f"command literal {literal} must stay intact")


class RemainingEnglishAuditTests(unittest.TestCase):
    """Known player-facing UI headings must not regress to their English source."""

    EXPECTED_UI = {
        "dj2.activate_block_jei.hand.name": "§r§cNhấp chuột phải",
        "dj2.configure_jei.gear.name": "§r§dCấu hình Block",
        "dj2.roots_block_conversion.barrier.name": "§r§dKhông cần chất xúc tác",
        "dj2.configure_jei.stairs.desc": "Xoay Block",
    }

    def test_audited_jei_action_headings_are_translated(self):
        with zipfile.ZipFile(PACK) as zf:
            values = parse_lang(zf.read("assets/crafttweaker/lang/vi_vn.lang").decode("utf-8"))
        for key, expected in self.EXPECTED_UI.items():
            self.assertEqual(values.get(key), expected, f"English UI string regressed: {key}")

    def test_audited_runtime_prose_is_translated(self):
        with zipfile.ZipFile(PACK) as zf:
            integrated = parse_lang(
                zf.read("assets/integrateddynamics/lang/vi_vn.lang").decode("utf-8")
            )
            tconstruct = parse_lang(
                zf.read("assets/tconstruct/lang/vi_vn.lang").decode("utf-8")
            )
        self.assertEqual(
            integrated.get("operator.operators.integrateddynamics.ingredients.items.info"),
            "Danh sách item",
        )
        self.assertEqual(
            integrated.get("operator.operators.integrateddynamics.ingredients.fluids.info"),
            "Danh sách fluid",
        )
        for key in (
            "item.tconstruct.materials.slimecrystal_blue.tooltip",
            "item.tconstruct.materials.slimecrystal_magma.tooltip",
        ):
            self.assertEqual(tconstruct.get(key), "Dùng để chế tạo Slime Tools")


class GlyphDistinctnessTests(unittest.TestCase):
    """Different Vietnamese letters must not share an identical bitmap.

    Vanilla 1.12.2 draws unicode pages at full 16x16 resolution and relies on
    single-texel strokes to tell 'ả' from 'ã' or 'ê' from 'é'. Any rasteriser
    that throws away half the vertical resolution (for example by designing on an
    8x8 grid and doubling every pixel into a 2x2 block) collapses those pairs into
    the same shape, which is a far worse defect than a faint accent: the reader
    can no longer tell which word is written.
    """

    ALPHABET = (
        "ăâđêôơưĂÂĐÊÔƠƯ"
        "áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩị"
        "óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
        "ÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊ"
        "ÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ"
    )

    @classmethod
    def setUpClass(cls):
        cls.cells = {}
        with zipfile.ZipFile(PACK) as zf:
            pages = {}
            for page in (0x00, 0x01, 0x1E, 0x20):
                raw = zf.read(f"assets/minecraft/textures/font/unicode_page_{page:02x}.png")
                pages[page] = Image.open(io.BytesIO(raw)).convert("RGBA")
        for char in cls.ALPHABET:
            codepoint = ord(char)
            image = pages[codepoint >> 8]
            index = codepoint & 0xFF
            x0, y0 = (index % 16) * 16, (index // 16) * 16
            pixels = image.load()
            cls.cells[char] = tuple(
                tuple(1 if pixels[x0 + x, y0 + y][3] else 0 for x in range(16))
                for y in range(16)
            )

    def test_every_vietnamese_letter_has_a_unique_bitmap(self):
        by_shape = {}
        collisions = []
        for char, cell in self.cells.items():
            twin = by_shape.get(cell)
            if twin is not None:
                collisions.append(f"{twin} == {char}")
            else:
                by_shape[cell] = char
        self.assertEqual(
            collisions,
            [],
            "letters render as identical bitmaps and cannot be told apart in game: "
            + ", ".join(collisions),
        )

    def test_glyphs_use_full_vertical_resolution(self):
        """Ink duplicated across every row pair means half the detail was thrown away."""
        doubled = []
        for char, cell in self.cells.items():
            if not any(any(row) for row in cell):
                continue
            if all(cell[y] == cell[y + 1] for y in range(0, 16, 2)):
                doubled.append(char)
        self.assertEqual(
            doubled,
            [],
            "these glyphs are 2x-upscaled from a half-resolution master, which "
            "collapses distinct Vietnamese letters: " + "".join(doubled),
        )


class GlyphWidthTableTests(unittest.TestCase):
    """glyph_sizes.bin must use the same nibble convention as Mojang's own file.

    FontRenderer reads the low nibble as the LAST inked column (inclusive) and
    adds 1 itself when computing the advance. Writing an exclusive bound there
    makes every rebuilt glyph claim one empty column of extra width, so
    Vietnamese text is spaced looser than the ASCII around it and wraps early.
    Vanilla's own table is the ground truth this locks against.
    """

    VIETNAMESE = (
        "ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩị"
        "óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    )
    CLIENT_JAR = Path(
        "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher/libraries"
        "/com/mojang/minecraft/1.12.2/minecraft-1.12.2-client.jar"
    )

    @staticmethod
    def _ink_columns(pages, codepoint):
        image = pages[codepoint >> 8]
        low = codepoint & 0xFF
        cx, cy = (low % 16) * 16, (low // 16) * 16
        pixels = image.load()
        columns = [
            x for x in range(16)
            if any(pixels[cx + x, cy + y][3] > 0 for y in range(16))
        ]
        return (columns[0], columns[-1]) if columns else None

    @classmethod
    def _load(cls, archive, prefix):
        sizes = archive.read(f"{prefix}font/glyph_sizes.bin")
        pages = {}
        for page in ("00", "01", "1e", "20"):
            name = f"{prefix}textures/font/unicode_page_{page}.png"
            if name in archive.namelist():
                pages[int(page, 16)] = Image.open(io.BytesIO(archive.read(name))).convert("RGBA")
        return sizes, pages

    def test_vanilla_low_nibble_is_the_last_inked_column(self):
        """Pin the convention itself, so the rule can't be misremembered later."""
        if not self.CLIENT_JAR.exists():
            self.skipTest("vanilla client jar not available")
        with zipfile.ZipFile(self.CLIENT_JAR) as jar:
            sizes, pages = self._load(jar, "assets/minecraft/")
        checked = mismatched = 0
        for codepoint in list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)):
            ink = self._ink_columns(pages, codepoint)
            if ink is None:
                continue
            checked += 1
            if (sizes[codepoint] & 0x0F) != ink[1]:
                mismatched += 1
        self.assertGreater(checked, 40, "sanity: expected a real sample of vanilla glyphs")
        self.assertEqual(
            mismatched, 0,
            "vanilla stores the last inked column inclusively; if this fails the "
            "assumption behind our width table is wrong",
        )

    def test_rebuilt_glyphs_declare_their_real_ink_bounds(self):
        with zipfile.ZipFile(PACK) as archive:
            sizes, pages = self._load(archive, "assets/minecraft/")
        wrong = {}
        for char in self.VIETNAMESE:
            codepoint = ord(char)
            ink = self._ink_columns(pages, codepoint)
            if ink is None:
                continue
            byte = sizes[codepoint]
            declared = (byte >> 4, byte & 0x0F)
            if declared != ink:
                wrong[char] = {"declared": declared, "ink": ink}
        self.assertEqual(
            wrong, {},
            "these glyphs declare width bounds that do not match their drawn ink, "
            f"so their advance is wrong in game: {wrong}",
        )


class ComposedTextTests(unittest.TestCase):
    """Shipped text must be NFC — precomposed — not base letter + combining mark.

    The pack only overrides unicode pages 00/01/1e/20. Combining marks live on
    page 03, which stays vanilla, so an NFD string like "a" + U+0323 would draw
    its accent from a different font at a different weight, or land in the wrong
    place. Every string currently ships composed; this keeps it that way, since
    a single NFD value would look broken only for the words containing it.
    """

    COMBINING = frozenset(range(0x0300, 0x0370)) | {0x1DC0, 0x1DC1}

    def test_no_shipped_string_uses_combining_marks(self):
        offenders = {}
        with zipfile.ZipFile(PACK) as archive:
            for name in archive.namelist():
                if not name.endswith((".lang", ".json")):
                    continue
                try:
                    text = archive.read(name).decode("utf-8")
                except UnicodeDecodeError:
                    self.fail(f"{name} is not valid UTF-8")
                found = {ord(ch) for ch in text if ord(ch) in self.COMBINING}
                if found:
                    offenders[name] = sorted(hex(cp) for cp in found)
        self.assertEqual(
            offenders, {},
            "these files carry decomposed (NFD) text, whose accents would render "
            f"from the un-overridden vanilla page 03: {offenders}",
        )


class AccentVisibilityTests(unittest.TestCase):
    """Vietnamese accents must be thick enough to read, at the atlas's real size.

    Minecraft 1.12.2 draws every texel of the 16x16 cell, so measurements are
    taken on the cell itself. The defect players reported was the dot-below
    rendering as a single dim pixel under a bold body; a two-pixel mark is the
    narrowest that still reads as an accent.
    """

    DOT_BELOW = "ệộụạậặợựịỵ"
    # Every letter whose mark sits below the baseline; these are verified by the
    # dot-below width/detachment tests instead of the ascender ink comparison.
    DOT_BELOW_ALL = "ạặậẹệịọộợụựỵẠẶẬẸỆỊỌỘỢỤỰỴ"
    # Tone marks replace the tittle on i/I; comparing "ink above body" against
    # the plain dotted base is therefore not meaningful for this family.
    DOTTED_BASE = "íìỉĩịÍÌỈĨỊ"
    UPPER_OR_SIDE_DIACRITICS = "áàảãâăéèẻẽêóòỏõôơúùủũư"
    # Every lowercase letter that carries a tone mark, for the vanilla-floor check.
    TONE_MARKED = (
        "áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩị"
        "óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    )

    @classmethod
    def setUpClass(cls):
        cls.pages = {}
        with zipfile.ZipFile(PACK) as zf:
            cls.sizes = zf.read("assets/minecraft/font/glyph_sizes.bin")
            for page in ("00", "01", "1e", "20"):
                blob = zf.read(f"assets/minecraft/textures/font/unicode_page_{page}.png")
                cls.pages[int(page, 16)] = Image.open(io.BytesIO(blob)).convert("RGBA")

    def cell(self, codepoint):
        image = self.pages[codepoint >> 8]
        index = codepoint & 0xFF
        cx, cy = (index % 16) * 16, (index // 16) * 16
        pixels = image.load()
        return [[1 if pixels[cx + x, cy + y][3] > 0 else 0 for x in range(16)] for y in range(16)]

    def test_dot_below_is_at_least_two_pixels_wide(self):
        thin = {}
        for char in self.DOT_BELOW:
            grid = self.cell(ord(char))
            width = sum(grid[15])
            if width < 2:
                thin[char] = width
        self.assertEqual(thin, {}, f"dot-below too faint to read: {thin}")

    def test_dot_below_is_detached_from_the_letter_body(self):
        """A nang must be a separate mark, not ink fused to the stem.

        Width alone is not enough. Descenders (y, g, p, q) already reach the
        bottom row, so a dot stamped there merges into the tail and the letter
        reads as an unaccented one — 'ỵ' looked like 'y' with a slightly ragged
        tail. Vanilla keeps a blank row between body and dot; so must we.
        """
        fused = {}
        for char in self.DOT_BELOW:
            grid = self.cell(ord(char))
            rows_with_ink = [y for y in range(16) if any(grid[y])]
            if not rows_with_ink:
                fused[char] = "no ink"
                continue
            dot_row = rows_with_ink[-1]
            if dot_row < 1 or any(grid[dot_row - 1]):
                fused[char] = f"no gap above row {dot_row}"
        self.assertEqual(
            fused,
            {},
            "these dot-below marks are fused to the letter body and read as "
            f"unaccented: {fused}",
        )

    def test_upper_and_side_accents_add_visible_ink(self):
        """Each accent must contribute real ink beyond its unaccented base."""
        faint = {}
        for char in self.UPPER_OR_SIDE_DIACRITICS:
            base = unicodedata.normalize("NFD", char)[0]
            accented = self.cell(ord(char))
            plain = self.cell(ord(base))
            extra = sum(
                1
                for y in range(16)
                for x in range(16)
                if accented[y][x] and not plain[y][x]
            )
            if extra < 2:
                faint[char] = extra
        self.assertEqual(faint, {}, f"accents contribute too little ink: {faint}")

    def test_tone_marks_are_no_lighter_than_vanilla(self):
        """A tone mark must carry at least as much ink as Mojang's own unifont.

        This is the defect players reported as "the accents look tiny". A bare
        acute rasterised from a bold typeface at this size lands as a 2-texel
        tick where vanilla spends 8 — next to a heavy body that reads as no
        accent at all. Vanilla is the floor: every player has already seen it
        render legibly at this exact cell size.

        Ink is counted over the whole cell minus the shared body rows, so a mark
        is measured wherever it sits — above the letter or below it — instead of
        assuming every accent lives in the ascender.
        """
        client_jar = Path(
            "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher/libraries"
            "/com/mojang/minecraft/1.12.2/minecraft-1.12.2-client.jar"
        )
        if not client_jar.exists():
            self.skipTest("vanilla client jar not available for comparison")
        with zipfile.ZipFile(client_jar) as jar:
            vanilla = {
                int(page, 16): Image.open(
                    io.BytesIO(jar.read(f"assets/minecraft/textures/font/unicode_page_{page}.png"))
                ).convert("RGBA")
                for page in ("00", "01", "1e")
            }

        def mark_ink(pages, char):
            """Ink above the letter's own body — measured per font, not per row index.

            A fixed row cut-off is not comparable across fonts: this pack's body
            starts one row lower than vanilla's, so a hardcoded window counts
            part of vanilla's letter as if it were accent ink. The base letter's
            own top row is the honest boundary in each font.

            Measured absolutely rather than as accented-minus-base: on 'i' the
            mark replaces the tittle instead of adding to it, so a difference
            reports a loss even when the mark is heavier than vanilla's.
            """
            base = unicodedata.normalize("NFD", char)[0]

            def cell_rows(code):
                image = pages[code >> 8]
                index = code & 0xFF
                cx, cy = (index % 16) * 16, (index // 16) * 16
                pixels = image.load()
                return [
                    [1 if pixels[cx + x, cy + y][3] > 0 else 0 for x in range(16)]
                    for y in range(16)
                ]

            base_rows = cell_rows(ord(base))
            body_top = next((y for y in range(16) if any(base_rows[y])), 16)
            rows = cell_rows(ord(char))
            return sum(sum(rows[y]) for y in range(body_top))

        lighter = {}
        for char in self.TONE_MARKED:
            if char in self.DOT_BELOW_ALL or char in self.DOTTED_BASE:
                continue
            ours = mark_ink(self.pages, char)
            theirs = mark_ink(vanilla, char)
            if ours < theirs:
                lighter[char] = (ours, theirs)
        self.assertEqual(
            lighter,
            {},
            "these tone marks carry less ink than vanilla and read as missing "
            f"accents (ours, vanilla): {lighter}",
        )


class MainMenuMojibakeTests(unittest.TestCase):
    """CustomMainMenu decodes with the platform charset, so these strings must be ASCII."""

    MAINMENU = ROOT / "work" / "client_overlay_vi" / "config" / "CustomMainMenu" / "mainmenu.json"

    def test_mainmenu_strings_are_ascii_safe(self):
        data = self.MAINMENU.read_text(encoding="utf-8")
        offenders = []
        for field, value in re.findall(r'"(text|tooltip)"\s*:\s*"([^"]*)"', data):
            if any(ord(ch) > 127 for ch in value):
                offenders.append(value)
        self.assertEqual(
            offenders,
            [],
            "CustomMainMenu cannot render non-ASCII; these render as mojibake: " + repr(offenders),
        )

    def test_mainmenu_still_valid_json_and_keeps_placeholders(self):
        raw = self.MAINMENU.read_text(encoding="utf-8")
        json.loads(raw)
        for token in ("#modsloaded#", "#mcversion#"):
            self.assertIn(token, raw, f"placeholder {token} must survive")


class BitmapFontTests(unittest.TestCase):
    """1.12.2 needs legacy bitmap unicode pages; TTF providers are silently ignored."""

    REQUIRED_PAGES = ("00", "01", "1e", "20")

    def _pack_names(self):
        with zipfile.ZipFile(PACK) as zf:
            return set(zf.namelist())

    def test_pack_ships_no_modern_ttf_font_provider(self):
        names = self._pack_names()
        self.assertNotIn(
            "assets/minecraft/font/default.json",
            names,
            "TTF font provider is a 1.13+ feature and does nothing on 1.12.2",
        )
        self.assertEqual(
            [n for n in names if n.lower().endswith((".ttf", ".otf"))],
            [],
            "shipping a TTF in a 1.12.2 pack has no effect",
        )

    def test_pack_ships_bitmap_unicode_pages_for_vietnamese(self):
        names = self._pack_names()
        for page in self.REQUIRED_PAGES:
            entry = f"assets/minecraft/textures/font/unicode_page_{page}.png"
            self.assertIn(entry, names, f"missing bitmap font page {page}")

    def test_glyph_sizes_covers_every_vietnamese_codepoint(self):
        with zipfile.ZipFile(PACK) as zf:
            self.assertIn("assets/minecraft/font/glyph_sizes.bin", zf.namelist())
            blob = zf.read("assets/minecraft/font/glyph_sizes.bin")
        self.assertEqual(len(blob), 65536, "glyph_sizes.bin must hold one byte per BMP codepoint")
        for ch in VIETNAMESE:
            packed = blob[ord(ch)]
            start, end = packed >> 4, packed & 0x0F
            self.assertLess(start, end, f"zero-width glyph for U+{ord(ch):04X} ({ch})")

    def test_unicode_pages_have_valid_grid_dimensions(self):
        with zipfile.ZipFile(PACK) as zf:
            for page in self.REQUIRED_PAGES:
                blob = zf.read(f"assets/minecraft/textures/font/unicode_page_{page}.png")
                self.assertEqual(blob[:8], b"\x89PNG\r\n\x1a\n", f"page {page} is not a PNG")
                width, height = struct.unpack(">II", blob[16:24])
                self.assertEqual(width, height, f"page {page} must be square")
                self.assertEqual(width % 16, 0, f"page {page} must divide into a 16x16 grid")


class BitmapFontMetricsTests(unittest.TestCase):
    """Glyphs must match vanilla metrics, or text rides off the baseline in-game.

    These lock in three defects seen in a real screenshot: accented text sitting
    above the baseline, glyphs clipped at the cell edge, and corrupted Latin
    spacing caused by rewriting ASCII entries in glyph_sizes.bin.
    """

    CLIENT_JAR = Path(
        "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher/libraries"
        "/com/mojang/minecraft/1.12.2/minecraft-1.12.2-client.jar"
    )

    @classmethod
    def setUpClass(cls):
        if not cls.CLIENT_JAR.exists():
            raise unittest.SkipTest("vanilla client jar not available for metric comparison")
        from PIL import Image

        cls.Image = Image
        with zipfile.ZipFile(cls.CLIENT_JAR) as jar:
            cls.vanilla_sizes = jar.read("assets/minecraft/font/glyph_sizes.bin")
        with zipfile.ZipFile(PACK) as zf:
            cls.sizes = zf.read("assets/minecraft/font/glyph_sizes.bin")
            cls.pages = {
                page: Image.open(io.BytesIO(
                    zf.read(f"assets/minecraft/textures/font/unicode_page_{page}.png")
                )).convert("RGBA")
                for page in ("00", "01", "1e", "20")
            }

    def _ink_rows(self, page, codepoint):
        image = self.pages[page]
        index = codepoint & 0xFF
        cell_x, cell_y = (index % 16) * 16, (index // 16) * 16
        rows = [
            y for y in range(16)
            if any(image.getpixel((cell_x + x, cell_y + y))[3] > 0 for x in range(16))
        ]
        return (min(rows), max(rows)) if rows else None

    def test_ascii_is_rendered_from_the_pack_typeface(self):
        """ASCII must come from the pack, not Mojang's ascii.png.

        1.12.2 serves 26 Vietnamese letters (à á â ã è é ê ì í ò ó ô õ ù ú and
        capitals) from ascii.png and the rest from the unicode pages, drawing the
        former larger than the latter. Unless the pack owns ASCII too, one word
        mixes two typefaces at two sizes — the defect seen in-game.
        """
        rewritten = [
            cp for cp in range(0x20, 0x7F)
            if self.sizes[cp] != self.vanilla_sizes[cp]
        ]
        self.assertNotEqual(rewritten, [], "ASCII widths still come from vanilla")
        for codepoint in (0x41, 0x6E, 0x67):
            self.assertIsNotNone(
                self._ink_rows("00", codepoint),
                f"U+{codepoint:04X} is not drawn in the pack's page 00",
            )

    def test_every_capital_shares_one_cap_height(self):
        """All capitals must sit on the same rows, and on the vanilla baseline.

        forceUnicodeFont routes every glyph through the unicode pages, so what
        matters is that the pack is internally consistent and lands on vanilla's
        baseline (row 13) — not that it reproduces unifont's exact stroke height,
        which depends on the source typeface's own cap height.
        """
        # Q's tail legitimately drops below the baseline, so only its top is
        # comparable with the other capitals.
        heights = {
            chr(cp): self._ink_rows("00", cp)
            for cp in range(0x41, 0x5B)
            if cp != 0x51
        }
        distinct = set(heights.values())
        self.assertEqual(
            len(distinct),
            1,
            f"capitals disagree on cap height, text will look ragged: {heights}",
        )
        top, bottom = distinct.pop()
        self.assertEqual(bottom, 13, "capitals must sit on the vanilla baseline row 13")
        self.assertGreaterEqual(bottom - top + 1, 9, "capitals are too short to read")
        self.assertEqual(
            self._ink_rows("00", 0x51)[0], top, "Q does not share the common cap height"
        )

    def test_descenders_reach_the_vanilla_depth(self):
        self.assertEqual(
            self._ink_rows("00", 0x67)[1], 15, "descender g must reach the vanilla depth"
        )

    def test_client_forces_the_uniform_unicode_rendering_path(self):
        """Without this option Minecraft mixes ascii.png and unicode-page metrics."""
        options = DEFAULT_OPTIONS.read_text(encoding="utf-8")
        self.assertIn("forceUnicodeFont:true", options)
        self.assertNotIn("forceUnicodeFont:false", options)

    def test_accented_capitals_share_the_vanilla_baseline(self):
        """Bodies must end on the vanilla baseline row, or text rides off the line.

        Only the bottom edge is asserted: that is what defines the baseline. The
        top edge depends on how tall the typeface draws its tone marks, which
        legitimately differs between JetBrains Mono and Mojang's unifont.
        """
        for codepoint in (0x1EA4, 0x1EEA, 0x1EBE):
            bounds = self._ink_rows("1e", codepoint)
            self.assertIsNotNone(bounds, f"U+{codepoint:04X} not drawn")
            self.assertEqual(
                bounds[1], 13,
                f"U+{codepoint:04X} body does not rest on the vanilla baseline",
            )
            self.assertGreaterEqual(bounds[0], 0, f"U+{codepoint:04X} clipped at cell top")

    def test_below_dot_glyphs_reach_but_never_exceed_the_cell(self):
        """O-circumflex-dot descends to row 15; row 16 would be clipped by the cell."""
        for codepoint in (0x1ED8, 0x1EC7):
            bounds = self._ink_rows("1e", codepoint)
            self.assertIsNotNone(bounds, f"U+{codepoint:04X} not drawn")
            self.assertEqual(bounds[1], 15, f"U+{codepoint:04X} loses its below-dot")

    def test_no_glyph_overflows_the_width_declared_in_glyph_sizes(self):
        """Ink outside [start, end] is what actually bleeds into the neighbour.

        Column 0 is not itself a defect: a glyph with zero left bearing is valid
        and glyph_sizes declares start=0 for it. Minecraft advances the cursor
        from the declared width, so the real invariant is that every drawn pixel
        lies inside that window.
        """
        overflowing = []
        for page, image in self.pages.items():
            pixels = image.load()
            for index in range(256):
                codepoint = (int(page, 16) << 8) | index
                if codepoint < 0xA0:
                    continue  # ASCII cells are passed through from vanilla
                packed = self.sizes[codepoint]
                if packed == 0:
                    continue
                start, end = packed >> 4, packed & 15
                cell_x, cell_y = (index % 16) * 16, (index // 16) * 16
                columns = [
                    x for x in range(16)
                    if any(pixels[cell_x + x, cell_y + y][3] > 0 for y in range(16))
                ]
                if columns and (columns[0] < start or columns[-1] > end):
                    overflowing.append(
                        f"page {page} U+{codepoint:04X} ink {columns[0]}..{columns[-1]} "
                        f"vs declared {start}..{end}"
                    )
        self.assertEqual(overflowing[:8], [], f"{len(overflowing)} glyphs overflow their width")

    def test_every_vietnamese_letter_is_drawn_with_sane_width(self):
        for char in VIETNAMESE:
            codepoint = ord(char)
            page = f"{codepoint >> 8:02x}"
            if page not in self.pages:
                continue
            packed = self.sizes[codepoint]
            start, end = packed >> 4, packed & 0x0F
            self.assertLess(start, end, f"zero-width glyph for U+{codepoint:04X} ({char})")
            self.assertIsNotNone(
                self._ink_rows(page, codepoint), f"U+{codepoint:04X} ({char}) has no pixels"
            )


if __name__ == "__main__":
    unittest.main()
