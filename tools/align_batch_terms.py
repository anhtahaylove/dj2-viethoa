"""Align a new batch's term casing with what the pack already ships.

The validator treats "Đã Tắt" and "Đã tắt" as two different translations of one
English term, and it is right to: the same tooltip word rendering differently in
two mods looks like a bug to a player. The shipped strings are the authority —
a new batch adapts to them, never the other way round, so integrating a batch
cannot silently restyle text that is already live.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_TGT = ROOT / "work" / "translated" / "runtime_locales"
# Which batch is "new" changes per wave, so take it from the command line and
# default to the most recent one rather than hard-coding a stale manifest.
DEFAULT_BATCH = ROOT / "work" / "approved_t2_wave1_corpus.json"


def main() -> int:
    batch_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BATCH
    batch_keys = defaultdict(set)
    for row in json.loads(batch_path.read_text(encoding="utf-8"))["rows"]:
        batch_keys[row["namespace"]].add(row["key"])

    out = __import__("subprocess").run(
        [sys.executable, str(ROOT / "tools" / "validate_translated_locales.py")],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    ).stdout

    pattern = re.compile(
        r"inconsistent term '(?P<term>[^']+)': "
        r"'(?P<a>[^']+)' \((?P<akeys>[^)]*)\) \| '(?P<b>[^']+)' \((?P<bkeys>[^)]*)\)"
    )

    def parse(blob: str) -> list[tuple[str, str]]:
        out = []
        for ref in blob.split(", "):
            ref = ref.strip()
            if ":" in ref:
                ns, key = ref.split(":", 1)
                out.append((ns, key))
        return out

    fixes, skipped = [], []
    for m in pattern.finditer(out):
        sides = [(m.group("a"), parse(m.group("akeys"))), (m.group("b"), parse(m.group("bkeys")))]
        new_side = [s for s in sides if all(k in batch_keys.get(ns, ()) for ns, k in s[1])]
        old_side = [s for s in sides if not any(k in batch_keys.get(ns, ()) for ns, k in s[1])]
        # Only rewrite when one side is purely new and the other purely shipped:
        # a term split across both is a pre-existing inconsistency this batch
        # did not cause, and guessing which spelling wins would rewrite live text.
        if len(new_side) != 1 or len(old_side) != 1:
            skipped.append(m.group("term"))
            continue
        want = old_side[0][0]
        # Casing/spacing only. Where the two sides differ in substance — a
        # Vietnamese word vs a kept-English one ("Chất Lỏng" vs "Fluid") — the
        # shipped side is not automatically right, and rewriting would undo a
        # deliberate translation. Those need a human call, so leave them.
        if want.casefold().replace(" ", "") != new_side[0][0].casefold().replace(" ", ""):
            skipped.append(f"{m.group('term')} (differs in wording, not casing)")
            continue
        for ns, key in new_side[0][1]:
            path = RUN_TGT / f"{ns}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            entries = data["entries"] if "entries" in data else data
            if entries.get(key) == want:
                continue
            fixes.append(f"{ns}:{key}: {entries.get(key)!r} -> {want!r}")
            entries[key] = want
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({"fixed": len(fixes), "skipped_ambiguous": skipped}, ensure_ascii=False, indent=1))
    for f in fixes:
        print("  ", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
