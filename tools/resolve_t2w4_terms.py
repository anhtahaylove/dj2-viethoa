"""Resolve the term conflicts T2 wave 4 introduced.

align_batch_terms handles pure casing. What is left differs in wording, so each
entry records a decision. Same rule as every batch before it: only the new
batch's own keys may be rewritten -- the shipped side is the authority, because
rewriting it restyles text players already see.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES = (ROOT / "work" / "translated" / "runtime_locales", ROOT / "work" / "translated" / "tooltips")
BATCH = ROOT / "work" / "approved_t2_wave4_corpus.json"

# Adopt the shipped wording for the batch's own key.
ADOPT_SHIPPED = {
    # BuildingGadgets already ships "Neo" for the anchor tooltip; key.anchor is
    # the keybind for that same gadget function, so it must read identically.
    ("buildinggadgets", "key.anchor"): "Neo",
    # Same gadget mode, shipped as "Vùng Liên Kết" in both its tooltip and its
    # chat message. The keybind naming that mode has to match, not paraphrase.
    ("buildinggadgets", "key.connected_area"): "Vùng Liên Kết",
    # BiblioCraft ships "Tùy Chỉnh" for the paint press's Custom option; Rec
    # Complex's structure GUI uses the same word in the same sense.
    ("reccomplex", "reccomplex.gui.custom"): "Tùy Chỉnh",
    # Waila's scale slider and BiblioCraft's painting scale are the same
    # quantity; BiblioCraft shipped "Tỉ Lệ" first.
    ("waila", "screen.label.scale"): "Tỉ Lệ",
}


def main() -> int:
    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    allowed = {(r["namespace"], r["key"]) for r in batch["rows"]}
    stray = set(ADOPT_SHIPPED) - allowed
    if stray:
        raise SystemExit(f"refusing to touch keys outside this batch: {sorted(stray)}")

    changed = []
    for store in STORES:
        for path in sorted(store.glob("*.json")):
            ns = path.stem
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            dirty = False
            for (want_ns, key), value in ADOPT_SHIPPED.items():
                if want_ns == ns and key in data and data[key] != value:
                    changed.append(f"{ns}:{key}: {data[key]!r} -> {value!r}")
                    data[key] = value
                    dirty = True
            if dirty:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

    print(json.dumps({"changed": len(changed), "details": changed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
