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
]

SYMBOL = re.compile(r"^[\W\d_]+$")
COMMAND = re.compile(r"^/|<[a-z]+>|\[[a-z]+\]")


def family(key):
    parts = key.split(".")
    return ".".join(parts[:2]) if len(parts) > 2 else key


def reason_to_keep(row):
    """Why this row ships in English, or None when it is real translation debt."""
    key, english = row["key"], row["en"]
    if not english.strip():
        return "empty value"
    if SYMBOL.match(english):
        return "symbol / number only"
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
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", metavar="NAMESPACE",
                    help="print the remaining real-debt rows for one namespace")
    args = ap.parse_args()

    rows = json.loads(TIERS.read_text(encoding="utf-8"))
    other = [r for r in rows if r["tier"] == "other"]
    keep, debt = [], []
    for row in other:
        why = reason_to_keep(row)
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
        "other_total": len(other),
        "ships_in_english": len(keep),
        "real_debt": len(debt),
        "keep_reasons": dict(reasons.most_common()),
        "debt_by_namespace": dict(namespaces.most_common()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
