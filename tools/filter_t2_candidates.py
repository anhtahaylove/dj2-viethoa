"""Phase 0 of the T2 plan: filter GUI/JEI labels before batching.

The plan is explicit that filtering must precede batching, because a label that
duplicates a registry name has to stay English — translating the GUI title of a
machine whose block name stays "Crystallizer" shows the player two names for one
block. Three exclusions, in the plan's order:

  1. the value is a protected term;
  2. the value equals a tile./item. display name from the SAME mod;
  3. the value carries no translatable words (units, symbols, format tokens).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from measure_coverage import DEV_ONLY, NAME_LIKE, is_registry_name, read_english, read_pack  # noqa: E402
from tier_missing import tier  # noqa: E402

OUT = ROOT / "work" / "t2_candidates.json"
PROTECTED = json.loads((ROOT / "work" / "protected_terms.json").read_text(encoding="utf-8"))
TERMS = {t.casefold() for t in PROTECTED}

# No letters at all, or only format tokens/units: nothing to translate.
NO_WORDS = re.compile(r"^[\W\d_§%sdn.,:/+-]*$", re.IGNORECASE)


def display_names(en_ns: dict[str, str]) -> set[str]:
    """Registry display names this mod ships, casefolded."""
    out = set()
    for key, value in en_ns.items():
        if re.match(r"^(tile|item|entity|fluid|block)\.", key) and key.endswith(".name"):
            out.add(value.casefold())
    return out


def all_display_names(en: dict[str, dict[str, str]]) -> set[str]:
    """Every registry display name in the modpack, casefolded.

    A ritual/recipe entry such as `ac.ritual.azathothStatue = Azathoth Statue`
    is a pointer to an item, and the item may be registered by ANOTHER mod --
    AbyssalCraft rituals name AbyssalCraft blocks, but AE2 and Actually
    Additions GUI entries name items from across the pack. Comparing only
    within one namespace let 225 real item names through as translatable
    labels, which would have broken JEI lookup for each of them.
    """
    out = set()
    for entries in en.values():
        out |= display_names(entries)
    return out


def main() -> int:
    en = read_english()
    pack = read_pack()

    rows, excluded = [], {"protected": 0, "registry_name": 0, "no_words": 0,
                          "dev_only": 0}
    pack_names = all_display_names(en)
    for ns, entries in sorted(en.items()):
        names = display_names(entries) | pack_names
        for key, value in entries.items():
            if key in pack.get(ns, {}):
                continue
            if key.startswith(DEV_ONLY):
                excluded["dev_only"] += 1
                continue
            if NAME_LIKE.search(key) or is_registry_name(ns, key) or tier(key, pack.get(ns, {})) != "T2":
                continue
            folded = value.casefold()
            if folded in TERMS:
                excluded["protected"] += 1
                continue
            if folded in names:
                excluded["registry_name"] += 1
                continue
            if NO_WORDS.match(value):
                excluded["no_words"] += 1
                continue
            rows.append({"namespace": ns, "key": key, "en": value})

    OUT.write_text(json.dumps({"rows": rows, "excluded": excluded}, ensure_ascii=False, indent=1), encoding="utf-8")
    uniq = {r["en"] for r in rows}
    print(json.dumps({
        "candidates": len(rows),
        "unique_english": len(uniq),
        "namespaces": len({r["namespace"] for r in rows}),
        "excluded": excluded,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
