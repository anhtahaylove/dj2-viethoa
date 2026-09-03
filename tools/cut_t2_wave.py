"""Cut one wave of the T2 GUI/JEI plan.

Generalises cut_t2_wave1.py, which hardcoded its mods and paths. The plan
batches by mod rather than by index because labels from one mod appear on one
screen, and translating them together keeps the terminology coherent.

Rows already frozen in an earlier wave's manifest are excluded, so a wave can
never re-translate shipped text. Repeated English is emitted once, so the same
label cannot end up with two different Vietnamese spellings in one wave.

Usage:
  python tools/cut_t2_wave.py --wave 2 --mods jecalculation industrialforegoing
  python tools/cut_t2_wave.py --wave 2 --top 6      # pick by remaining volume
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"


def load_rows() -> list[dict]:
    data = json.loads((WORK / "t2_candidates.json").read_text(encoding="utf-8"))
    return data["rows"]


def already_frozen() -> set[tuple[str, str]]:
    """Every (namespace, key) claimed by an earlier wave manifest."""
    done: set[tuple[str, str]] = set()
    for manifest in sorted(WORK.glob("approved_t2_wave*_corpus.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for row in data["rows"]:
            done.add((row["namespace"], row["key"]))
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", type=int, required=True)
    ap.add_argument("--mods", nargs="*", default=None)
    ap.add_argument("--top", type=int, default=0,
                    help="instead of --mods, take the N mods with the most remaining rows")
    ap.add_argument("--size", type=int, default=130, help="unique strings per unit file")
    args = ap.parse_args()

    done = already_frozen()
    remaining = [r for r in load_rows() if (r["namespace"], r["key"]) not in done]

    if args.mods:
        wave_mods = tuple(args.mods)
    elif args.top:
        wave_mods = tuple(ns for ns, _ in Counter(r["namespace"] for r in remaining).most_common(args.top))
    else:
        raise SystemExit("pass --mods or --top")

    rows = [r for r in remaining if r["namespace"] in wave_mods]
    if not rows:
        raise SystemExit(f"no remaining rows for {wave_mods}")
    rows.sort(key=lambda r: (r["namespace"], r["key"]))

    manifest = WORK / f"approved_t2_wave{args.wave}_corpus.json"
    if manifest.exists():
        raise SystemExit(f"{manifest.name} already exists; refusing to overwrite a frozen wave")
    manifest.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")

    seen: set[str] = set()
    units: list[tuple[int, str, str, str]] = []
    for row in rows:
        if row["en"] in seen:
            continue
        seen.add(row["en"])
        units.append((len(units) + 1, row["namespace"], row["key"], row["en"]))

    unit_dir = Path(os.environ["LOCALAPPDATA"]) / "Temp" / f"dj2_t2w{args.wave}_units"
    unit_dir.mkdir(parents=True, exist_ok=True)
    for old in unit_dir.glob("unit_*.txt"):
        old.unlink()

    chunks = [units[i:i + args.size] for i in range(0, len(units), args.size)]
    for n, chunk in enumerate(chunks, 1):
        body = "".join(f"{i}\t{ns}\t{k}\t{en}\n" for i, ns, k, en in chunk)
        # newline="" keeps LF: Python's default turns "\n" into "\r\n" on
        # Windows, and the integrator then reads the CR as part of the English
        # string, so every lookup misses while reporting a clean run.
        (unit_dir / f"unit_{n:02d}.txt").write_text(body, encoding="utf-8", newline="")

    print(json.dumps({
        "wave": args.wave,
        "mods": list(wave_mods),
        "rows": len(rows),
        "unique_english": len(units),
        "by_mod": {m: sum(1 for r in rows if r["namespace"] == m) for m in wave_mods},
        "units": len(chunks),
        "dir": str(unit_dir),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
