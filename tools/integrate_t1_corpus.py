"""Merge the finished T1 units into the pack's source-of-truth files.

Routing follows the registry-prefix rule: keys starting with one of the banned
prefixes go to source/tooltips/ (whose tests allow descriptions), the rest to
work/runtime_locale_sources/. Writing an `item.*` key into runtime_locale_sources/
fails test_runtime_locale_manifests_do_not_translate_registry_names.

The corpus has 2562 rows but only 2390 distinct English strings: identical
English under different keys was translated once, so a translation is looked up
by its unit index and then fanned back out to every key that shares it.

Every row is re-validated here against the live JAR rather than trusting the
unit files: token parity via the build's own FORMAT regex (a hand-rolled one
misreads "200% cooler"), colour codes, URLs and edge spaces.
"""
from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from validate_lang import FORMAT  # noqa: E402  the build's own token regex

UNITS = Path("C:/Users/Administrator/AppData/Local/Temp/dj2_t1_units")
VI = Path("C:/Users/Administrator/AppData/Local/Temp/dj2_t1_vi")
MANIFEST = ROOT / "work" / "approved_t1_corpus.json"
TIP_SRC = ROOT / "source" / "tooltips"
TIP_TGT = ROOT / "work" / "translated" / "tooltips"
RUN_SRC = ROOT / "work" / "runtime_locale_sources"
RUN_TGT = ROOT / "work" / "translated" / "runtime_locales"
RUN_META = ROOT / "work" / "runtime_locale_meta"
GLOSSARY = ROOT / "work" / "t1_glossary.json"

COLOR = re.compile(r"§.")
URL = re.compile(r"https?://\S+")
NUMBERED = re.compile(r"%(\d+)\$")

# Keys under these prefixes name a thing; they must never be translated and
# must never be written into runtime_locale_sources/.
REGISTRY_PREFIXES = (
    "item.", "tile.", "block.", "fluid.", "entity.", "material.", "oredict.",
    "ore.", "biome.", "dimension.", "enchantment.", "potion.", "itemGroup.",
)


def parse_lang(text: str) -> "OrderedDict[str, str]":
    out: OrderedDict[str, str] = OrderedDict()
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        out[key.strip()] = value
    return out


def load_units() -> dict[int, tuple[str, str, str]]:
    """index -> (namespace, key, english)"""
    out: dict[int, tuple[str, str, str]] = {}
    for path in sorted(UNITS.glob("unit_*.txt")):
        raw = path.read_bytes().decode("utf-8")
        # A CR here is silent poison: it becomes part of the English string, so
        # every lookup misses and the batch reports 100% "unresolved" instead of
        # a file-format error. load_translations already refuses CR; so does this.
        if "\r" in raw:
            raise SystemExit(f"{path.name} contains CR; rewrite it LF-only")
        for line in raw.split("\n"):
            if not line.strip():
                continue
            idx, ns, key, en = line.split("\t")
            # Indices are GLOBAL across unit_*.txt, not per-file. A batch split
            # into several files that each restart at 1 silently overwrote the
            # earlier files here, and the rows reappeared as "unresolved".
            if int(idx) in out:
                raise SystemExit(
                    f"{path.name}: duplicate unit index {idx}; "
                    "number unit rows continuously across all unit files")
            out[int(idx)] = (ns, key, en)
    return out


def load_translations() -> dict[int, str]:
    out: dict[int, str] = {}
    for path in sorted(VI.glob("unit_*.vi.txt")):
        raw = path.read_bytes().decode("utf-8")
        if "\r" in raw:
            raise SystemExit(f"{path.name} contains CR; rewrite it LF-only")
        for line in raw.split("\n"):
            if not line.strip():
                continue
            idx, _, vi = line.partition("\t")
            if int(idx) in out:
                raise SystemExit(
                    f"{path.name}: duplicate translation index {idx}; "
                    "number rows continuously across all unit files")
            out[int(idx)] = vi
    return out


def verify(en: str, vi: str, key: str) -> list[str]:
    bad = []
    if not vi.strip():
        bad.append("empty")
    # Numbered tokens may legally reorder; unnumbered ones may not.
    if NUMBERED.search(en):
        if sorted(FORMAT.findall(en)) != sorted(FORMAT.findall(vi)):
            bad.append("numbered token multiset changed")
    elif FORMAT.findall(en) != FORMAT.findall(vi):
        bad.append(f"tokens {FORMAT.findall(en)} != {FORMAT.findall(vi)}")
    if COLOR.findall(en) != COLOR.findall(vi):
        bad.append("colour codes differ")
    if URL.findall(en) != URL.findall(vi):
        bad.append("URLs differ")
    if en.count("\\n") != vi.count("\\n"):
        bad.append("escaped newline count differs")
    if "\n" in vi or "\r" in vi or "\t" in vi:
        bad.append("raw control character")
    if en[:1].isspace() != vi[:1].isspace() or en[-1:].isspace() != vi[-1:].isspace():
        bad.append("edge space changed")
    if any(ord(c) > 0xFFFF for c in vi):
        bad.append("character outside the BMP")
    # NOTE: a registry PREFIX decides which file a key lives in, not whether it
    # may be translated. `item.katana.desc` is prose a player reads; only the
    # `.name` form must stay English, and the exporter already excluded those.
    return bad


def merge_lang(path: Path, additions: dict[str, str]) -> tuple[int, int]:
    """English sources are .lang; preserve any leading comment header."""
    header = ""
    existing: "OrderedDict[str, str]" = OrderedDict()
    if path.exists():
        text = path.read_text(encoding="utf-8-sig")
        for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if raw.lstrip().startswith("#") and not existing:
                header += raw + "\n"
        existing = parse_lang(text)
    added = 0
    for key, value in additions.items():
        if key in existing:
            if existing[key] != value:
                raise SystemExit(f"{path.name}: {key} already present with a different value")
            continue
        existing[key] = value
        added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    body = header + "".join(f"{k}={v}\n" for k, v in existing.items())
    path.write_text(body, encoding="utf-8", newline="\n")
    return added, len(existing)


def merge_json(path: Path, additions: dict[str, str]) -> tuple[int, int]:
    """Translated targets are JSON key->value maps."""
    existing: dict[str, str] = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8-sig"))
    added = 0
    for key, value in additions.items():
        if key in existing:
            if existing[key] != value:
                raise SystemExit(f"{path.name}: {key} already present with a different value")
            continue
        existing[key] = value
        added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return added, len(existing)


def write_tooltip_meta(namespace: str, jar: str | None, english_locale: str) -> None:
    """source/tooltips/<ns>.meta.json — provenance for the tooltip family.

    Merges into any existing record: a namespace can be fed by several JARs and
    an earlier batch may already have registered one.
    """
    if not jar:
        return
    path = TIP_SRC / f"{namespace}.meta.json"
    locale = english_locale.lower()
    entry = {"jar": jar, "path": f"assets/{namespace}/lang/{english_locale}"}
    if path.exists():
        meta = json.loads(path.read_text(encoding="utf-8-sig"))
        if entry not in meta.get("sources", []):
            meta.setdefault("sources", []).append(entry)
    else:
        meta = {"english_locale": locale.removesuffix(".lang"), "sources": [entry]}
    path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")


def write_runtime_meta(namespace: str, jar: str | None, english_locale: str, keys: int) -> None:
    """Deliberately a no-op — documented so nobody re-adds the write.

    work/runtime_locale_meta/<ns>.json drives apply_runtime_locale_casing's
    vi_VN vs vi_vn choice. Only 44 of the 135 runtime namespaces have a record,
    and the shipped pack is correct: the other 91 keep vi_vn.lang whatever
    their JAR's en_US spelling. CREATING a record renames that namespace's
    locale and changes which file the client loads, and its only other field
    (`keys`) is a comment nothing reads. So: never create, never rewrite.
    """
    return


def main() -> int:
    # --units/--vi/--manifest retarget a later batch; the merge, routing and
    # protected-term logic is identical, so it must not be forked per batch.
    global UNITS, VI, MANIFEST
    argv = sys.argv[1:]
    known = {"--units": "UNITS", "--vi": "VI", "--manifest": "MANIFEST"}
    # An unrecognised flag used to be ignored in silence, so a typo ran the
    # PREVIOUS batch's manifest against this batch's units and half-wrote
    # another batch's keys before the value guard aborted. Refuse instead.
    for token in argv:
        if token.startswith("--") and token not in known:
            raise SystemExit(
                f"unknown flag {token}; expected any of {', '.join(sorted(known))}")
    for flag, name in known.items():
        if flag in argv:
            globals()[name] = Path(argv[argv.index(flag) + 1])

    units = load_units()
    trans = load_translations()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = manifest["rows"]

    missing = set(units) - set(trans)
    if missing:
        raise SystemExit(f"{len(missing)} unit rows have no translation")

    # English string -> Vietnamese, so duplicate English fans back out.
    #
    # Three resolution passes, narrowest first:
    #  1. (namespace, English) — the translation written for this very mod.
    #  2. the mined glossary — the unit files deliberately OMIT strings already
    #     settled by the shipped pack ("Active", "Empty"), so those keys have no
    #     unit row at all and must come from the glossary.
    #  3. another namespace's translation of the identical English, but ONLY
    #     where every namespace agreed; a conflict means the same word needs
    #     different Vietnamese per mod and must not be guessed.
    by_english: dict[tuple[str, str], str] = {}
    per_english: dict[str, set[str]] = defaultdict(set)
    for idx, (ns, key, en) in units.items():
        by_english[(ns, en)] = trans[idx]
        per_english[en].add(trans[idx])

    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))["term_map"]
    consensus = {en: next(iter(v)) for en, v in per_english.items() if len(v) == 1}

    problems: list[str] = []
    tips: dict[str, dict[str, str]] = defaultdict(dict)
    runtime: dict[str, dict[str, str]] = defaultdict(dict)
    unresolved: list[str] = []

    for row in rows:
        ns, key, en = row["namespace"], row["key"], row["en"]
        vi = by_english.get((ns, en))
        if vi is None:
            vi = glossary.get(en) or consensus.get(en)
        if vi is None:
            unresolved.append(f"{ns}:{key}: {en[:60]!r}")
            continue
        for issue in verify(en, vi, key):
            problems.append(f"{ns}:{key}: {issue}")
        if key.startswith(REGISTRY_PREFIXES):
            tips[ns][key] = vi
        else:
            runtime[ns][key] = vi

    if unresolved:
        problems.extend(f"unresolved {u}" for u in unresolved)
    if problems:
        for p in problems[:25]:
            print("PROBLEM", p)
        raise SystemExit(f"{len(problems)} problems; nothing written")

    # Two different provenance records, in two different shapes:
    #   source/tooltips/<ns>.meta.json   {english_locale, sources:[{jar,path}]}
    #   work/runtime_locale_meta/<ns>.json {jar, english_locale, keys}
    # The runtime one exists ONLY for namespaces whose JAR spells the locale
    # en_US.lang; apply_runtime_locale_casing uses it to pick vi_VN vs vi_vn.
    # Writing it for an en_us namespace would rename that locale wrongly.
    locales = {(r["namespace"]): r["english_locale"] for r in rows if r.get("english_locale")}
    jars = {r["namespace"]: r.get("jar") for r in rows if r.get("jar")}

    report = {"tooltips": {}, "runtime": {}}
    by_ns_key = {(r["namespace"], r["key"]): r["en"] for r in rows}
    for ns, entries in sorted(tips.items()):
        src = {k: by_ns_key[(ns, k)] for k in entries}
        merge_lang(TIP_SRC / f"{ns}.lang", src)
        added, total = merge_json(TIP_TGT / f"{ns}.json", entries)
        write_tooltip_meta(ns, jars.get(ns), locales.get(ns, "en_us"))
        report["tooltips"][ns] = {"added": added, "total": total}
    for ns, entries in sorted(runtime.items()):
        src = {k: by_ns_key[(ns, k)] for k in entries}
        _, src_total = merge_lang(RUN_SRC / f"{ns}.lang", src)
        added, total = merge_json(RUN_TGT / f"{ns}.json", entries)
        write_runtime_meta(ns, jars.get(ns), locales.get(ns, "en_us"), src_total)
        report["runtime"][ns] = {"added": added, "total": total}

    print(json.dumps({
        "rows": len(rows),
        "distinct_english": len(by_english),
        "tooltip_namespaces": len(tips),
        "runtime_namespaces": len(runtime),
        "tooltip_keys": sum(len(v) for v in tips.values()),
        "runtime_keys": sum(len(v) for v in runtime.values()),
        "problems": 0,
    }, indent=2))
    (ROOT / "work" / "t1_integration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
