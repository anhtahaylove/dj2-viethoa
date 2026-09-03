"""Merge translated batches into the pack's locale files and validate them.

Subagents write `work/audit/batches/<mod>_NN.done.json` ({key: vietnamese}).
This script folds every finished batch into the real locale pair
(`work/runtime_locale_sources/<mod>.lang` + `work/translated/runtime_locales/<mod>.json`),
merging rather than overwriting, then runs the project's own guard.

Usage:
    python merge_batches.py          # merge + validate everything available
    python merge_batches.py --check  # validate only, no writes
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from validate_lang import validate  # noqa: E402

BATCHES = ROOT / "work" / "audit" / "batches"
SRC_DIR = ROOT / "work" / "runtime_locale_sources"
TGT_DIR = ROOT / "work" / "translated" / "runtime_locales"
MISSING = json.loads((ROOT / "work" / "audit" / "missing_by_mod.json").read_text(encoding="utf-8"))
PROTECTED = json.loads((ROOT / "work" / "protected_terms.json").read_text(encoding="utf-8"))


def load_lang(path):
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value
    return out


def main():
    check_only = "--check" in sys.argv
    done = sorted(BATCHES.glob("*.done.json"))
    if not done:
        print("khong co lo nao da dich (*.done.json)")
        return 0

    by_mod = {}
    for path in done:
        mod = path.name.split("_")[0] if "_" in path.name else path.stem
        mod = path.name.rsplit("_", 1)[0]
        data = json.loads(path.read_text(encoding="utf-8"))
        by_mod.setdefault(mod, {}).update(data)

    total_err = 0
    for mod, translated in sorted(by_mod.items()):
        upstream = MISSING.get(mod, {})
        # Keep only keys we actually owe a translation for.
        translated = {k: v for k, v in translated.items() if k in upstream}

        src_path = SRC_DIR / f"{mod}.lang"
        tgt_path = TGT_DIR / f"{mod}.json"
        src = load_lang(src_path)
        tgt = json.loads(tgt_path.read_text(encoding="utf-8")) if tgt_path.exists() else {}

        # Merge, never overwrite an existing translation.
        for key, value in translated.items():
            src.setdefault(key, upstream[key])
            tgt[key] = value

        errors = validate({k: v for k, v in src.items() if k in tgt}, tgt, PROTECTED)
        status = "OK" if not errors else f"{len(errors)} LOI"
        print(f"  {mod:22} {len(translated):>4} moi  ->  {len(tgt):>4} tong   {status}")
        for err in errors[:5]:
            print(f"      {err.code} {err.key} {err.detail[:70]}")
        total_err += len(errors)

        if errors or check_only:
            continue
        src_path.write_text(
            "\n".join(f"{k}={v}" for k, v in src.items()) + "\n", encoding="utf-8"
        )
        tgt_path.write_text(
            json.dumps(tgt, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    print(f"\ntong loi: {total_err}")
    return 1 if total_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
