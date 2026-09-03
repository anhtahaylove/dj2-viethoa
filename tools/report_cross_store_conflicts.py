"""Report keys whose Vietnamese differs between two translated stores.

The build merges several trees into one lang file per namespace, so the same
key living in two stores with two wordings ships as a coin flip.
"""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    store: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for path in (ROOT / "work" / "translated").rglob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for key, value in data.items():
            if isinstance(value, str):
                store[key][rel] = value

    conflicts = {k: v for k, v in store.items() if len(set(v.values())) > 1}
    print(f"conflicting keys: {len(conflicts)}")
    for key, places in sorted(conflicts.items()):
        print(f"\n{key}")
        for rel, value in places.items():
            print(f"   {rel}: {value[:70]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
