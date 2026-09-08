"""Flag Vietnamese button labels wider than any official translation of the same mod.

Minecraft 1.12.2 draws a GuiButton at a fixed width; a label that overruns it is
clipped or spills past the border. There is no way to read that width from the
.lang files, so this uses the mods' own shipped translations as the reference:
if de_de, pt_br, ru_ru or ko_kr already render a label at N pixels inside a
mod's button, the button demonstrably tolerates N pixels, and a Vietnamese label
under that is safe.

Widths come from the pack's own glyph_sizes.bin, using FontRenderer's unicode
path (the pack forces forceUnicodeFont:true, so every glyph is measured there).

Not a build gate: the reference is evidence, not a specification. It prints a
report so a human can judge the outliers.
"""
from pathlib import Path
import json, re, sys, zipfile, collections

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "release/DJ2_Viet_Hoa_2.23.4/DJ2_Viet_Hoa_2.23.4.zip"
from instance_paths import mods_dir

MODS = mods_dir(required=False) or Path("mods-not-installed")
PAIRS = (
    ("work/runtime_locale_sources", "work/translated/runtime_locales"),
    ("source/tooltips", "work/translated/tooltips"),
)
# Keys that land inside a fixed-width button. `.info` keys are floating
# tooltips, which wrap on their own and cannot overrun anything.
BUTTON = re.compile(r"(^button\.|\.button\.)", re.I)
FLOATING = re.compile(r"\.(info|tooltip|desc\d*|text\d*|line\d+)$", re.I)

# Keys that merely *look* like button faces. Verified against the mod bytecode:
# Guide-API's four navigation buttons are 18x10 texture sprites, and these keys
# are returned by ButtonBack/ButtonSearch/ButtonPrev/ButtonNext.getHoveringText(),
# i.e. they render as a floating hover tooltip, not inside the button. Measuring
# them against the sprite width produces a false overflow.
# (javap -c amerifrance/guideapi/button/Button*.class, Guide-API-1.12-2.1.8-63.jar)
NOT_BUTTON_FACE = {
    ("guideapi", "button.back.name"),
    ("guideapi", "button.search.name"),
    ("guideapi", "button.prev.name"),
    ("guideapi", "button.next.name"),
}


def load_glyph_widths():
    with zipfile.ZipFile(PACK) as z:
        return z.read("assets/minecraft/font/glyph_sizes.bin")


def make_measurer(glyphs):
    def char_width(ch):
        code = ord(ch)
        if code == 0xA7:                      # the section sign itself
            return -1
        if ch == " " or code == 0xA0:         # hardcoded in FontRenderer
            return 4
        if code >= len(glyphs):
            return 0
        packed = glyphs[code]
        if packed == 0:
            return 0
        start, end = packed >> 4, (packed & 15) + 1
        return (end - start) // 2 + 1         # unicode path halves the advance

    def width(text):
        total, i = 0, 0
        while i < len(text):
            if text[i] == "\u00a7":           # skip the code AND its argument
                i += 2
                continue
            total += char_width(text[i])
            i += 1
        return total

    return width


def parse_lang(text):
    out = {}
    for line in text.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        out.setdefault(key.strip(), value.strip())
    return out


def official_translations():
    """Every non-English .lang shipped inside the mod jars, keyed by lang key."""
    out = collections.defaultdict(dict)
    for jar in sorted(MODS.glob("*.jar")):
        # A jar that will not open costs this gate every official translation
        # inside it. Skipping quietly leaves the gate green while it silently
        # compares against less than it thinks, so stop and name the file.
        try:
            z = zipfile.ZipFile(jar)
        except (zipfile.BadZipFile, OSError) as exc:
            raise SystemExit(f"cannot read mod jar {jar.name}: {exc}") from exc
        for name in z.namelist():
            m = re.search(r"/lang/([a-z]{2}_[a-z]{2})\.lang$", name, re.I)
            if not m:
                continue
            code = m.group(1).lower()
            if code in ("en_us", "en_ud"):    # en_ud is upside-down joke text
                continue
            try:
                text = z.read(name).decode("utf-8", errors="replace")
            except (zipfile.BadZipFile, OSError) as exc:
                raise SystemExit(f"cannot read {name} from {jar.name}: {exc}") from exc
            for key, value in parse_lang(text).items():
                out[key].setdefault(code, value)
    return out


def main():
    width = make_measurer(load_glyph_widths())
    official = official_translations()
    per_mod = collections.defaultdict(
        lambda: {"reference": 0, "widest_vi": 0, "worst": None}
    )
    for source_dir, target_dir in PAIRS:
        for lang_path in sorted((ROOT / source_dir).glob("*.lang")):
            json_path = ROOT / target_dir / f"{lang_path.stem}.json"
            if not json_path.exists():
                continue
            source = parse_lang(lang_path.read_text(encoding="utf-8"))
            target = json.loads(json_path.read_text(encoding="utf-8"))
            mod = lang_path.stem
            for key, vietnamese in target.items():
                english = source.get(key)
                if english is None or not BUTTON.search(key) or FLOATING.search(key):
                    continue
                if (mod, key) in NOT_BUTTON_FACE:
                    continue
                for value in official.get(key, {}).values():
                    if value != english:      # untranslated copies prove nothing
                        per_mod[mod]["reference"] = max(
                            per_mod[mod]["reference"], width(value)
                        )
                vi_width = width(vietnamese)
                if vi_width > per_mod[mod]["widest_vi"]:
                    per_mod[mod]["widest_vi"] = vi_width
                    per_mod[mod]["worst"] = (key, vietnamese)

    report, over = {}, []
    for mod, stats in sorted(per_mod.items()):
        entry = {
            "reference_px": stats["reference"],
            "widest_vi_px": stats["widest_vi"],
            "widest_key": stats["worst"][0] if stats["worst"] else None,
            "widest_value": stats["worst"][1] if stats["worst"] else None,
        }
        if stats["reference"] and stats["widest_vi"] > stats["reference"]:
            entry["verdict"] = f"over by {stats['widest_vi'] - stats['reference']}px"
            over.append(mod)
        elif not stats["reference"]:
            entry["verdict"] = "no official translation to compare against"
        else:
            entry["verdict"] = "within proven width"
        report[mod] = entry
    print(json.dumps({"report": report, "over_reference": over}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
