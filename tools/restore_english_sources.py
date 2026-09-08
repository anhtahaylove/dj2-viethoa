"""Restore `work/runtime_locale_sources/*.lang` to the real English the game loads.

WHY THIS EXISTS
---------------
`runtime_locale_sources/` is supposed to be the ENGLISH side of the pair that
every guard compares against: `validate()` in `validate_lang.py` checks format
tokens, colour codes, URLs and protected terms by reading `src[key]` and
`tgt[key]`. If `src` already holds the Vietnamese string, all four checks
compare Vietnamese against itself and can never fail.

7014 lines had drifted into Vietnamese, so those guards were inert for roughly
a third of the corpus. An audit against the JARs found no actual violation
hiding behind them, but the checks must be live for the next wave, not
retroactively trusted.

The English of record, in priority order:

1. `<instance>/resources/<ns>/lang/en_us.lang` -- the modpack's own overrides.
   The game loads these ON TOP of the JAR, so where they exist they ARE the
   English the player sees. CraftTweaker is the big case: its JAR ships one
   key while the pack's `resources/` tree ships 602.
2. `assets/<ns>/lang/en_us.lang` (or `.json`) inside each mod JAR.

Keys present in neither are left untouched: 16 `enchantment.*.desc` lines are
pack-authored text with no upstream English, and inventing one would be worse
than leaving the row alone.

Read-only by default; `--write` is required before it edits anything.

    python tools/restore_english_sources.py           # report
    python tools/restore_english_sources.py --write
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "work/runtime_locale_sources"
from instance_paths import instance_dir

INSTANCE = instance_dir(required=False) or Path("instance-not-installed")
MODS = INSTANCE / "mods"
RESOURCES = INSTANCE / "resources"

VIETNAMESE = re.compile(
    # Both cases: an all-caps Vietnamese string such as "XUỐNG" or "TIẾNG ỒN
    # LỚN!" carries its diacritics on UPPERCASE vowels, and a lowercase-only
    # class silently passes it through as if it were English.
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
    r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    r"ÁÀẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊ"
    r"ÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ]"
)
LANG_MEMBER = re.compile(r"^assets/([\w.\-]+)/lang/en_us\.(lang|json)$", re.IGNORECASE)


def parse_lang(text: str) -> dict[str, str]:
    """Keep the value byte-exact after the first '='.

    Minecraft concatenates these strings, so a leading or trailing space is
    content, not formatting -- `necronomicon.text.azathoth.1` ends with one in
    the shipped JAR. Stripping here would rewrite the English source with the
    padding removed and desync it from the other translated families.
    """
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        out.setdefault(key.strip(), value.rstrip("\r\n"))
    return out


def english_of_record() -> dict[str, dict[str, str]]:
    """namespace -> key -> English, JARs first then pack overrides on top."""
    merged: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for jar in sorted(MODS.glob("*.jar")):
        try:
            archive = zipfile.ZipFile(jar)
        except (zipfile.BadZipFile, OSError):
            continue
        with archive:
            for member in archive.namelist():
                match = LANG_MEMBER.match(member)
                if not match:
                    continue
                namespace = match.group(1).lower()
                try:
                    body = archive.read(member).decode("utf-8-sig", errors="replace")
                except (KeyError, OSError):
                    continue
                if member.lower().endswith(".json"):
                    try:
                        loaded = json.loads(body)
                    except json.JSONDecodeError:
                        continue
                    merged[namespace].update(
                        {k: v for k, v in loaded.items() if isinstance(v, str)}
                    )
                else:
                    merged[namespace].update(parse_lang(body))
    # Pack overrides win: the game layers resources/ over the JAR assets.
    if RESOURCES.is_dir():
        for path in RESOURCES.rglob("en_us.lang"):
            namespace = path.parent.parent.name.lower()
            merged[namespace].update(
                parse_lang(path.read_text(encoding="utf-8", errors="replace"))
            )
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--namespace")
    args = parser.parse_args()

    english = english_of_record()
    restored = collections.Counter()
    unmatched: list[tuple[str, str]] = []

    for path in sorted(SOURCES.glob("*.lang")):
        namespace = path.stem
        if args.namespace and namespace != args.namespace:
            continue
        reference = english.get(namespace, {})
        original = path.open("r", encoding="utf-8", newline="").read()
        newline = "\r\n" if "\r\n" in original else "\n"
        out_lines = []
        changed = False
        for line in original.split(newline):
            if "=" not in line or line.lstrip().startswith("#"):
                out_lines.append(line)
                continue
            key, value = line.split("=", 1)
            stripped = key.strip()
            if VIETNAMESE.search(value):
                real = reference.get(stripped)
                if real is None:
                    unmatched.append((namespace, stripped))
                elif real != value.strip():
                    out_lines.append(f"{stripped}={real}")
                    restored[namespace] += 1
                    changed = True
                    continue
            out_lines.append(line)
        if changed and args.write:
            path.write_text(newline.join(out_lines), encoding="utf-8", newline="")

    total = sum(restored.values())
    print(f"{'restored' if args.write else 'would restore'}: {total} lines "
          f"across {len(restored)} namespaces")
    for namespace, count in restored.most_common(15):
        print(f"  {namespace:24s} {count:5d}")
    if unmatched:
        print(f"\nno English of record, left untouched: {len(unmatched)}")
        for namespace, key in unmatched[:20]:
            print(f"  {namespace}/{key}")
    if not args.write:
        print("\n(report only; pass --write to apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
