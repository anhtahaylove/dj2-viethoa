"""Render a before/after comparison image using the pack's own bitmap font.

Usage:
    python make_compare.py <pairs.json> <output.png> [heading]

`pairs.json` is a list of [english, vietnamese] pairs. Text is drawn from the
resource pack's unicode_page_XX.png atlases so the Vietnamese side shows the
exact glyphs a player sees in game, rather than a desktop font that would
misrepresent the result.

Two font traps this handles (see the pipeline skill):
  * U+0020 is NOT blank in this atlas — its cell carries ink and would render
    as a solid block, so space is special-cased as advance-only.
  * Each glyph needs +1px advance or adjacent letters touch.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(r'C:/huuhungn/huuhungn-PC/mc_server_pack/dj2-viethoa')
PACK = ROOT / 'build' / 'DJ2_Viet_Hoa_2.23.4.zip'

SCALE = 2
PAD = 28
ROW_GAP = 22
COL_GAP = 40

BG = (24, 24, 27)
PANEL_EN = (39, 39, 42)
PANEL_VI = (30, 41, 38)
FG = (228, 228, 231)
DIM = (150, 150, 158)
ACCENT = (74, 222, 128)


class PackFont:
    """Draws text using the resource pack's unicode_page_XX.png atlases."""

    def __init__(self, zf):
        self.zf = zf
        self.pages = {}
        self.sizes = zf.read('assets/minecraft/font/glyph_sizes.bin')

    def page(self, index):
        if index not in self.pages:
            name = f'assets/minecraft/textures/font/unicode_page_{index:02x}.png'
            try:
                data = self.zf.read(name)
            except KeyError:
                return None
            self.pages[index] = Image.open(io.BytesIO(data)).convert('RGBA')
        return self.pages[index]

    def glyph(self, ch):
        # U+0020's cell is not empty in this atlas; drawing it yields a block.
        if ch == ' ':
            return None, 8

        cp = ord(ch)
        page = self.page(cp >> 8)
        if page is None:
            return None, 8
        idx = cp & 0xFF
        col, row = idx % 16, idx // 16
        cell = page.crop((col * 16, row * 16, col * 16 + 16, row * 16 + 16))

        packed = self.sizes[cp] if cp < len(self.sizes) else 0x0F
        start, end = packed >> 4, (packed & 0x0F) + 1
        width = max(1, end - start)
        if cell.getbbox() is None:
            return None, width
        return cell.crop((start, 0, start + width, 16)), width + 1

    def measure(self, text):
        return sum(self.glyph(c)[1] for c in text) * SCALE

    def draw(self, canvas, xy, text, colour):
        x, y = xy
        for ch in text:
            bitmap, width = self.glyph(ch)
            if bitmap is not None:
                big = bitmap.resize(
                    (bitmap.width * SCALE, bitmap.height * SCALE), Image.NEAREST
                )
                tint = Image.new('RGBA', big.size, colour + (255,))
                canvas.paste(tint, (int(x), int(y)), big)
            x += width * SCALE
        return x


def render(pairs, out_path, heading='VIET HOA 2.23.4'):
    with zipfile.ZipFile(PACK) as zf:
        font = PackFont(zf)
        line_h = 16 * SCALE

        col_w = max(
            max(font.measure(en) for en, _ in pairs),
            max(font.measure(vi) for _, vi in pairs),
        ) + PAD * 2

        header_h = line_h + 18
        body_h = len(pairs) * (line_h + ROW_GAP)
        width = PAD + col_w + COL_GAP + col_w + PAD
        height = PAD + header_h + body_h + PAD

        img = Image.new('RGB', (width, height), BG)
        draw = ImageDraw.Draw(img)

        left_x, right_x = PAD, PAD + col_w + COL_GAP
        top = PAD + header_h

        draw.rounded_rectangle(
            [left_x - 12, top - 14, left_x + col_w - 12, top + body_h - 6],
            radius=10, fill=PANEL_EN,
        )
        draw.rounded_rectangle(
            [right_x - 12, top - 14, right_x + col_w - 12, top + body_h - 6],
            radius=10, fill=PANEL_VI,
        )

        font.draw(img, (left_x, PAD), 'GOC / ORIGINAL', DIM)
        font.draw(img, (right_x, PAD), heading, ACCENT)

        y = top
        for en, vi in pairs:
            font.draw(img, (left_x, y), en, DIM)
            font.draw(img, (right_x, y), vi, FG)
            y += line_h + ROW_GAP

        img.save(out_path)
        return img.size


def verify(path):
    """Assert word gaps exist — catches the solid-space regression."""
    import re

    img = Image.open(path).convert('RGB')
    w, h = img.size
    mid = w // 2
    rows = [y for y in range(h) if any(img.getpixel((x, y)) == FG for x in range(mid, w))]
    if not rows:
        return 0
    start = rows[0]
    end = start
    for y in rows:
        if y - end <= 2:
            end = y
        else:
            break
    cols = [
        sum(1 for y in range(start, end + 1) if img.getpixel((x, y)) == FG)
        for x in range(mid, w)
    ]
    line = ''.join('.' if v == 0 else '#' for v in cols)
    return sum(1 for m in re.finditer(r'\.+', line) if 6 <= len(m.group()) <= 40)


if __name__ == '__main__':
    pairs_file, out_file = sys.argv[1], sys.argv[2]
    heading = sys.argv[3] if len(sys.argv) > 3 else 'VIET HOA 2.23.4'
    pairs = [tuple(p) for p in json.loads(Path(pairs_file).read_text(encoding='utf-8'))]

    size = render(pairs, out_file, heading)
    gaps = verify(out_file)
    print(f'{out_file}  {size[0]}x{size[1]}  word gaps: {gaps}')
    if gaps == 0:
        raise SystemExit('FAIL: no word gaps — space glyph regression')
