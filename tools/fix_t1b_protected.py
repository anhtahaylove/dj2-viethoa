"""Restore the four protected terms this batch translated away.

work/protected_terms.json lists words that must survive into the Vietnamese
because the wiki, JEI and the mods' own machine names index on them. The pack
already ships 70 strings containing these four, and keeps the English word in
every single one, so these six lines are the outliers, not a new convention.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_TGT = ROOT / "work" / "translated" / "runtime_locales"

FIXES = {
    # "Cool Generator" is an achievement punning on the machine's name.
    ("actuallyadditions", "achievement.actuallyadditions.craftCoalGen"): "Generator Mát Mẻ",
    ("divinerpg", "tooltip.armor_info.arcana_regen"): "Regeneration Arcana",
    ("divinerpg", "tooltip.armor_info.health_regen"): "Regeneration Máu",
    # Both words here are protected, so the string stays as the mod ships it.
    ("divinerpg", "tooltip.shots.explosive"): "Explosive Projectiles",
    ("divinerpg", "tooltip.shots.homing"): "Projectiles Tự Dẫn",
    # "Moving Mountains" is the Draconic shovel achievement. The shipped pack
    # keeps "Mountains" in the one comparable string it has ("The Dreadlands
    # Mountains"), and the protected list is absolute inside this store, so the
    # idiom cannot be localised away entirely.
    ("draconicevolution", "achievement.draconicevolution.dshovel"): "Dời Cả Mountains",
}


def main() -> int:
    for (ns, key), want in FIXES.items():
        path = RUN_TGT / f"{ns}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["entries"] if "entries" in data else data
        print(f"{ns}:{key}: {entries[key]!r} -> {want!r}")
        entries[key] = want
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
