"""Mine a glossary from the Vietnamese already shipped in the pack.

Parallel translators drift: one writes "Kich hoat", the next "Bat". The pack has
15k translated lines already, so the house style is a measurable fact, not a
preference. This extracts it so every batch starts from the same vocabulary.

Two products:
  term_map    English phrase -> the Vietnamese the pack already uses (only when
              that mapping is unambiguous across the whole pack)
  kept_english  English words the pack consistently leaves untranslated
"""
from __future__ import annotations

import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
SOURCES = ROOT / "work" / "runtime_locale_sources"
TARGETS = ROOT / "work" / "translated" / "runtime_locales"
TIP_SRC = ROOT / "source" / "tooltips"
TIP_TGT = ROOT / "work" / "translated" / "tooltips"
OUT = ROOT / "work" / "t1_glossary.json"

VIET = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
    re.IGNORECASE,
)


def parse_lang(text: str) -> dict:
    out = {}
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        out[key.strip()] = value
    return out


def load_pairs() -> list[tuple[str, str]]:
    """(english, vietnamese) for every string the pack already translated."""
    pairs: list[tuple[str, str]] = []
    for src in sorted(SOURCES.glob("*.lang")):
        tgt = TARGETS / f"{src.stem}.json"
        if not tgt.is_file():
            continue
        english = parse_lang(src.read_text(encoding="utf-8"))
        try:
            viet = json.loads(tgt.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key, en in english.items():
            vi = viet.get(key)
            if isinstance(vi, str) and vi and vi != en:
                pairs.append((en, vi))
    for src in sorted(TIP_SRC.glob("*.lang")):
        tgt = TIP_TGT / f"{src.stem}.json"
        if not tgt.is_file():
            continue
        english = parse_lang(src.read_text(encoding="utf-8"))
        try:
            viet = json.loads(tgt.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key, en in english.items():
            vi = viet.get(key)
            if isinstance(vi, str) and vi and vi != en:
                pairs.append((en, vi))
    return pairs


def main() -> dict:
    pairs = load_pairs()
    if len(pairs) < 500:
        raise RuntimeError(f"only {len(pairs)} translated pairs found — wrong glob?")

    # Whole-string mappings that the pack uses consistently.
    exact: dict[str, Counter] = defaultdict(Counter)
    for en, vi in pairs:
        e = en.strip()
        if 0 < len(e) <= 40:
            exact[e][vi.strip()] += 1

    term_map = {}
    conflicts = {}
    for en, counts in exact.items():
        if sum(counts.values()) < 2:
            continue
        best, n = counts.most_common(1)[0]
        total = sum(counts.values())
        if not VIET.search(best):
            continue
        if n / total >= 0.8:
            term_map[en] = best
        else:
            conflicts[en] = dict(counts)

    # English words the pack deliberately keeps: appear inside Vietnamese output
    # verbatim, often. These are the proper nouns translators must not touch.
    kept = Counter()
    for en, vi in pairs:
        for word in re.findall(r"\b[A-Z][A-Za-z']{2,}\b", vi):
            kept[word] += 1
    kept_english = sorted(w for w, c in kept.items() if c >= 8)

    OUT.write_text(
        json.dumps(
            {
                "pairs_mined": len(pairs),
                "term_map": dict(sorted(term_map.items())),
                "kept_english": kept_english,
                "conflicts_excluded": len(conflicts),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "pairs_mined": len(pairs),
        "term_map_size": len(term_map),
        "kept_english_size": len(kept_english),
        "conflicts_excluded": len(conflicts),
        "out": str(OUT),
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
