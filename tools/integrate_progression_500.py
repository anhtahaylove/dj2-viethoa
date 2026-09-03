"""Integrate the approved progression-priority localization batch.

The audit manifest and translated TSVs live in the user's temporary review area;
this script harvests only their exact keys from the active mod locale sources and
writes normal runtime-locale source/translation files. It never edits a mod JAR.
"""
from __future__ import annotations

import csv
import json
import os
import re
import zipfile
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(os.environ["LOCALAPPDATA"]) / "Temp"
MANIFEST = TEMP / "dj2_approved_progression_500.tsv"
PARTS = [TEMP / f"dj2_translate500_part{i}_vi.tsv" for i in range(1, 5)]
MODS = Path(os.environ["APPDATA"]) / "ElyPrismLauncher" / "instances" / "Divine Journey 2" / "minecraft" / "mods"
SOURCE_DIR = ROOT / "work" / "runtime_locale_sources"
TARGET_DIR = ROOT / "work" / "translated" / "runtime_locales"
META_DIR = ROOT / "work" / "runtime_locale_meta"

FORMAT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
COLOR = re.compile(r"§.")
URL = re.compile(r"https?://[^\s§]+")


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_lang(text: str) -> OrderedDict[str, str]:
    result: OrderedDict[str, str] = OrderedDict()
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        result[key.strip()] = value
    return result


def load_jar_locale(jar: Path, namespace: str) -> tuple[str, OrderedDict[str, str]]:
    candidates = (f"assets/{namespace}/lang/en_us.lang", f"assets/{namespace}/lang/en_US.lang")
    with zipfile.ZipFile(jar) as archive:
        names = set(archive.namelist())
        member = next((name for name in candidates if name in names), None)
        if not member:
            raise RuntimeError(f"missing English locale for {namespace} in {jar.name}")
        return Path(member).name, parse_lang(archive.read(member).decode("utf-8-sig"))


def sequence(text: str) -> tuple[list[str], list[str], list[str]]:
    return FORMAT.findall(text), COLOR.findall(text), URL.findall(text)


def main() -> dict[str, int]:
    approved = rows(MANIFEST)
    translated = [row for part in PARTS for row in rows(part)]
    approved_ids = [(row["namespace"], row["key"]) for row in approved]
    translated_ids = [(row["namespace"], row["key"]) for row in translated]
    if len(approved) != 500 or len(set(approved_ids)) != 500:
        raise RuntimeError("approved manifest must contain exactly 500 unique rows")
    if translated_ids != approved_ids:
        raise RuntimeError("translated TSV rows/order do not exactly match the approved manifest")

    by_namespace: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for source, target in zip(approved, translated):
        if target["en"] != source["en"] or target["namespace"] != source["namespace"] or target["key"] != source["key"]:
            raise RuntimeError(f"source drift at {source['namespace']}:{source['key']}")
        if not target["vi"] or target["vi"] == source["en"]:
            raise RuntimeError(f"untranslated value at {source['namespace']}:{source['key']}")
        if sequence(source["en"]) != sequence(target["vi"]):
            raise RuntimeError(f"token/color/url mismatch at {source['namespace']}:{source['key']}")
        if source["en"].count("\\n") != target["vi"].count("\\n") or "\n" in target["vi"] or "\r" in target["vi"]:
            raise RuntimeError(f"newline mismatch at {source['namespace']}:{source['key']}")
        by_namespace.setdefault(source["namespace"], []).append(target)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for namespace, group in by_namespace.items():
        jar_name = next(row["jar"] for row in approved if row["namespace"] == namespace)
        jar = MODS / jar_name
        if not jar.is_file():
            raise RuntimeError(f"missing active mod JAR: {jar}")
        english_locale, locale = load_jar_locale(jar, namespace)
        selected: OrderedDict[str, str] = OrderedDict()
        output: OrderedDict[str, str] = OrderedDict()
        translations = {row["key"]: row["vi"] for row in group}
        expected_en = {row["key"]: row["en"] for row in group}
        for key in locale:
            if key not in translations:
                continue
            if locale[key] != expected_en[key]:
                raise RuntimeError(f"active JAR source differs at {namespace}:{key}")
            selected[key] = locale[key]
            output[key] = translations[key]
        if set(selected) != set(translations):
            missing = sorted(set(translations) - set(selected))
            raise RuntimeError(f"missing active JAR keys for {namespace}: {missing[:10]}")
        source_path = SOURCE_DIR / f"{namespace}.lang"
        target_path = TARGET_DIR / f"{namespace}.json"
        existing_source = parse_lang(source_path.read_text(encoding="utf-8")) if source_path.exists() else OrderedDict()
        merged_source = OrderedDict(existing_source)
        merged_source.update(selected)
        source_path.write_text(
            "".join(f"{key}={value}\n" for key, value in merged_source.items()), encoding="utf-8", newline="\n"
        )
        existing_target = json.loads(target_path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict) if target_path.exists() else OrderedDict()
        merged_target = OrderedDict(existing_target)
        merged_target.update(output)
        # Runtime translations mirror the exact active English source. Prune
        # stale keys left by an older mod build instead of growing forever.
        merged_target = OrderedDict((key, merged_target[key]) for key in merged_source if key in merged_target)
        if set(merged_target) != set(merged_source):
            missing = sorted(set(merged_source) - set(merged_target))
            raise RuntimeError(f"missing translations after merge for {namespace}: {missing[:10]}")
        target_path.write_text(
            json.dumps(merged_target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        (META_DIR / f"{namespace}.json").write_text(
            json.dumps({"jar": jar_name, "english_locale": english_locale, "keys": len(selected)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        written += len(selected)
    return {"namespaces": len(by_namespace), "keys": written}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
