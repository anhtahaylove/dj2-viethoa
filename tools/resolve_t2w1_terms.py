"""Resolve the term conflicts T2 wave 1 introduced.

align_batch_terms handles pure casing. What is left differs in wording, so each
entry records a decision. Same rule as the T1 batch: only the new
batch's own keys may be rewritten — the shipped side is authority.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES = (ROOT / "work" / "translated" / "runtime_locales", ROOT / "work" / "translated" / "tooltips")
BATCH = ROOT / "work" / "approved_t2_wave1_corpus.json"

# Adopt the shipped wording for the batch's own key.
ADOPT_SHIPPED = {
    # "Bag enabled" is the same status line as the item tooltip already shipped.
    ("enderutilities", "enderutilities.gui.label.bag.enabled"): "Đã bật túi",
    # Thermal's "Truyền Tải" is the shipped spelling of the same verb.
    ("bibliocraft", "gui.paintpress.transfer"): "Truyền Tải",
    # DankNull ships "Số ô" for the identical label; both slot labels adopt it.
    ("enderutilities", "enderutilities.gui.label.slot.amount"): "Số ô",
    ("enderutilities", "enderutilities.placement_properties.asu.slots"): "Số ô",
}


def main() -> int:
    batch = {(r["namespace"], r["key"]) for r in json.loads(BATCH.read_text(encoding="utf-8"))["rows"]}
    changed = []
    for (ns, key), want in ADOPT_SHIPPED.items():
        if (ns, key) not in batch:
            raise SystemExit(f"refusing to rewrite shipped key {ns}:{key}")
        for store in STORES:
            path = store / f"{ns}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data.get("entries", data)
            if key not in entries:
                continue
            if entries[key] != want:
                changed.append(f"{ns}:{key}: {entries[key]!r} -> {want!r}")
                entries[key] = want
                path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            break
        else:
            raise SystemExit(f"missing key {ns}:{key}")

    print(json.dumps({"changed": len(changed)}, indent=1))
    for c in changed:
        print("  ", c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
