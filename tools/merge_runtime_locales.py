from pathlib import Path
from collections import OrderedDict
import json, sys
import validate_runtime_locales
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"work/runtime_locale_batches"
TARGET=ROOT/"work/runtime_locale_translated_batches"
OUTPUT=ROOT/"work/translated/runtime_locales"

def merge():
    report,errors=validate_runtime_locales.validate()
    if errors: raise RuntimeError("runtime locale validation failed:\n"+"\n".join(errors))
    OUTPUT.mkdir(parents=True,exist_ok=True)
    expected=set()
    for nsdir in sorted(p for p in SOURCE.iterdir() if p.is_dir()):
        merged=OrderedDict()
        for src in sorted(nsdir.glob("*.json")):
            out=TARGET/nsdir.name/src.name
            data=json.loads(out.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
            duplicate=set(merged)&set(data)
            if duplicate: raise RuntimeError(f"duplicate keys in {nsdir.name}: {sorted(duplicate)[:10]}")
            merged.update(data)
        dest=OUTPUT/f"{nsdir.name}.json";dest.write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");expected.add(dest.name)
    # Keep hand-authored namespace overlays outside the batch tree (e.g. abyssalcraft).
    return {p.stem:len(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(OUTPUT.glob("*.json"))}
if __name__=="__main__": print(json.dumps(merge(),ensure_ascii=False,indent=2))
