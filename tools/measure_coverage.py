"""Measure translation coverage of the built pack against the active mod JARs.

Coverage is only meaningful with its denominator stated, so this prints the
full breakdown: how many JAR keys exist, how many are registry/proper names the
pack deliberately keeps in English, and how much of the remaining prose is
translated. Percentages in DOC_DAU_TIEN.md must come from this script.
"""
import json
import os
import re
import zipfile
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS = (Path(os.environ["APPDATA"]) / "ElyPrismLauncher" / "instances"
        / "Divine Journey 2" / "minecraft" / "mods")
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"

# A key under one of these names a registry object; translating it breaks JEI
# search, so it is out of scope rather than "missing".
NAME_LIKE = re.compile(
    r"^(item|tile|block|fluid|entity|material|oredict|ore|biome|dimension|"
    r"enchantment|potion|itemGroup)\.", re.IGNORECASE)

# BiblioCraft registers its blocks without the usual `tile.` prefix, so its
# block names look like plain keys ("jungleBookcase.name"). They are registry
# names all the same — the pack already ships 13 of them untranslated on
# purpose — and counting them as untranslated inflated the backlog by 195 rows.
# Scoped to the one mod that does this: elsewhere a bare `<x>.name` is ordinary
# UI text (mekanism `tooltip.name` = "Name", enderutilities `language.name`).
BARE_NAME_MODS = {"bibliocraft"}
BARE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.name$")


def is_registry_name(namespace: str, key: str) -> bool:
    """True when the key names a registry object rather than player-facing text."""
    if NAME_LIKE.match(key) and not key.endswith((".desc", ".tooltip")):
        return True
    return namespace in BARE_NAME_MODS and bool(BARE_NAME.match(key))


DEV_ONLY = ("groovyscript.wiki", "chisel.")


def parse_lang(text: str) -> "OrderedDict[str, str]":
    out: "OrderedDict[str, str]" = OrderedDict()
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            out[key] = value
    return out


def read_english() -> dict[str, dict[str, str]]:
    """namespace -> key -> English, merged across every JAR serving it."""
    merged: dict[str, dict[str, str]] = {}
    pattern = re.compile(r"^assets/([^/]+)/lang/en_us\.(lang|json)$", re.IGNORECASE)
    for jar in sorted(MODS.glob("*.jar")):
        # Every English line in a jar this cannot open drops out of in_scope,
        # so a corrupt jar shrinks the denominator and coverage climbs. That
        # reads exactly like progress. Refuse to measure instead.
        try:
            archive = zipfile.ZipFile(jar)
        except (zipfile.BadZipFile, OSError) as exc:
            raise SystemExit(f"cannot read mod jar {jar.name}: {exc}") from exc
        with archive:
            members = sorted(
                (m for m in archive.namelist() if pattern.match(m)),
                key=lambda m: 0 if m.lower().endswith(".json") else 1,
            )
            for member in members:
                namespace = pattern.match(member).group(1)
                try:
                    raw = archive.read(member).decode("utf-8-sig")
                except (KeyError, UnicodeDecodeError, OSError) as exc:
                    raise SystemExit(
                        f"cannot read {member} from {jar.name}: {exc}"
                    ) from exc
                if member.lower().endswith(".json"):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise SystemExit(
                            f"cannot parse {member} from {jar.name}: {exc}"
                        ) from exc
                    locale = {k: v for k, v in parsed.items() if isinstance(v, str)} \
                        if isinstance(parsed, dict) else {}
                else:
                    locale = parse_lang(raw)
                merged.setdefault(namespace, {}).update(locale)
    return merged


def read_pack() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(PACK) as archive:
        for member in archive.namelist():
            match = re.match(r"assets/([^/]+)/lang/vi_vn\.lang$", member, re.IGNORECASE)
            if not match:
                continue
            out.setdefault(match.group(1), {}).update(
                parse_lang(archive.read(member).decode("utf-8-sig")))
    return out


def main() -> int:
    english = read_english()
    pack = read_pack()

    total = name_like = dev_only = empty = 0
    in_scope = translated = identical = missing = 0
    for namespace, entries in english.items():
        shipped = pack.get(namespace, {})
        for key, value in entries.items():
            total += 1
            if not value.strip():
                empty += 1
                continue
            if is_registry_name(namespace, key):
                name_like += 1
                continue
            if key.startswith(DEV_ONLY):
                dev_only += 1
                continue
            in_scope += 1
            vi = shipped.get(key)
            if vi is None:
                missing += 1
            elif vi == value:
                identical += 1
            else:
                translated += 1

    pct = 100.0 * translated / in_scope if in_scope else 0.0
    report = {
        "jar_keys_total": total,
        "excluded_registry_names": name_like,
        "excluded_dev_only": dev_only,
        "excluded_empty": empty,
        "in_scope": in_scope,
        "translated": translated,
        "identical_to_english": identical,
        "missing": missing,
        "coverage_pct": round(pct, 1),
        "pack_lang_keys": sum(len(v) for v in pack.values()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    (ROOT / "work" / "coverage_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
