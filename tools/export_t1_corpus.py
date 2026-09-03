"""Export the T1 tooltip/message corpus from the deep-audit gap report.

Routes every candidate to the directory its key prefix is allowed to live in
(see the registry-prefix rule) and drops strings that policy says must never be
translated. Writes a frozen manifest plus reviewable TSV batches.

Reads only the audit report and the active mod JARs; never edits a JAR.
"""
from __future__ import annotations

import csv
import json
import os
import re
import zipfile
from collections import OrderedDict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(os.environ["LOCALAPPDATA"]) / "Temp"
AUDIT = TEMP / "dj2_deep_audit_missing.json"
MODS = Path(os.environ["APPDATA"]) / "ElyPrismLauncher" / "instances" / "Divine Journey 2" / "minecraft" / "mods"

MANIFEST = ROOT / "work" / "approved_t1_corpus.json"
BATCH_DIR = TEMP / "dj2_t1_batches"

# Keys under these prefixes may not live in runtime_locale_sources/; they are
# routed to source/tooltips/ instead, which is guarded by different tests.
REGISTRY_PREFIXES = (
    "item.", "tile.", "block.", "fluid.", "entity.", "material.", "oredict.",
    "ore.", "biome.", "dimension.", "enchantment.", "potion.", "itemGroup.",
)

FORMAT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
COLOR = re.compile(r"§.")
URL = re.compile(r"https?://[^\s§]+")
RUNIC = re.compile(r"[\u16A0-\u16FF]")
ASTRAL = re.compile(r"[\U00010000-\U0010FFFF]")


def parse_lang(text: str) -> OrderedDict:
    result: OrderedDict[str, str] = OrderedDict()
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        result[key.strip()] = value
    return result


def tier(row: dict) -> str:
    key = row["key"].lower()
    namespace = row["namespace"]
    english = row["en"]
    if namespace == "groovyscript" and key.startswith("groovyscript.wiki"):
        return "T4_dev_only"
    if key.startswith("config.") or ".config." in key or "gui.config" in key:
        return "T3_config_screen"
    if namespace == "chisel" and ".desc." in key:
        return "T4_dev_only"
    if key.startswith("commands.") or key.startswith("command."):
        return "T3_command_help"
    if namespace in ("reccomplex", "universaltweaks", "endermodpacktweaks", "normalasm", "groovyscript"):
        return "T3_admin_tooling"
    if any(marker in key for marker in (".tooltip", ".desc", ".info", ".lore", ".message")):
        return "T1_tooltip_message"
    if key.startswith("death.") or key.startswith("advancement") or key.startswith("achievement"):
        return "T1_tooltip_message"
    if (
        key.startswith("gui.") or ".gui." in key or key.startswith("jei.") or ".jei." in key
        or key.startswith("key.") or key.startswith("keybind")
    ):
        return "T2_gui_label"
    if len(english.split()) >= 4:
        return "T1_tooltip_message"
    return "T2_gui_label"


def untranslatable(row: dict) -> str | None:
    """Return a reason when policy forbids translating this string."""
    key = row["key"]
    lower = key.lower()
    english = row["en"]
    stripped = english.strip()
    if not stripped:
        return "empty"
    if lower.endswith(".usage") or stripped.startswith("/"):
        return "command_usage_typed_literally"
    if RUNIC.search(english):
        return "runic_puzzle_text"
    if ASTRAL.search(english):
        return "outside_bitmap_font_bmp"
    if URL.search(english) and len(FORMAT.findall(english)) == 0 and len(stripped.split()) <= 2:
        return "bare_url"
    # A string with no letters at all is punctuation, numbers or a separator.
    if not re.search(r"[A-Za-z]", english):
        return "no_translatable_letters"
    # Single mixedCase/snake identifier with no spaces reads as a registry id.
    if " " not in stripped and re.search(r"[_:]|[a-z][A-Z]", stripped):
        return "identifier_like"
    return None


def route(key: str) -> str:
    return "tooltips" if key.startswith(REGISTRY_PREFIXES) else "runtime"


def build_namespace_index() -> dict[str, tuple[str, OrderedDict]]:
    """namespace -> (jar filename, merged English locale) from the active JARs.

    The audit report records no JAR name, so resolve the owner here.

    Two traps this must handle:

    - A namespace can be served by SEVERAL jars (EnderIO plus its Endergy addon
      both ship `assets/enderio/lang/`), so merge every contributor's keys
      instead of keeping only the largest file.
    - 1.12.2 mods normally ship `.lang`, but a few (SpartanShields) put part of
      their strings in `en_us.json`. Reading only `.lang` makes those keys look
      absent from the active JAR. Read both; `.lang` wins on conflict because
      that is the file Forge loads for this MC version.
    """
    merged: dict[str, OrderedDict] = {}
    owner_size: dict[str, int] = {}
    owner_name: dict[str, str] = {}
    owner_locale: dict[str, str] = {}
    pattern = re.compile(r"^assets/([^/]+)/lang/en_us\.(lang|json)$", re.IGNORECASE)
    for jar in sorted(MODS.glob("*.jar")):
        try:
            archive = zipfile.ZipFile(jar)
        except zipfile.BadZipFile:
            continue
        with archive:
            # Sort so .json is read first and .lang can overwrite it.
            members = sorted(
                (m for m in archive.namelist() if pattern.match(m)),
                key=lambda m: 0 if m.lower().endswith(".json") else 1,
            )
            for member in members:
                namespace = pattern.match(member).group(1)
                try:
                    raw = archive.read(member).decode("utf-8-sig")
                except (KeyError, UnicodeDecodeError):
                    continue
                if member.lower().endswith(".json"):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    locale = OrderedDict(
                        (k, v) for k, v in parsed.items() if isinstance(v, str)
                    ) if isinstance(parsed, dict) else OrderedDict()
                else:
                    locale = parse_lang(raw)
                if not locale:
                    continue
                bucket = merged.setdefault(namespace, OrderedDict())
                bucket.update(locale)
                if len(locale) > owner_size.get(namespace, 0):
                    owner_size[namespace] = len(locale)
                    owner_name[namespace] = jar.name
                    # Record the exact spelling the JAR uses. build_pack's
                    # apply_runtime_locale_casing keys the vi_VN/vi_vn choice
                    # off this, so en_US must not be normalised to en_us.
                    owner_locale[namespace] = member.rsplit("/", 1)[-1]
    return {ns: (owner_name[ns], owner_locale[ns], locale) for ns, locale in merged.items()}


def main() -> dict:
    rows = json.loads(AUDIT.read_text(encoding="utf-8"))
    candidates = [row for row in rows if tier(row) == "T1_tooltip_message"]

    dropped: Counter = Counter()
    kept: list[dict] = []
    for row in candidates:
        reason = untranslatable(row)
        if reason:
            dropped[reason] += 1
            continue
        kept.append(row)

    # Verify every surviving key against the live JAR so a stale audit cannot
    # silently inject a key the active mod build no longer ships.
    #
    # The audit report truncates `en` at 300 chars, so compare on that prefix and
    # always carry the JAR's FULL English string into the corpus — translating a
    # truncated source would ship a half sentence.
    index = build_namespace_index()
    verified: list[dict] = []
    drift: list[dict] = []
    for row in kept:
        namespace = row["namespace"]
        owner = index.get(namespace)
        if owner is None:
            drift.append({**row, "reason": "namespace_has_no_active_jar"})
            continue
        jar_name, english_locale, locale = owner
        if row["key"] not in locale:
            drift.append({**row, "reason": "key_absent_from_active_jar"})
            continue
        english = locale[row["key"]]
        if english[: len(row["en"])] != row["en"]:
            drift.append({**row, "reason": "english_source_changed"})
            continue
        verified.append({
            "namespace": namespace,
            "jar": jar_name,
            "english_locale": english_locale,
            "key": row["key"],
            "en": english,
            "route": route(row["key"]),
        })

    verified.sort(key=lambda row: (row["route"], row["namespace"], row["key"]))
    MANIFEST.write_text(
        json.dumps(
            {
                "candidates": len(candidates),
                "dropped": dict(dropped),
                "drift": len(drift),
                "approved": len(verified),
                "rows": verified,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    for old in BATCH_DIR.glob("t1_batch_*.tsv"):
        old.unlink()
    size = 120
    batches = 0
    for index in range(0, len(verified), size):
        chunk = verified[index : index + size]
        path = BATCH_DIR / f"t1_batch_{index // size + 1:02d}.tsv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["namespace", "jar", "english_locale", "key", "route", "en", "vi"],
                delimiter="\t",
            )
            writer.writeheader()
            for row in chunk:
                writer.writerow({**row, "vi": ""})
        batches += 1

    return {
        "candidates": len(candidates),
        "dropped": dict(dropped),
        "drift": len(drift),
        "approved": len(verified),
        "batches": batches,
        "by_route": dict(Counter(row["route"] for row in verified)),
        "manifest": str(MANIFEST),
        "batch_dir": str(BATCH_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
