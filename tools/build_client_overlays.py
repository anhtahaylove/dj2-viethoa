"""Build reviewed Vietnamese client-only overlay files from untouched upstream assets."""
from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:  # Text PNGs are prebuilt; config-only rebuilds do not require Pillow.
    Image = ImageDraw = ImageFont = None

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT.parent / "_upstream" / "Divine-Journey-2" / "overrides"
OVERLAY = ROOT / "work" / "client_overlay_vi"
PREBUILT_MENU = ROOT / "source" / "client_mainmenu_vi"
FONT = Path("C:/Windows/Fonts/segoeuib.ttf")
PACK_NAME = "DJ2_Viet_Hoa_2.23.4.zip"

MENU_LABELS = {
    "singleplayer.png": "CHƠI ĐƠN",
    "multiplayer.png": "CHƠI MẠNG",
    "options.png": "TÙY CHỌN",
    "mods.png": "MOD",
    "version_history.png": "LỊCH SỬ PHIÊN BẢN",
    "quit_game.png": "THOÁT GAME",
}


def _write_text(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")


def _render_sprite(source: Path, destination: Path, label: str) -> None:
    if Image is None:
        prebuilt = PREBUILT_MENU / destination.name
        if not prebuilt.exists():
            raise RuntimeError(
                f"Pillow is unavailable and prebuilt menu sprite is missing: {prebuilt}. "
                "Install Pillow to regenerate it from upstream."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(prebuilt, destination)
        return
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    frame_height = height // 2
    draw = ImageDraw.Draw(image)
    for frame_index in range(2):
        y0 = frame_index * frame_height
        frame = image.crop((0, y0, width, y0 + frame_height)).convert("RGB")
        interior = frame.crop((2, 2, width - 2, frame_height - 2))
        background = Counter(interior.getdata()).most_common(1)[0][0]
        # Preserve the original two-pixel border and both normal/hover colors.
        draw.rectangle((2, y0 + 2, width - 3, y0 + frame_height - 3), fill=background + (255,))

    max_size = 16 if width >= 200 else 13
    for size in range(max_size, 7, -1):
        font = ImageFont.truetype(str(FONT), size)
        box = draw.textbbox((0, 0), label, font=font)
        if box[2] - box[0] <= width - 14 and box[3] - box[1] <= frame_height - 8:
            break
    for frame_index in range(2):
        y0 = frame_index * frame_height
        box = draw.textbbox((0, 0), label, font=font)
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]
        x = (width - text_width) // 2 - box[0]
        y = y0 + (frame_height - text_height) // 2 - box[1]
        draw.text((x + 1, y + 1), label, font=font, fill=(92, 0, 0, 255))
        draw.text((x, y), label, font=font, fill=(185, 25, 25, 255))
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)


def build() -> set[str]:
    written: set[str] = set()

    # CustomMainMenu: preserve every action, URL, position and upstream version label.
    menu_source = UPSTREAM / "config" / "CustomMainMenu" / "mainmenu.json"
    menu = json.loads(menu_source.read_text(encoding="utf-8-sig"))
    menu["labels"]["modpack"]["text"] = "Divine Journey 2.23.4"
    # CustomMainMenu reads this file with the platform default charset instead of UTF-8,
    # so any diacritic here reaches the player as mojibake ("Mod da tai" -> "Mod Ä‘Ã£ táº£i").
    # These three strings therefore stay unaccented; every other surface renders
    # full Vietnamese through the resource pack's locale files.
    menu["buttons"]["discord"]["tooltip"] = "Tham gia may chu Discord cua Divine Journey 2!"
    menu["buttons"]["language"]["tooltip"] = "Ngon ngu"
    menu["labels"]["modsloaded"]["text"] = "#modsloaded# Mod da tai"
    menu_destination = OVERLAY / "config" / "CustomMainMenu" / "mainmenu.json"
    _write_text(menu_destination, json.dumps(menu, ensure_ascii=False, indent=4) + "\n")
    written.add(menu_destination.relative_to(OVERLAY).as_posix())

    menu_source_dir = UPSTREAM / "resources" / "mainmenu"
    menu_destination_dir = OVERLAY / "resources" / "mainmenu"
    for name, label in MENU_LABELS.items():
        destination = menu_destination_dir / name
        _render_sprite(menu_source_dir / name, destination, label)
        written.add(destination.relative_to(OVERLAY).as_posix())

    # Default Options: change only the three localization/resource-pack fields.
    options_source = UPSTREAM / "config" / "defaultoptions" / "options.txt"
    options = options_source.read_text(encoding="utf-8-sig")
    options = options.replace("resourcePacks:[]", f'resourcePacks:["{PACK_NAME}"]')
    options = options.replace("lang:en_us", "lang:vi_vn")
    # Minecraft 1.12.2 draws 26 Vietnamese letters (à á â ã è é ê ì í ò ó ô õ ù ú
    # plus capitals) from ascii.png and every other accented letter from the
    # unicode pages — and it renders ascii.png glyphs larger than unicode-page
    # glyphs. With this option off, a single word mixes both sizes. Forcing the
    # unicode path routes ALL text through the pack's own pages, so every glyph
    # comes from one typeface at one size.
    options = options.replace("forceUnicodeFont:false", "forceUnicodeFont:true")
    options_destination = OVERLAY / "config" / "defaultoptions" / "options.txt"
    _write_text(options_destination, options)
    written.add(options_destination.relative_to(OVERLAY).as_posix())

    # Crash Assistant: prefer vi_vn when options.txt is missing. The current
    # mod does not bundle vi_vn UI, so unsupported UI still falls back to en_us.
    crash_source = UPSTREAM / "config" / "crash_assistant" / "config.toml"
    crash = crash_source.read_text(encoding="utf-8-sig")
    crash = crash.replace('default_lang = "en_us"', 'default_lang = "vi_vn"')
    crash_destination = OVERLAY / "config" / "crash_assistant" / "config.toml"
    _write_text(crash_destination, crash)
    written.add(crash_destination.relative_to(OVERLAY).as_posix())

    return written


if __name__ == "__main__":
    for path in sorted(build()):
        print(path)
