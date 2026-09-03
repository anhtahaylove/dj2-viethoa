"""Tier every untranslated key so the release table is reproducible.

The tier numbers published in DOC_DAU_TIEN.md were previously produced by an
ad-hoc heuristic typed at the prompt, and re-running it gave different splits
(T1 1041 then 560) because the classification order was not pinned. Anything
quoted to players must come from here instead, so the same input always yields
the same table.

Order matters: a key is assigned to the FIRST tier that claims it.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from measure_coverage import DEV_ONLY, is_registry_name, read_english, read_pack  # noqa: E402

OUT = ROOT / "work" / "missing_by_tier.json"

# T1 before T2: "gui.foo.tooltip" is prose a player reads, not a bare label.
# Death messages are the sentence a player reads in chat when they die --
# prose, not configuration. They sat in T3 beside config/command keys only
# because both start with a bare prefix, which buried 134 of the most
# frequently seen strings in the pack under a "config" heading. The shipped
# pack already translates TConstruct/MoarTinkers death lines, so T1 is where
# they belong.
T1 = re.compile(
    r"(\.desc$|\.description$|\.tooltip|tooltip\.|\.message|message\.|^msg\.|"
    r"\.msg\.|^achievement|achievementPage|^advancement|\.info$|info\.|"
    r"\.hint|chat\.|\.warn|\.error|^death\.|\.death\.|"
    # Sound subtitles are the accessibility caption a player reads on screen;
    # both `subtitle.` and `subtitles.` spellings ship in this pack.
    r"^subtitles?\.|\.subtitles?\.|"
    # Hover text and inline help are prose too, whatever the mod calls it.
    r"(^|\.)(hover|hint|note|help|notify|notification|alert)(\.|$))",
    re.IGNORECASE,
)
T2 = re.compile(
    r"(^gui\.|\.gui\.|^jei\.|\.jei\.|^key\.|^container\.|^screen\.|"
    r"^itemGroup\.|\.button|\.label|\.slot|"
    # Only `^key.` was listed, but most mods namespace their controls as
    # `<mod>.keybind(s).<action>` -- the same Controls-screen label.
    r"\.keybinds?\.|\.keybinding|^keybind|"
    # Same widgets, different vocabulary across mods: a tab/panel is a screen,
    # a caption/title is a label, a hotkey/control is a keybind.
    r"(^|\.)(window|menu|page|panel|dialog|tab|btn|lbl|caption|title|header"
    r"|heading|control|hotkey|binding)s?(\.|$))",
    re.IGNORECASE,
)
# Controls-screen bindings, checked before the T1 prose words so that
# `keybind.<mod>.hover` is read as a control, not as hover text.
KEYBIND = re.compile(r"^key\.|\.keybinds?\.|\.keybinding|^keybinds?\.", re.IGNORECASE)


T3 = re.compile(
    r"(^command|\.command|^config|\.config|^options\.|^stat\.|"
    # `cfg.`, `conf.`, `settings.`, `option.` are the same config screen.
    r"(^|\.)(cfg|conf|settings?|opts?|option|cmd|usage|syntax)(\.|$))",
    re.IGNORECASE,
)


# A label whose own `.desc`/`.tooltip` is already translated is a widget caption
# sitting next to translated prose -- the player sees both in the same panel.
# Its key shape carries no hint (`roots.modifiers.modifiers.chthonic`), so shape
# regexes cannot find it; the pack's own contents are the signal.
ORPHAN_SUFFIXES = (".desc", ".description", ".tooltip", ".info", ".lore")


def has_translated_child(key: str, shipped: dict[str, str]) -> bool:
    return any(key + suffix in shipped for suffix in ORPHAN_SUFFIXES)


def tier(key: str, shipped: dict[str, str] | None = None) -> str:
    # A control binding wins over the T1 prose words: `keybind.<mod>.hover` is
    # the Hover Mode control, not hover text.
    if KEYBIND.search(key):
        return "T2"
    if T1.search(key):
        return "T1"
    if T2.search(key):
        return "T2"
    if T3.search(key):
        return "T3"
    if shipped and has_translated_child(key, shipped):
        return "T2"
    return "other"


def main() -> int:
    english = read_english()
    pack = read_pack()

    shipped_anywhere: dict[str, str] = {}
    for entries in pack.values():
        shipped_anywhere.update(entries)

    rows = []
    cross_namespace = 0
    for namespace, entries in english.items():
        shipped = pack.get(namespace, {})
        for key, value in entries.items():
            if not value.strip():
                continue
            if is_registry_name(namespace, key):
                continue
            if key.startswith(DEV_ONLY):
                continue
            if key in shipped:
                continue
            if key in shipped_anywhere:
                # Authored under one namespace, shipped under the owner's.
                cross_namespace += 1
                continue
            rows.append(
                {
                    "namespace": namespace,
                    "key": key,
                    "en": value,
                    "tier": tier(key, shipped),
                }
            )

    rows.sort(key=lambda r: (r["tier"], r["namespace"], r["key"]))
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    counts = Counter(r["tier"] for r in rows)
    print(json.dumps(
        {
            "T1": counts["T1"],
            "T2": counts["T2"],
            "T3": counts["T3"],
            "other": counts["other"],
            "total_missing": len(rows),
            "shipped_under_other_namespace": cross_namespace,
        },
        indent=2,
    ))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
