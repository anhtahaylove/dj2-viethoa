"""Resolve the term conflicts T2 wave 2 introduced.

align_batch_terms handles pure casing. What is left differs in wording, so each
entry records a decision. Same rule as every batch before it: only the new
batch's own keys may be rewritten — the shipped side is the authority, because
rewriting it restyles text players already see.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES = (ROOT / "work" / "translated" / "runtime_locales", ROOT / "work" / "translated" / "tooltips")
BATCH = ROOT / "work" / "approved_t2_wave2_corpus.json"

# Adopt the shipped wording for the batch's own key.
ADOPT_SHIPPED = {
    # JourneyMap ships "Trượt ..." for the same four pan actions on its hotkey
    # help screen; the keybind list must read identically or the same action is
    # named twice in one mod.
    ("journeymap", "key.journeymap.fullscreen.east"): "Trượt Sang Đông (16 Block)",
    ("journeymap", "key.journeymap.fullscreen.north"): "Trượt Lên Bắc (16 Block)",
    ("journeymap", "key.journeymap.fullscreen.south"): "Trượt Xuống Nam (16 Block)",
    ("journeymap", "key.journeymap.fullscreen.west"): "Trượt Sang Tây (16 Block)",
    # EnderUtilities ships "Xóa lưới" for the identical crafting-grid button.
    ("jecalculation", "jecalculation.gui.recipe.clear"): "Xóa lưới",
    # GuideAPI ships "Đang Pha Chế" for the brewing recipe category.
    ("jei", "gui.jei.category.brewing"): "Đang Pha Chế",
    # EnderIO ships "Chế độ lò" for the same furnace-mode heading.
    ("industrialforegoing", "text.industrialforegoing.button.stone.furnace"): "Chế độ lò",
    # "Advanced" ships lower-case as prose in EnderUtilities/Galacticraft.
    ("jei", "config.jei.advanced"): "Nâng cao",
}

# Same English, genuinely different sense: one shared wording would be wrong
# somewhere, so the validator is told why each stays split.
EXEMPT = {
    # jecalculation's `label.fluid` is the GUI label for the fluid INGREDIENT
    # kind ("Chất Lỏng"); AE2's FluidTunnel and CommonCapabilities' recipe
    # component keep "Fluid" as part of a machine/type proper name.
    "jecalculation.gui.common.label.fluid",
    # Same split for `label.item`: a UI kind label, versus AE2's ItemTunnel
    # and LevelType_Item which are device/type names kept English.
    "jecalculation.gui.common.label.item",
    # IndustrialForegoing's `side_config.tank` is the machine's own fluid
    # buffer, translated "Bể Chứa"; AE2/Mekanism keep "Tank" inside item names.
    "gui.industrialforegoing.side_config.tank",
    # Its `water_tank` is likewise the machine's internal buffer, while
    # Galacticraft's "Water Tank" is a craftable block name.
    "gui.industrialforegoing.side_config.water_tank",
}


def main() -> int:
    batch = {(r["namespace"], r["key"]) for r in json.loads(BATCH.read_text(encoding="utf-8"))["rows"]}
    changed, missing = [], []
    for (ns, key), want in ADOPT_SHIPPED.items():
        if (ns, key) not in batch:
            raise SystemExit(f"refusing to rewrite shipped key {ns}:{key}")
        found = False
        for store in STORES:
            path = store / f"{ns}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data.get("entries", data)
            if key not in entries:
                continue
            found = True
            if entries[key] != want:
                changed.append(f"{ns}:{key}: {entries[key]!r} -> {want!r}")
                entries[key] = want
                path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if not found:
            missing.append(f"{ns}:{key}")

    print(json.dumps({"changed": changed, "missing": missing, "exempt_to_add": sorted(EXEMPT)},
                     ensure_ascii=False, indent=1))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
