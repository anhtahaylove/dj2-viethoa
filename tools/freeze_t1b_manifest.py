"""Freeze the second T1 batch into a manifest the integrator can consume.

Every row is re-verified against the live JAR: the English text must still be
exactly what the mod ships, so a stale corpus cannot silently overwrite a
string that changed. Reuses export_t1_corpus's namespace index and routing so
the two batches cannot drift apart.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from export_t1_corpus import build_namespace_index, route  # noqa: E402

SOURCE = ROOT / "work" / "t1_remaining_corpus.json"
OUT = ROOT / "work" / "approved_t1b_corpus.json"


def main() -> int:
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    index = build_namespace_index()

    verified, drift, dropped = [], [], []
    for row in rows:
        entry = index.get(row["namespace"])
        if entry is None:
            dropped.append(f"{row['namespace']}:{row['key']}: namespace not in any active jar")
            continue
        jar, locale_name, locale = entry
        english = locale.get(row["key"])
        if english is None:
            dropped.append(f"{row['namespace']}:{row['key']}: key absent from jar")
            continue
        if english != row["en"]:
            drift.append(f"{row['namespace']}:{row['key']}: jar text differs from corpus")
            continue
        verified.append(
            {
                "namespace": row["namespace"],
                "jar": jar,
                "english_locale": locale_name,
                "key": row["key"],
                "en": english,
                "route": route(row["key"]),
            }
        )

    verified.sort(key=lambda r: (r["route"], r["namespace"], r["key"]))
    payload = {
        "candidates": len(rows),
        "dropped": dropped,
        "drift": drift,
        "approved": len(verified),
        "rows": verified,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps({
        "candidates": len(rows),
        "approved": len(verified),
        "dropped": len(dropped),
        "drift": len(drift),
        "by_route": dict(Counter(r["route"] for r in verified)),
    }, indent=2))
    for line in (drift + dropped)[:10]:
        print("  ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
