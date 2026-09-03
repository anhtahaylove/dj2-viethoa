"""Export the remaining untranslated T1 rows (tooltips, messages, achievements).

Scope matches measure_coverage exactly, so the counts here reconcile with the
coverage table rather than drifting from it. A key already shipped under ANY
namespace is not missing: enchantment.cofhcore.* is authored under `cofh` but
ships under `cofhcore`, and treating that as a gap re-translates a live string.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from measure_coverage import DEV_ONLY, is_registry_name, read_english, read_pack  # noqa: E402

OUT = ROOT / "work" / "t1_remaining_corpus.json"

# Player-facing prose: what a tooltip, a chat line or an achievement blurb says.
T1 = re.compile(
    r"(\.desc$|\.description$|\.tooltip|tooltip\.|\.message|message\.|^msg\.|"
    r"\.msg\.|^achievement|achievementPage|^advancement|\.info$|info\.|"
    r"\.hint|chat\.|\.warn|\.error)",
    re.IGNORECASE,
)


def main() -> int:
    english = read_english()
    pack = read_pack()

    # A key that shipped anywhere counts as shipped.
    shipped_anywhere: dict[str, str] = {}
    for entries in pack.values():
        shipped_anywhere.update(entries)

    rows = []
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
                continue
            if not T1.search(key):
                continue
            rows.append({"namespace": namespace, "key": key, "en": value})

    rows.sort(key=lambda r: (r["namespace"], r["key"]))
    OUT.write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    unique = {r["en"] for r in rows}
    print(f"rows {len(rows)}")
    print(f"unique english {len(unique)}")
    print(f"namespaces {len({r['namespace'] for r in rows})}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
