"""Prepare and render TConstruct book prose localization."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "tconstruct"
BATCH = ROOT / "work" / "tconstruct_batches"
TRANS = ROOT / "work" / "translated" / "tconstruct" / "tconstruct.json"
OUT = ROOT / "work" / "tconstruct_vi"


def walk(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "text" and isinstance(child, str) and child.strip():
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


def encode(value):
    return value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")


def decode(value):
    return re.sub(r"\\([\\rn])", lambda match: {"\\": "\\", "r": "\r", "n": "\n"}[match.group(1)], value)


def prepare():
    BATCH.mkdir(parents=True, exist_ok=True)
    entries, index = {}, {}
    for file in sorted(SOURCE.rglob("*.json")):
        relative = file.relative_to(SOURCE)
        data = json.loads(file.read_text(encoding="utf-8"))
        for field_path, value in walk(data):
            key = relative.as_posix() + "::" + "/".join(map(str, field_path))
            entries[key] = encode(value)
            index[key] = {"relative": relative.as_posix(), "path": list(field_path)}
    lines = ["# TConstruct book prose; technical titles and names stay English."] + [f"{key}={value}" for key, value in entries.items()]
    (BATCH / "tconstruct.lang").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (BATCH / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("fields", len(entries), "chars", sum(map(len, entries.values())))


def render():
    index = json.loads((BATCH / "index.json").read_text(encoding="utf-8"))
    translations = json.loads(TRANS.read_text(encoding="utf-8"))
    if set(index) != set(translations):
        raise RuntimeError(f"coverage {len(translations)}/{len(index)}")
    docs = {}
    for key, info in index.items():
        relative = Path(info["relative"])
        document = docs.setdefault(relative, json.loads((SOURCE / relative).read_text(encoding="utf-8")))
        put(document, info["path"], decode(translations[key]))
    for relative, document in docs.items():
        parts = list(relative.parts)
        parts[parts.index("en_us")] = "vi_vn"
        target = OUT / Path(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # TConstruct also has a line-oriented language file inside the book locale.
    source_lang = SOURCE / "assets/tconstruct/book/en_us/language.lang"
    target_lang = OUT / "assets/tconstruct/book/vi_vn/language.lang"
    target_lang.parent.mkdir(parents=True, exist_ok=True)
    target_lang.write_bytes(source_lang.read_bytes())
    print("rendered", len(docs), "json files")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    prepare()
    if args.render:
        render()
