"""Harvest English UI strings straight from the mod JARs the game loads.

WHY THIS EXISTS
---------------
`work/runtime_locale_sources/*.lang` used to be maintained entirely by hand.
That made a whole class of bug invisible: if nobody remembered to harvest a
mod, its strings stayed English forever and **no checker could tell**, because
every validator compares source against translation -- never source against
the JARs the game actually reads. Three separate rounds of "why is this still
English?" (Tinker `stat.*`, Thaumcraft `tc.aspect.*`, Totemic) were all the
same bug wearing different clothes.

This script closes that hole. It reads every JAR in the instance, keeps the
player-facing keys, and reports what the sources are missing. It is READ-ONLY
by default: `--write` is required before it touches `runtime_locale_sources/`,
and it never edits translations.

Usage
-----
    python tools/extract_runtime_sources.py                 # report only
    python tools/extract_runtime_sources.py --namespace totemic
    python tools/extract_runtime_sources.py --write --namespace totemic
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "work/runtime_locale_sources"
INSTANCE_MODS = Path(
    "C:/Users/Administrator/AppData/Roaming/ElyPrismLauncher/instances/"
    "Divine Journey 2/minecraft/mods"
)

LANG_PATH = re.compile(r"^assets/([^/]+)/lang/en_us\.lang$", re.IGNORECASE)

# Registry names: item/block/entity identifiers. The project deliberately keeps
# these in English so players can search JEI, the wiki and mod docs.
REGISTRY_PREFIXES = (
    "item.",
    "tile.",
    "block.",
    "entity.",
    "fluid.",
    "material.",
    "potion.",
    "enchantment.",
    "itemGroup.",
    "death.",
)

# Auto-generated documentation aimed at people WRITING GroovyScript, not at
# players. 2735 of groovyscript's 2786 keys are this: harvesting them would
# bury the real backlog under noise nobody ever reads in-game.
NOISE_PATTERNS = (
    re.compile(r"^groovyscript\.wiki\."),
    re.compile(r"^language\.(name|region|code)$"),
)


def parse_lang(text: str) -> dict[str, str]:
    """Parse a .lang file. Values keep '=' and trailing spaces verbatim."""
    out: dict[str, str] = {}
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value
    return out


def is_ui_key(key: str) -> bool:
    """True when a player can read this string somewhere in the interface."""
    if key.startswith(REGISTRY_PREFIXES):
        return False
    return not any(pattern.search(key) for pattern in NOISE_PATTERNS)


def harvest_jars(mods_dir: Path) -> dict[str, dict[str, str]]:
    """Read every JAR's en_us lang file, keeping only player-facing keys."""
    harvested: dict[str, dict[str, str]] = {}
    for jar in sorted(Path(mods_dir).rglob("*.jar")):
        try:
            with zipfile.ZipFile(jar) as zf:
                for name in zf.namelist():
                    match = LANG_PATH.match(name)
                    if not match:
                        continue
                    namespace = match.group(1).lower()
                    try:
                        text = zf.read(name).decode("utf-8", "replace")
                    except Exception:
                        continue
                    bucket = harvested.setdefault(namespace, {})
                    for key, value in parse_lang(text).items():
                        # Empty values are placeholders (blank guide-book pages
                        # padding a fixed-size entry). There is nothing to
                        # translate, and harvesting them would report a
                        # permanent, unfixable gap on every future run.
                        if is_ui_key(key) and value.strip():
                            bucket.setdefault(key, value)
        except zipfile.BadZipFile:
            continue
    return {ns: keys for ns, keys in harvested.items() if keys}


def load_source_keys(sources_dir: Path) -> dict[str, set[str]]:
    """Map namespace -> keys already present in the hand-written sources."""
    out: dict[str, set[str]] = {}
    for path in sorted(Path(sources_dir).glob("*.lang")):
        out[path.stem.lower()] = set(parse_lang(path.read_text(encoding="utf-8")))
    return out


def diff_against_sources(
    harvested: dict[str, dict[str, str]], sources: dict[str, set[str]]
) -> dict[str, dict]:
    """Report, per namespace, which harvested UI keys the sources lack."""
    report: dict[str, dict] = {}
    for namespace, keys in harvested.items():
        present = sources.get(namespace, set())
        missing = sorted(set(keys) - present)
        report[namespace] = {
            "jar_ui_keys": len(keys),
            "in_source": len(set(keys) & present),
            "missing_count": len(missing),
            "missing": missing,
        }
    return report


def write_source(namespace: str, harvested: dict[str, str], sources_dir: Path) -> int:
    """Merge harvested keys into a namespace source file. Never drops keys."""
    dest = Path(sources_dir) / f"{namespace}.lang"
    existing = parse_lang(dest.read_text(encoding="utf-8")) if dest.exists() else {}
    added = {k: v for k, v in harvested.items() if k not in existing}
    if not added:
        return 0
    merged = {**existing, **added}
    body = "\n".join(f"{k}={merged[k]}" for k in sorted(merged)) + "\n"
    dest.write_text(body, encoding="utf-8")
    return len(added)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mods", type=Path, default=INSTANCE_MODS)
    parser.add_argument("--sources", type=Path, default=SOURCES)
    parser.add_argument("--namespace", action="append", default=None)
    parser.add_argument("--write", action="store_true", help="merge into sources")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    if not args.mods.exists():
        print(f"mods dir not found: {args.mods}")
        return 1

    harvested = harvest_jars(args.mods)
    if args.namespace:
        wanted = {n.lower() for n in args.namespace}
        harvested = {k: v for k, v in harvested.items() if k in wanted}
    report = diff_against_sources(harvested, load_source_keys(args.sources))

    ranked = sorted(report.items(), key=lambda kv: -kv[1]["missing_count"])
    total = sum(entry["missing_count"] for _, entry in ranked)
    print(f"namespaces scanned: {len(report)}   UI keys missing from sources: {total}\n")
    for namespace, entry in ranked[: args.limit]:
        if not entry["missing_count"]:
            continue
        covered = entry["in_source"]
        print(
            f"{namespace:28} {covered:5}/{entry['jar_ui_keys']:<5} in source"
            f"   missing {entry['missing_count']}"
        )

    if args.write:
        if not args.namespace:
            print("\nrefusing to write every namespace at once; pass --namespace")
            return 2
        for namespace in sorted(harvested):
            added = write_source(namespace, harvested[namespace], args.sources)
            print(f"\n{namespace}: +{added} keys merged into sources")

    out = ROOT / "work/audit/runtime_source_gap.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nfull report: {out.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
