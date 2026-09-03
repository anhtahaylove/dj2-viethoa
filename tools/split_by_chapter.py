"""Split Divine Journey 2 BetterQuesting language entries into chapter batches."""
import json
import re
from pathlib import Path

from validate_lang import load_lang

ROOT = Path(__file__).resolve().parents[1]
QUEST_DB = ROOT.parent / "Divine_Journey_2.23.4_Server_Pack" / "config" / "betterquesting" / "DefaultQuests.json"
SOURCE = ROOT / "source" / "betterquesting-quests.lang"
OUT = ROOT / "work" / "batches"
KEY_RE = re.compile(r"dj2\.quest\.db\.(\d+)\.(title|desc)$")

lang, duplicates = load_lang(SOURCE)
if duplicates:
    raise SystemExit(f"Duplicate keys in source: {duplicates[:5]}")
db = json.loads(QUEST_DB.read_text(encoding="utf-8"))
quest_lines = db["questLines:9"]
quest_to_chapter = {}
chapters = {}
for raw_key, value in quest_lines.items():
    index = int(raw_key.split(":", 1)[0])
    props = value["properties:10"]["betterquesting:10"]
    title_key = props["name:8"]
    desc_key = props["desc:8"]
    chapters[index] = {
        "chapter_index": index,
        "title_key": title_key,
        "chapter_title_en": lang[title_key],
        "desc_key": desc_key,
        "chapter_desc_en": lang[desc_key],
        "entries": [
            {"key": title_key, "en": lang[title_key]},
            {"key": desc_key, "en": lang[desc_key]},
        ],
    }
    for quest in value.get("quests:9", {}).values():
        quest_to_chapter[int(quest["id:3"])] = index

orphans = {"chapter_index": None, "chapter_title_en": "Orphan quests", "entries": []}
for key, value in lang.items():
    match = KEY_RE.fullmatch(key)
    if not match:
        continue
    quest_id = int(match.group(1))
    target = chapters.get(quest_to_chapter.get(quest_id), orphans)
    target["entries"].append({"key": key, "en": value})

OUT.mkdir(parents=True, exist_ok=True)
written = []
for index, payload in sorted(chapters.items()):
    path = OUT / f"ql_{index:02d}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written.append(path)
path = OUT / "orphans.json"
path.write_text(json.dumps(orphans, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
written.append(path)
count = sum(len(json.loads(p.read_text(encoding="utf-8"))["entries"]) for p in written)
if count != len(lang):
    raise SystemExit(f"Split mismatch: wrote {count}, source has {len(lang)}")
print(f"batches={len(written)} entries={count}")
for p in written:
    data = json.loads(p.read_text(encoding="utf-8"))
    print(f"{p.name}\t{len(data['entries'])}\t{data['chapter_title_en']}")
