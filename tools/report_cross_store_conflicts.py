"""Report keys whose Vietnamese differs between two stores that MERGE together.

The build merges several translated stores into one lang file per namespace, so
the same key living in two stores with two wordings ships as a coin flip.

Not every duplicate key is a conflict, though, and the earlier version of this
report conflated three different situations:

  * Same key, same value in both stores -- nothing ships differently.
  * Same key, different values, but the stores feed DIFFERENT namespaces --
    they never meet during the merge, and the English upstream usually differs
    in meaning too (`gui.close` in two mods is two unrelated strings).
  * Same key, different values, and both stores feed the SAME namespace --
    the only case where the shipped byte is decided by dict ordering.

Only the third case is actionable, so it is what `real_conflicts()` returns and
what the pytest gate asserts stays empty. `--all` prints the benign groups too,
which is useful when auditing but must not gate the build.
"""
import argparse
import collections
import json
from pathlib import Path

import build_pack

ROOT = Path(__file__).resolve().parents[1]


def store_namespaces():
    """Map each translated store file to the namespace(s) the build merges it into.

    Derived from build_pack.lang_family_specs() rather than re-listed here, so a
    new family or a changed `p2_`/`books_` prefix cannot drift out of sync with
    what the artifact actually contains.
    """
    owners = collections.defaultdict(set)
    for spec in build_pack.lang_family_specs():
        source_dir = spec["source_dir"]
        include = spec["include_stems"]
        for source_path in sorted(source_dir.glob("*.lang")):
            if include is not None and source_path.stem not in include:
                continue
            translated = spec["translated_dir"] / f"{source_path.stem}.json"
            if not translated.exists():
                continue
            rel = translated.relative_to(ROOT).as_posix()
            owners[rel].add(spec["to_namespace"](source_path.stem))
    return owners


def load_stores():
    """key -> {store path: value} for every translated JSON store."""
    store = collections.defaultdict(dict)
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
    return store


def real_conflicts(store=None, owners=None):
    """Duplicate keys that ship a coin-flip value: same namespace, different text.

    Returns {key: {namespace: {store path: value}}}. Empty is the healthy state.
    """
    store = load_stores() if store is None else store
    owners = store_namespaces() if owners is None else owners
    found = {}
    for key, places in store.items():
        if len(places) < 2 or len(set(places.values())) < 2:
            continue
        by_namespace = collections.defaultdict(dict)
        for rel, value in places.items():
            for namespace in owners.get(rel, ()):
                by_namespace[namespace][rel] = value
        clashing = {
            namespace: mapping
            for namespace, mapping in by_namespace.items()
            if len(mapping) > 1 and len(set(mapping.values())) > 1
        }
        if clashing:
            found[key] = clashing
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true",
                    help="also list benign duplicates (same value, or different namespaces)")
    args = ap.parse_args()

    store = load_stores()
    owners = store_namespaces()
    conflicts = real_conflicts(store, owners)

    print(f"real conflicts (same namespace, different value): {len(conflicts)}")
    for key, namespaces in sorted(conflicts.items()):
        print(f"\n{key}")
        for namespace, mapping in sorted(namespaces.items()):
            print(f"  namespace {namespace}")
            for rel, value in sorted(mapping.items()):
                print(f"     {rel}: {value[:70]!r}")

    if args.all:
        duplicates = {k: v for k, v in store.items() if len(v) > 1}
        identical = [k for k, v in duplicates.items() if len(set(v.values())) == 1]
        differing = sorted(set(duplicates) - set(identical) - set(conflicts))
        print(f"\nbenign: {len(identical)} duplicate keys with identical values")
        print(f"benign: {len(differing)} keys differing only across separate namespaces")
        for key in differing:
            print(f"\n{key}")
            for rel, value in sorted(store[key].items()):
                print(f"   {rel} -> {sorted(owners.get(rel, ())) or ['(unshipped)']}: {value[:60]!r}")

    return 1 if conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
