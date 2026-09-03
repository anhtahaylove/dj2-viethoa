"""Extract English item/block/entity names that translations must preserve."""
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS = ROOT.parent / "Divine_Journey_2.23.4_Server_Pack" / "mods"
OUT = ROOT / "work" / "protected_terms.json"
NAME_KEY = re.compile(r"^(item|tile|block|fluid|entity)\..*\.name$")
COMMON = {
    "Stone", "Water", "Lava", "Wood", "Glass", "Sand", "Dirt", "Ice",
    "Coal", "Iron", "Gold", "Bucket", "Seeds", "Torch", "Chest", "Door",
}

names = set()
for jar in MODS.glob("*.jar"):
    try:
        with zipfile.ZipFile(jar) as archive:
            for member in archive.namelist():
                if not re.search(r"/lang/en_us\.lang$", member, re.I):
                    continue
                text = archive.read(member).decode("utf-8-sig", "replace")
                for line in text.splitlines():
                    if "=" not in line or line.lstrip().startswith("#"):
                        continue
                    key, value = (part.strip() for part in line.split("=", 1))
                    if NAME_KEY.match(key) and value and "%s" not in value and len(value) > 3:
                        names.add(value)
    except (zipfile.BadZipFile, KeyError):
        pass

keep = sorted(name for name in names if ((" " in name) or len(name) > 8) and name not in COMMON)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(keep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"protected_terms={len(keep)} output={OUT}")
