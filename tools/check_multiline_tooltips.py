"""Check that multi-line tooltips still break sensibly after translation.

A tooltip splits on the literal two-character sequence \\n. Vietnamese runs
1.3-2x wider than English, so a segment that fit on one line in English can
overflow -- but only where the frame is FIXED. Most long strings self-wrap and
their apparent "width" is meaningless.

Telling the two apart is the whole problem. The test: if the ENGLISH source
already has a segment wider than any Minecraft screen, that string is
self-wrapping by construction and \\n only marks paragraphs. Blood Magic's guide
book ships a 4112px source line -- no frame is that wide.

For the fixed-frame remainder, the threshold comes from the mod's OWN official
translations (any Latin locale), never a number invented here: if de_de already
renders 434px on that key, the frame tolerates 434px.

Run:  python tools/check_multiline_tooltips.py
"""
from pathlib import Path
import collections
import json
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "release/DJ2_Viet_Hoa_2.23.4/DJ2_Viet_Hoa_2.23.4.zip"
INSTANCE = Path(
    "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher/instances/"
    "Divine Journey 2/minecraft"
)
PAIRS = (
    ("work/runtime_locale_sources", "work/translated/runtime_locales"),
    ("source/tooltips", "work/translated/tooltips"),
)
CODES = re.compile(r"§.|&[0-9a-fk-orA-FK-OR]")
# Widest sane fixed frame. A source segment above this self-wraps in game, so
# the string is prose and its segment widths carry no layout meaning.
SELF_WRAP_PX = 340
# Comparing against Han/Kana is unfair -- those scripts are far more compact
# than any alphabet, which would set an artificially low ceiling.
LATIN_LOCALES = {
    "de_de", "fr_fr", "es_es", "it_it", "pt_br", "ru_ru", "pl_pl", "nl_nl",
    "sv_se", "cs_cz", "tr_tr", "hu_hu", "fi_fi", "da_dk", "nb_no", "ro_ro",
    "uk_ua", "pt_pt", "es_mx", "el_gr", "bg_bg", "sk_sk",
}
# A reference built from only a couple of official keys is noise, not a ceiling.
MIN_REFERENCE_KEYS = 4


def glyph_widths():
    """Raw glyph_sizes.bin from the built pack (forceUnicodeFont is on)."""
    with zipfile.ZipFile(PACK) as pack:
        return pack.read("assets/minecraft/font/glyph_sizes.bin")


def make_width(sizes):
    def width(text):
        total = 0
        for char in CODES.sub("", text):
            code = ord(char)
            if char == " ":
                total += 4
                continue
            if code >= len(sizes):
                total += 8
                continue
            packed = sizes[code]
            start, end = packed >> 4, packed & 15
            total += (end - start) // 2 + 1
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


def official_reference(width):
    """Widest multi-line segment each mod ships in an official Latin locale."""
    ceiling = collections.defaultdict(int)
    samples = collections.Counter()
    source = {}
    for jar in sorted((INSTANCE / "mods").glob("*.jar")):
        try:
            archive = zipfile.ZipFile(jar)
        except Exception:
            continue
        with archive:
            for name in archive.namelist():
                match = re.match(r"assets/([^/]+)/lang/([^/]+)\.lang$", name)
                if not match or match.group(2).lower() not in LATIN_LOCALES:
                    continue
                namespace = match.group(1)
                try:
                    text = archive.read(name).decode("utf-8", errors="replace")
                except Exception:
                    continue
                for key, value in parse_lang(text).items():
                    if "\\n" not in value:
                        continue
                    samples[namespace] += 1
                    widest = max(width(seg) for seg in value.split("\\n"))
                    if widest > ceiling[namespace]:
                        ceiling[namespace] = widest
                        source[namespace] = f"{match.group(2)}:{key}"
    return ceiling, samples, source


def main():
    width = make_width(glyph_widths())
    ceiling, samples, source = official_reference(width)

    self_wrapping = 0
    worst = {}
    for source_dir, target_dir in PAIRS:
        for lang_path in sorted((ROOT / source_dir).glob("*.lang")):
            json_path = ROOT / target_dir / f"{lang_path.stem}.json"
            if not json_path.exists():
                continue
            english = parse_lang(lang_path.read_text(encoding="utf-8"))
            target = json.loads(json_path.read_text(encoding="utf-8"))
            for key, source_value in english.items():
                translated = target.get(key)
                if not isinstance(translated, str) or "\\n" not in translated:
                    continue
                if max(width(s) for s in source_value.split("\\n")) > SELF_WRAP_PX:
                    self_wrapping += 1
                    continue
                widest = max(width(s) for s in translated.split("\\n"))
                mod = lang_path.stem
                if widest > worst.get(mod, (0, ""))[0]:
                    worst[mod] = (widest, key)

    rows, over = [], []
    for mod, (widest, key) in sorted(worst.items(), key=lambda kv: -kv[1][0]):
        reference = ceiling.get(mod, 0)
        if samples.get(mod, 0) < MIN_REFERENCE_KEYS:
            rows.append(
                {"mod": mod, "vi_px": widest, "reference_px": reference or None,
                 "verdict": "no usable reference", "key": key}
            )
            continue
        verdict = "ok" if widest <= reference else f"over by {widest - reference}px"
        rows.append(
            {"mod": mod, "vi_px": widest, "reference_px": reference,
             "reference_from": source.get(mod), "verdict": verdict, "key": key}
        )
        if widest > reference:
            over.append(f"{mod}:{key} {widest}px > {reference}px")

    print(json.dumps(
        {"self_wrapping_skipped": self_wrapping, "rows": rows, "over_reference": over},
        ensure_ascii=False, indent=2,
    ))
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
