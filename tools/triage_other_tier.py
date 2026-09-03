"""Split the `other` tier of work/missing_by_tier.json into policy-keep vs real debt.

`other` is the untriaged remainder after T1/T2/T3, and its raw size is a bad
progress signal: most rows are strings the pack deliberately ships in English
(item and registry names, ritual and brew proper names, `%s` name templates,
internal ids, command syntax). Counting those as outstanding work makes the
backlog look ~2x larger than it is.

Every rule below was derived by reading the family in the shipped corpus, not by
pattern-matching a value. Run with no arguments for a summary; `--list <ns>`
prints the remaining real-debt rows for one namespace so a wave can be scoped.
"""
from pathlib import Path
import argparse, collections, json, re, sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_coverage

ROOT = Path(__file__).resolve().parents[1]
TIERS = ROOT / "work" / "missing_by_tier.json"

# Whole key families that ship in English by design.
KEEP_FAMILIES = {
    "base.part": "GregTech '%s Bolt'-style name templates; translating breaks every derived item name",
    "info_book.evilcraft": "book index entries that repeat item names verbatim",
    "enderutilities.container": "container titles that mirror the block's registry name",
    "botania.brew": "brew proper names (Shielding, Absolution, Vanity's Emptiness)",
    "ritual.bewitchment": "ritual proper names",
    "pe.transmutation": "per-character animation frames, not prose",
    "twilightforest.shader": "shader identifiers",
    "reccomplex.transformer": "internal transformer ids",
    "reccomplex.direction": "direction tokens",
    "openmodslib.structure": "structure registry ids",
    "storagedrawers.material": "material registry names",
    "perk.modifier": "perk modifier proper names",
    "modwiki.style": "style ids",
    "choice.format": "format tokens",
    # Every sibling is a mod's own display name ("Ender IO", "Actually
    # Additions", "The Erebus"), i.e. the proper name a player greps for in the
    # mod list. All 91 rows in this family are names, none are prose.
    "cfg.universaltweaks": "third-party mod display names",
}

# Key prefixes that name a thing rather than label a control.
KEEP_PATTERNS = [
    (re.compile(r"^effect\.xu2\."), "potion/effect proper names"),
    (re.compile(r"^attribute\.name\."), "attribute registry names"),
    (re.compile(r"^jer\.dim\."), "vanilla dimension names"),
    (re.compile(r"^jer\.dungeon\."), "loot-table / structure ids"),
    (re.compile(r"^effect\."), "potion effect names"),
    (re.compile(r"^potion\."), "potion names"),
    (re.compile(r"^enchantment\."), "enchantment names"),
    (re.compile(r"^biome\.|\.biome\."), "biome names"),
    (re.compile(r"^entity\.|\.entity\."), "entity names"),
    (re.compile(r"^spell\.|\.spell\."), "spell proper names"),
    (re.compile(r"^ritual\.|\.ritual\."), "ritual proper names"),
    # Astralsorcery's bare constellation key IS the proper name (Aevitas,
    # Discidia, ...); its `.info`/`.effect` siblings hold the translated
    # prose that describes the constellation, confirmed against the shipped
    # pack, where those siblings are Vietnamese but the bare key stays Latin.
    (re.compile(r"^astralsorcery\.constellation\.[a-z]+$"), "constellation proper names"),
]

SYMBOL = re.compile(r"^[\W\d_]+$")
# `<x1>`/`[dim1]` (numbered placeholders) and `[params...]` (an ellipsis) are
# still command syntax the player must type; the bare `[a-z]+` version missed
# both and mis-tiered 2 real command-usage strings as translation debt.
COMMAND = re.compile(r"^/|<[a-z][a-z0-9]*>|\[[a-z][a-z0-9.]*\]", re.IGNORECASE)

# `%s: %s`, `[%1$s] %2$s: %3$d`, `#%s: %s` are pure format templates: every
# letter in the raw string is inside a specifier (`%1$s`), so SYMBOL's
# "every char is non-word" test misses them (the `s` in `%1$s` is a letter).
# Strip specifiers first, then check whether any letter survives.
FORMAT_TOKEN = re.compile(r"%\d*\$?[sd]|%%")


def is_format_template(english: str) -> bool:
    remainder = FORMAT_TOKEN.sub("", english)
    return not re.search(r"[A-Za-z]", remainder)


# `§e`, `§f` with no text: EnderIO's TOP integration splits every readout into
# a `.pre`/`.post` pair, and the pair members that DO carry a label are already
# translated ("§eRecv: §f" -> "§eNhận: §f"). The colour-only members have no
# prose to translate at all.
COLOR_CODE = re.compile(r"§[0-9a-fk-or]", re.IGNORECASE)


def is_pure_style_code(english: str) -> bool:
    return bool(english) and not COLOR_CODE.sub("", english)


# Container/GUI/JEI-category/research titles whose English is exactly some
# registry name in the same namespace are showing the object's name, so they
# inherit the item-name policy. Verified against the shipped pack: 0 of the
# keys this matches were translated, while near-miss labels that only contain
# a registry term ("Silo Location" -> "Vị trí Silo") do not match and stay
# debt. `gui.message.*` is excluded: those are HUD messages, not titles, and
# galacticraft translates them ("Fuel" -> "Nhiên liệu").
REGISTRY_NAME_KEY = re.compile(r"^(item|tile|block|entity)\..*\.name$")


def is_title_like_key(key: str) -> bool:
    if key.startswith("gui.message."):
        return False
    if re.match(r"^(container|gui)\.", key) or re.search(r"\.gui\.", key):
        return True
    return key.startswith("jei.") or key.endswith(".title")


def registry_names(english_by_namespace, namespace):
    return {
        value.strip()
        for key, value in english_by_namespace.get(namespace, {}).items()
        if REGISTRY_NAME_KEY.match(key)
    }


# A value that is an item/block name registered by SOME mod in the pack is
# covered by the item-name policy even when the key lives in another
# namespace. Roots' spell modifiers "Brimstone", "Fire Extinguisher" and
# "Singularity" are all Extra Utilities 2 / AE2 registry items and are listed
# in work/protected_terms.json, so they ship English while the rest of that
# family (203 of 216 titles) is translated.
PROTECTED_TERMS = ROOT / "work" / "protected_terms.json"


def protected_terms():
    return {t.strip() for t in json.loads(PROTECTED_TERMS.read_text(encoding="utf-8"))}


# Keys human-reviewed while harvesting wave 19's 444-row debt list and found
# to be single-letter/abbreviation notation rather than prose. Each rationale
# is exact-key, not pattern-matched, because the same letter is ordinary
# prose everywhere else in the corpus (e.g. "x" as a pronoun/variable name).
EXACT_KEEP = {
    # Compass abbreviations: translating "N" risks colliding with "Nam"
    # (South) in Vietnamese, where North is "Bắc". Ambiguous either way.
    "jm.minimap.compass.n": "compass abbreviation; Vietnamese for North is Bac, not N",
    "jm.minimap.compass.s": "compass abbreviation; Vietnamese for South is Nam, collides with N->Bac swap",
    "jm.minimap.compass.e": "compass abbreviation (East)",
    "jm.minimap.compass.w": "compass abbreviation (West)",
    # Coordinate axis labels: universal notation, not prose.
    "reccomplex.parameters.pos.x": "coordinate axis label, universal notation",
    "reccomplex.parameters.pos.y": "coordinate axis label, universal notation",
    "reccomplex.parameters.pos.z": "coordinate axis label, universal notation",
    # Unit abbreviations, kept English like every other unit in the corpus
    # (FE = Forge Energy, CF = Crystal Flux are both units elsewhere too).
    "actuallyadditions.cf": "unit abbreviation (Crystal Flux)",
    "definition.hammercore:fe.short": "unit abbreviation (Forge Energy)",
    "definition.hammercore:bt.short": "unit abbreviation (Burn Ticks)",
    # "OK"/"Ok" is never translated anywhere it already ships (compare
    # actuallyadditions.info.actuallyadditions.gui.ok and waila.screen.button.ok,
    # both "Ok"), unlike "Cancel" -> "Hủy" or "Confirm" -> "Xác Nhận".
    "generic.ok.txt": "corpus precedent: OK/Ok stays English (see actuallyadditions, waila)",
    "singles.buildinggadgets.confirm": "corpus precedent: OK/Ok stays English (see actuallyadditions, waila)",
    # Screen titles that shorten the block's registry name by dropping its
    # leading qualifier: "Wooden Crate" -> "Crate", "Quartz Grindstone" ->
    # "Grindstone". Each is the ONLY registry match in its namespace, so the
    # title is unambiguously that block. Listed exact-key rather than as a
    # suffix rule because a generic-suffix heuristic also swallows ordinary
    # vocabulary ("Storage", "Tank", "Fuel", "Block"), which the corpus does
    # translate.
    "container.abyssalcraft.crate": "screen title shortens registry name 'Wooden Crate'",
    "gui.appliedenergistics2.GrindStone": "screen title shortens registry name 'Quartz Grindstone'",
    # "x%s" is multiplier notation ("x3"), used verbatim inside already
    # translated prose elsewhere in the corpus; there is no word to translate.
    "gui.atum.rotations": "multiplier notation (x%s), used verbatim in translated prose",
    # Config-category label whose own tooltip keeps the registry term:
    # "ac_shoggoth.tooltip" ships as "Cấu hình Shoggoth Ooze".
    "ac_shoggoth": "config category label; registry term kept, per its own tooltip",
}


def family(key):
    parts = key.split(".")
    return ".".join(parts[:2]) if len(parts) > 2 else key


def reason_to_keep(row, english_by_namespace=None, protected=None):
    """Why this row ships in English, or None when it is real translation debt."""
    key, english = row["key"], row["en"]
    if not english.strip():
        return "empty value"
    if key in EXACT_KEEP:
        return EXACT_KEEP[key]
    if protected and english.strip() in protected:
        return "value is a protected registry term"
    if SYMBOL.match(english):
        return "symbol / number only"
    if is_format_template(english):
        return "format template, no prose to translate"
    if is_pure_style_code(english):
        return "colour/style code only, no prose to translate"
    if COMMAND.search(english):
        return "command syntax the player must type"
    fam = family(key)
    if fam in KEEP_FAMILIES:
        return KEEP_FAMILIES[fam]
    for pattern, why in KEEP_PATTERNS:
        if pattern.search(key):
            return why
    if key.endswith(".name") and len(english.split()) <= 4:
        return "item / block / registry name"
    if english_by_namespace and is_title_like_key(key):
        if english.strip() in registry_names(english_by_namespace, row["namespace"]):
            return "screen title mirrors the object's registry name"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", metavar="NAMESPACE",
                    help="print the remaining real-debt rows for one namespace")
    ap.add_argument("--tier", default="other",
                    help="tier to triage: other (default), T2, T3, or all")
    args = ap.parse_args()

    rows = json.loads(TIERS.read_text(encoding="utf-8"))
    if args.tier == "all":
        selected = list(rows)
    else:
        selected = [r for r in rows if r["tier"] == args.tier]
    english = measure_coverage.read_english()
    protected = protected_terms()
    keep, debt = [], []
    for row in selected:
        why = reason_to_keep(row, english, protected)
        (keep if why else debt).append((row, why))

    if args.list:
        wanted = [r for r, _ in debt if r["namespace"] == args.list]
        for row in sorted(wanted, key=lambda r: r["key"]):
            print(f"{row['key']}\t{row['en']}")
        print(f"\n{len(wanted)} rows in {args.list}", file=sys.stderr)
        return 0

    reasons = collections.Counter(why for _, why in keep)
    namespaces = collections.Counter(r["namespace"] for r, _ in debt)
    report = {
        "tier": args.tier,
        "tier_total": len(selected),
        "ships_in_english": len(keep),
        "real_debt": len(debt),
        "keep_reasons": dict(reasons.most_common()),
        "debt_by_namespace": dict(namespaces.most_common()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
