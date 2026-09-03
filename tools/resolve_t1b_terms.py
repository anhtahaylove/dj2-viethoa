"""Resolve the term conflicts this batch introduced, one decision per term.

align_batch_terms handles pure casing. What is left needs a judgement about
meaning, so each entry below records which way it goes and why. Two outcomes
are possible and both are legitimate: adopt the shipped wording, or keep the
new wording because the English word means something different here.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Keys live in one of two stores depending on their registry prefix, so resolve
# by search rather than assuming; guessing wrong writes a key into the wrong
# file, where the build would silently not pick it up.
STORES = (
    ROOT / "work" / "translated" / "runtime_locales",
    ROOT / "work" / "translated" / "tooltips",
)

# key -> agreed Vietnamese. These are the same concept as an already-shipped
# string, so the batch adopts the shipped wording.
ADOPT_SHIPPED = {
    ("modularmachinery", "tooltip.energyhatch.ic2.any"): "Bất Kỳ",
    ("mysticalagriculture", "tooltip.ma.blast_resistant"): "Chống vụ nổ",
    ("cofh", "info.cofh.capacity"): "Dung lượng",
    ("cofh", "info.cofh.charge"): "Nạp điện",
    ("thaumicenergistics", "tooltip.thaumicenergistics.device_offline"): "Thiết bị ngừng hoạt động",
    ("thaumicenergistics", "tooltip.thaumicenergistics.device_online"): "Thiết bị đang hoạt động",
    ("cofh", "info.cofh.fluid"): "Chất lỏng",
    ("buildinggadgets", "tooltip.gadget.fuzzy"): "Xấp xỉ",
    ("wawla", "tooltip.wawla.generic.harvestable"): "Khai thác được",
    ("cofh", "info.cofh.ignored"): "Bỏ Qua",
    ("cofh", "info.cofh.item"): "Vật Phẩm",
    ("wawla", "tooltip.wawla.item"): "Vật Phẩm",
    ("agricraft", "agricraft_tooltip.material"): "Vật Liệu",
    ("mysticalagriculture", "tooltip.ma.material"): "Vật Liệu",
    ("solarflux", "info.solarflux.maximum"): "Tối Đa",
    ("spartanshields", "tooltip.spartanshields.dev.unimplemented"): "Chưa được triển khai!",
    # thermaldynamics: the SHIPPED string is tile...structure.info ("Cung cấp
    # kết cấu."); the batch's own info...duct.structure adopts it. Writing the
    # batch's wording into the shipped key would be backwards.
    ("thermaldynamics", "info.thermaldynamics.duct.structure"): "Cung cấp kết cấu.",
    ("divinerpg", "tooltip.armor_info.step_assist"): "Hỗ trợ bước cao",
    ("mysticalagriculture", "tooltip.ma.step_assist"): "Hỗ trợ bước cao",
    # AE2's "Bật" is the shipped spelling; both conflicting keys are new.
    ("cofh", "info.cofh.enabled"): "Bật",
    ("cyclopscore", "general.cyclopscore.info.enabled"): "§aBật",
    ("wawla", "tooltip.wawla.head"): "Đầu",
    ("mysticalagriculture", "tooltip.ma.durability"): "Độ bền",
}

# Genuinely different senses of the same English word. Each keeps its own
# wording and gets an exemption instead.
KEEP_DISTINCT = {
    "info.cofh.augmentation": (
        "Nâng Cấp",
        "COFH augment slot (an upgrade you install) vs Thaumic Augmentation's "
        "research name, which is a proper title kept as English",
    ),
    "tooltip.ma.bow": (
        "Cung",
        "the weapon; mysticalagriculture ships the English word 'Bow' as a "
        "tool-type label while tconstruct's stat.bow.name is the same weapon",
    ),
    "tooltip.ma.flight": (
        "Bay lượn",
        "armour grants the ability to fly; thaumcraft volatus is the aspect of "
        "motion, a different concept with its own established wording",
    ),
    "tooltip.armor_info.fly": (
        "Bay lượn",
        "same armour ability as tooltip.ma.flight",
    ),
    "info.actuallyadditions.booklet.manualName.2": (
        "Sách Hướng Dẫn",
        "the in-game book item's own title; integrateddynamics 'manual' is a "
        "generic reference to documentation",
    ),
    "enderutilities.tooltip.item.mirror": (
        "Gương",
        "an actual mirror item; buildinggadgets 'Mirror' is the mirroring "
        "transform applied to a build",
    ),
}


def main() -> int:
    # A shipped key must never be rewritten to match a new one — that silently
    # restyles live text, and I got this backwards once already. The batch
    # manifest is the authority on which keys are new.
    batch = json.loads((ROOT / "work" / "approved_t1b_corpus.json").read_text(encoding="utf-8"))
    in_batch = {(r["namespace"], r["key"]) for r in batch["rows"]}
    stray = [f"{ns}:{k}" for ns, k in ADOPT_SHIPPED if (ns, k) not in in_batch]
    if stray:
        raise SystemExit("refusing to rewrite already-shipped keys: " + ", ".join(stray))

    changed = []
    for (ns, key), want in ADOPT_SHIPPED.items():
        for store in STORES:
            path = store / f"{ns}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data["entries"] if "entries" in data else data
            if key not in entries:
                continue
            if entries[key] != want:
                changed.append(f"{ns}:{key}: {entries[key]!r} -> {want!r}")
                entries[key] = want
                path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            break
        else:
            raise SystemExit(f"missing key {ns}:{key} in every store")

    print(json.dumps({"adopted_shipped": len(changed), "kept_distinct": len(KEEP_DISTINCT)}, indent=1))
    for c in changed:
        print("  ", c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
