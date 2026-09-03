"""Freeze one T2 wave into the manifest shape the integrator consumes.

Same contract as the T1 freeze: every row is re-checked against the live JAR, so
a stale candidate list cannot ship text the mod no longer has. Route follows the
registry prefix, exactly as the T1 path does.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from export_t1_corpus import REGISTRY_PREFIXES, build_namespace_index  # noqa: E402

def manifest_path() -> Path:
    """Wave number comes from argv so a later wave cannot silently refreeze wave 1."""
    wave = sys.argv[1] if len(sys.argv) > 1 else "1"
    return ROOT / "work" / f"approved_t2_wave{wave}_corpus.json"


def main() -> int:
    SRC = manifest_path()
    rows = json.loads(SRC.read_text(encoding="utf-8"))["rows"]
    index = build_namespace_index()

    verified, drift = [], []
    for row in rows:
        ns = row["namespace"]
        if ns not in index:
            drift.append(f"{ns}: namespace not in any active JAR")
            continue
        jar, en_locale, entries = index[ns]
        live = entries.get(row["key"])
        if live is None:
            drift.append(f"{ns}:{row['key']}: key gone from JAR")
            continue
        if live != row["en"]:
            drift.append(f"{ns}:{row['key']}: English changed")
            continue
        verified.append({
            "namespace": ns,
            "jar": jar,
            "english_locale": en_locale,
            "key": row["key"],
            "en": row["en"],
            "route": "tooltips" if row["key"].startswith(REGISTRY_PREFIXES) else "runtime",
        })

    verified.sort(key=lambda r: (r["route"], r["namespace"], r["key"]))
    SRC.write_text(
        json.dumps({"approved": len(verified), "drift": drift, "rows": verified}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(json.dumps({
        "candidates": len(rows),
        "approved": len(verified),
        "drift": len(drift),
        "by_route": {r: sum(1 for v in verified if v["route"] == r) for r in ("runtime", "tooltips")},
    }, indent=1))
    for d in drift[:10]:
        print("  ", d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
