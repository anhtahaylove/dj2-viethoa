"""Extract translatable Patchouli JSON fields, translate, and recreate vi_vn trees."""
from __future__ import annotations

import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "patchouli"
BATCH = ROOT / "work" / "patchouli_batches"
TRANS = ROOT / "work" / "translated" / "patchouli"
OUT = ROOT / "work" / "patchouli_vi"
TRANSLATOR = ROOT / "work" / "translate_lang_json.py"
FIELDS = {"name", "description", "text", "title"}


def load_patchouli_json(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some shipped 1.12 Patchouli resources use Java/Gson's tolerated \'
        # escape, which strict Python JSON rejects. JSON does not need escaped
        # apostrophes, so this normalization is lossless.
        return json.loads(text.replace("\\'", "'"))


def walk(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FIELDS and isinstance(child, str) and child.strip():
                yield path + (key,), child
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


def put(value, path, translated):
    node = value
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = translated


def key_for(relative, path):
    return relative.as_posix() + "::" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in path)


def prepare():
    BATCH.mkdir(parents=True, exist_ok=True)
    groups = {}
    index = {}
    for file in sorted(SOURCE.rglob("*.json")):
        rel = file.relative_to(SOURCE)
        namespace = rel.parts[1] if rel.parts and rel.parts[0] == "assets" else rel.parts[0]
        data = load_patchouli_json(file)
        for field_path, text in walk(data):
            key = key_for(rel, field_path)
            groups.setdefault(namespace, {})[key] = text
            index[key] = {"relative": rel.as_posix(), "path": list(field_path)}
    # JSON text can contain literal newlines and backslashes, which are unsafe in
    # the line-oriented .lang transport. Encode both reversibly before translation.
    for namespace, entries in groups.items():
        encoded = {
            key: value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
            for key, value in entries.items()
        }
        lines = ["# Patchouli fields extracted deterministically."] + [f"{key}={value}" for key, value in encoded.items()]
        (BATCH / f"{namespace}.lang").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (BATCH / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("files", len(list(SOURCE.rglob('*.json'))), "fields", len(index), "groups", len(groups))
    return sorted(groups)


def translate_one(namespace):
    output = TRANS / f"{namespace}.json"
    cp = subprocess.run([sys.executable, str(TRANSLATOR), str(BATCH / f"{namespace}.lang"), str(output), "--chunk", "10"], capture_output=True, text=True, encoding="utf-8", timeout=10800)
    return namespace, cp.returncode, cp.stdout[-500:], cp.stderr[-500:]


def render():
    index = json.loads((BATCH / "index.json").read_text(encoding="utf-8"))
    translations = {}
    for path in TRANS.glob("*.json"):
        translations.update(json.loads(path.read_text(encoding="utf-8")))
    if set(index) != set(translations):
        raise RuntimeError(f"translation coverage mismatch: {len(translations)}/{len(index)}")
    docs = {}
    for key, info in index.items():
        rel = Path(info["relative"])
        data = docs.setdefault(rel, load_patchouli_json(SOURCE / rel))
        encoded = translations[key]
        # Reverse the line-oriented transport encoding without treating arbitrary
        # backslash sequences as Python/JSON escapes.
        decoded = re.sub(r"\\([\\rn])", lambda match: {"\\": "\\", "r": "\r", "n": "\n"}[match.group(1)], encoded)
        put(data, info["path"], decoded)
    rendered = set()
    for rel, data in docs.items():
        parts = list(rel.parts)
        parts[parts.index("en_us")] = "vi_vn"
        dest = OUT / Path(*parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rendered.add(rel)
    # Copy structural templates with no player-facing text so the translated
    # locale tree has exact source-file coverage.
    for source in SOURCE.rglob("*.json"):
        rel = source.relative_to(SOURCE)
        if rel in rendered:
            continue
        parts = list(rel.parts)
        parts[parts.index("en_us")] = "vi_vn"
        dest = OUT / Path(*parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(load_patchouli_json(source), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("rendered", len(list(OUT.rglob("*.json"))))


def main():
    groups = prepare()
    TRANS.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        for result in concurrent.futures.as_completed([executor.submit(translate_one, group) for group in groups]):
            print(result.result(), flush=True)
    render()


if __name__ == "__main__":
    main()
