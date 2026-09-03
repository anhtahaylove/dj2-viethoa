from pathlib import Path
import json, re, sys
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work/runtime_locale_batches"
TARGET = ROOT / "work/runtime_locale_translated_batches"
FMT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
COLOR = re.compile(r"§.")
URL = re.compile(r"https?://[^\s§]+")
SEPARATORS = ("$", "#")

def token_sequences(text):
    return {"format": FMT.findall(text), "color": COLOR.findall(text), "url": URL.findall(text)}

def validate():
    errors=[]; report={}
    sources=sorted(SOURCE.rglob("*.json"))
    for src in sources:
        rel=src.relative_to(SOURCE); dst=TARGET/rel
        if not dst.exists():
            errors.append(f"missing output: {rel.as_posix()}"); continue
        try:
            a=json.loads(src.read_text(encoding="utf-8")); b=json.loads(dst.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"json error {rel.as_posix()}: {exc}"); continue
        if not isinstance(a,dict) or not isinstance(b,dict): errors.append(f"not object: {rel.as_posix()}"); continue
        if list(a)!=list(b): errors.append(f"key/order mismatch: {rel.as_posix()}")
        changed=0
        for key,value in a.items():
            if key not in b: continue
            translated=b[key]
            if not isinstance(translated,str): errors.append(f"non-string {rel.as_posix()}:{key}"); continue
            changed += value != translated
            ta,tb=token_sequences(value),token_sequences(translated)
            if ta!=tb: errors.append(f"token mismatch {rel.as_posix()}:{key}: {ta} != {tb}")
            for sep in SEPARATORS:
                if value.count(sep)!=translated.count(sep): errors.append(f"separator {sep} mismatch {rel.as_posix()}:{key}")
            if "\n" in translated or "\r" in translated: errors.append(f"raw newline {rel.as_posix()}:{key}")
        report[rel.as_posix()]={"entries":len(a),"changed":changed}
    return report, errors
if __name__=="__main__":
    report,errors=validate(); print(json.dumps({"report":report,"errors":errors},ensure_ascii=False,indent=2)); sys.exit(bool(errors))
