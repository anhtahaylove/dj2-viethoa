"""Triage the keys whose Vietnamese value is byte-identical to the English.

Sorting these is NOT the same as finding gaps: most are proper nouns the pack
deliberately preserves. This script only proposes buckets and gathers the
evidence; a human still adjudicates `needs_review`.

Buckets:
  keep_proper_name  a registered item/block/entity name, or an aspect/ritual
                    name -- preserved on purpose, matches PROTECTED_TERMS
  keep_untranslatable  URL, command usage, pure symbol/number, single ASCII
                    token, meme/subtitle, runic/ciphered text
  keep_no_vietnamese_needed  the English is already what a Vietnamese player
                    reads: proper noun with no prose around it (Title Case,
                    no function words)
  needs_review      real prose (>=2 English function words, not Title Case)
                    that looks like a genuine miss

Writes a TSV so the reviewer can adjudicate row by row.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import zipfile
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(os.environ["LOCALAPPDATA"]) / "Temp"
UNTRANSLATED = TEMP / "dj2_deep_audit_untranslated.json"
PROTECTED = ROOT / "work" / "protected_terms.json"
OUT_TSV = TEMP / "dj2_identical_triage.tsv"
OUT_JSON = ROOT / "work" / "identical_english_triage.json"

# Function words are the strongest signal that a string is prose rather than a
# name. A Title-Case string with none of these is almost always a proper noun.
FUNCTION_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "for", "with", "without", "from", "by",
    "and", "or", "but", "if", "when", "while", "this", "that", "these",
    "those", "it", "its", "you", "your", "will", "can", "cannot", "not",
    "no", "yes", "all", "any", "each", "into", "out", "up", "down", "over",
    "than", "then", "there", "here", "how", "what", "which", "who", "does",
    "do", "has", "have", "had", "must", "should", "may", "might", "would",
    "click", "press", "use", "used", "using", "place", "placed", "right",
    "left", "shift", "hold", "requires", "required", "allows", "adds",
}

URL = re.compile(r"https?://")
COMMAND = re.compile(r"^\s*/")
SYMBOLIC = re.compile(r"^[\W\d_§%]+$")
RUNIC = re.compile(r"[\u16A0-\u16FF]")
FORMAT_ONLY = re.compile(r"^[\s%sdn§.\d]+$")


def strip_codes(text: str) -> str:
    text = re.sub(r"§.", "", text)
    text = re.sub(r"%(?:n|%|(?:\d+\$)?[-#+0,(<]*\d*(?:\.\d+)?[a-zA-Z])", " ", text)
    return text


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", strip_codes(text))


def is_title_case(text: str) -> bool:
    tokens = words(text)
    if not tokens:
        return False
    significant = [t for t in tokens if t.lower() not in {"of", "the", "and", "a", "an"}]
    return bool(significant) and all(t[:1].isupper() for t in significant)


def function_word_count(text: str) -> int:
    return sum(1 for w in words(text) if w.lower() in FUNCTION_WORDS)


def load_protected() -> set[str]:
    if not PROTECTED.is_file():
        return set()
    try:
        data = json.loads(PROTECTED.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    terms: set[str] = set()
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, str):
                terms.add(value.casefold())
            elif isinstance(value, list):
                terms.update(str(v).casefold() for v in value)
    elif isinstance(data, list):
        terms.update(str(v).casefold() for v in data)
    return terms


REGISTRY_PREFIXES = (
    "item.", "tile.", "block.", "fluid.", "entity.", "material.", "oredict.",
    "ore.", "biome.", "dimension.", "enchantment.", "potion.", "itemGroup.",
)

# Key families that name a thing rather than describe it.
NAME_KEY = re.compile(
    r"(^|\.)(name|title|aspect|entry|category|ritual|spell|rite|tab|group"
    r"|modifier|material|trait|achievement|advancement)(\.|$)",
    re.IGNORECASE,
)
ASPECT_KEY = re.compile(r"^tc\.aspect\.|^aspect\.", re.IGNORECASE)


def classify(row: dict, protected: set[str]) -> tuple[str, str]:
    key, en = row["key"], row["en"]
    bare = strip_codes(en).strip()

    if URL.search(en):
        return "keep_untranslatable", "contains a URL"
    if COMMAND.match(bare) or ".usage" in key.lower() or key.lower().startswith("commands."):
        return "keep_untranslatable", "command syntax typed literally"
    if RUNIC.search(en):
        return "keep_untranslatable", "runic/ciphered text"
    if not bare or SYMBOLIC.match(bare) or FORMAT_ONLY.match(en):
        return "keep_untranslatable", "symbols/format tokens only"
    if len(words(en)) == 1 and len(bare) <= 24:
        return "keep_untranslatable", "single token"

    if bare.casefold() in protected:
        return "keep_proper_name", "matches a PROTECTED_TERM"
    if key.startswith(REGISTRY_PREFIXES) and NAME_KEY.search(key):
        return "keep_proper_name", "registry name key"
    if ASPECT_KEY.search(key):
        return "keep_proper_name", "Thaumcraft aspect name"

    fw = function_word_count(en)
    title = is_title_case(en)

    if title and fw == 0:
        return "keep_no_vietnamese_needed", "Title Case proper noun, no prose"
    if NAME_KEY.search(key) and fw <= 1 and len(words(en)) <= 6:
        return "keep_no_vietnamese_needed", "short name-shaped label"
    if fw >= 2:
        return "needs_review", f"prose: {fw} English function words"
    if len(words(en)) >= 6:
        return "needs_review", "long string, few function words"
    return "needs_review", "ambiguous short label"


def main() -> dict:
    rows = json.loads(UNTRANSLATED.read_text(encoding="utf-8"))
    protected = load_protected()
    buckets: Counter = Counter()
    reasons: Counter = Counter()
    out: list[dict] = []
    for row in rows:
        bucket, reason = classify(row, protected)
        buckets[bucket] += 1
        reasons[f"{bucket}:{reason}"] += 1
        out.append({**row, "bucket": bucket, "reason": reason})

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    review = [r for r in out if r["bucket"] == "needs_review"]
    review.sort(key=lambda r: (r["namespace"], r["key"]))
    lines = ["namespace\tkey\tbucket\treason\ten\tvi"]
    for r in review:
        en = r["en"].replace("\t", " ")
        lines.append(f"{r['namespace']}\t{r['key']}\t{r['bucket']}\t{r['reason']}\t{en}\t")
    OUT_TSV.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    return {
        "total": len(rows),
        "buckets": dict(buckets),
        "protected_terms_loaded": len(protected),
        "review_tsv": str(OUT_TSV),
        "triage_json": str(OUT_JSON),
        "top_reasons": dict(reasons.most_common(12)),
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
