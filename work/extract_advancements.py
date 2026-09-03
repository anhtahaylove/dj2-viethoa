import collections
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = Path.home() / "AppData/Local/Temp/dj2-book-extra-raw.json"


def parse_lang(text):
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "//")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out.setdefault(key, value)
    return out


def main():
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    entries = {}
    missing = []
    for record in raw["records"]:
        requests = [
            (adv["path"], field["field"], field["value"]["translate"])
            for adv in record["advancements"]
            for field in adv.get("fields", [])
            if field.get("kind") == "translate"
        ]
        if not requests:
            continue
        with zipfile.ZipFile(record["path"]) as archive:
            locales = []
            for name in archive.namelist():
                lower = name.lower()
                if "/lang/" not in lower or not lower.endswith(("en_us.lang", "en_us.json")):
                    continue
                try:
                    text = archive.read(name).decode("utf-8-sig")
                    data = json.loads(text) if lower.endswith(".json") else parse_lang(text)
                    locales.append((name, data))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            for advancement, field, key in requests:
                hits = [(name, data[key]) for name, data in locales if key in data]
                if not hits:
                    missing.append({"jar": record["jar"], "advancement": advancement, "field": field, "key": key})
                    continue
                locale_path, source = hits[0]
                item = {
                    "jar": record["jar"], "advancement": advancement, "field": field,
                    "key": key, "source": source, "namespace": locale_path.split("/")[1],
                    "locale_path": locale_path,
                }
                previous = entries.get(key)
                if previous and (previous["source"], previous["namespace"]) != (source, item["namespace"]):
                    raise RuntimeError(f"conflicting source for {key}")
                entries[key] = item

    audit = {"entries": dict(sorted(entries.items())), "missing": missing}
    (ROOT / "work/audit/advancement_inventory.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    source_dir = ROOT / "source/advancements"
    source_dir.mkdir(parents=True, exist_ok=True)
    for old in source_dir.glob("*.lang"):
        old.unlink()
    grouped = collections.defaultdict(dict)
    for key, item in entries.items():
        grouped[item["namespace"]][key] = item["source"]
    for namespace, data in grouped.items():
        (source_dir / f"{namespace}.lang").write_text(
            "\n".join(f"{key}={value}" for key, value in sorted(data.items())) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "resolved": len(entries), "missing_occurrences": len(missing),
        "missing_unique": len({item["key"] for item in missing}), "namespaces": len(grouped)
    }, indent=2))


if __name__ == "__main__":
    main()
