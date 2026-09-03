"""Cut wave 1 of the T2 plan: GUI/JEI labels, batched per mod.

The plan is batched by mod, not by index, because labels from one mod appear on
one screen and translating them together keeps the terminology coherent.

The plan named astralsorcery/botania/roots/bewitchment for wave 1 on a count of
1,040 rows. That count is stale: the T1 batches since then absorbed almost all
of it, and those four mods now hold 40 GUI rows between them. Wave 1 therefore
takes the two mods that actually carry the most untranslated GUI text, which is
what the plan's priority rule ("mods whose screens players open most") means in
the pack's current state.

Repeated English is emitted once, so an identical label cannot end up with two
different Vietnamese spellings in the same wave.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WAVE = ("bibliocraft", "enderutilities")
UNITS = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "dj2_t2w1_units"


def main() -> int:
    data = json.loads((ROOT / "work" / "t2_candidates.json").read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r["namespace"] in WAVE]
    rows.sort(key=lambda r: (r["namespace"], r["key"]))

    manifest = ROOT / "work" / "approved_t2_wave1_corpus.json"
    manifest.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    seen: dict[str, int] = {}
    units: list[tuple[int, str, str, str]] = []
    for row in rows:
        if row["en"] in seen:
            continue
        seen[row["en"]] = len(units) + 1
        units.append((len(units) + 1, row["namespace"], row["key"], row["en"]))

    UNITS.mkdir(parents=True, exist_ok=True)
    for old in UNITS.glob("unit_*.txt"):
        old.unlink()

    size = 130
    chunks = [units[i:i + size] for i in range(0, len(units), size)]
    for n, chunk in enumerate(chunks, 1):
        body = "".join(f"{i}\t{ns}\t{k}\t{en}\n" for i, ns, k, en in chunk)
        # newline="" keeps LF: Python's default translates "\n" to "\r\n" on
        # Windows, and the integrator then reads the CR as part of the English
        # string, so every lookup misses.
        (UNITS / f"unit_{n:02d}.txt").write_text(body, encoding="utf-8", newline="")

    print(json.dumps({
        "rows": len(rows),
        "unique_english": len(units),
        "by_mod": {m: sum(1 for r in rows if r["namespace"] == m) for m in WAVE},
        "units": len(chunks),
        "dir": str(UNITS),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
