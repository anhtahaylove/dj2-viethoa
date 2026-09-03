"""Check translated units against their source before anything is merged.

Uses the build's own FORMAT regex: a hand-rolled %-token pattern reports
phantom mismatches because a space is a legal Java format flag ("200% cooler").
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from validate_lang import FORMAT  # noqa: E402

# Defaults are the first T1 batch; --units/--vi retarget later batches so the
# same checks run everywhere instead of being copied and drifting.
UNITS = Path("C:/Users/Administrator/AppData/Local/Temp/dj2_t1_units")
VI = Path("C:/Users/Administrator/AppData/Local/Temp/dj2_t1_vi")

COLOR = re.compile(r"§.|&[0-9a-fk-or]")
URL = re.compile(r"https?://\S+")
# Real markup tags only. Distinguishing them from prose by shape fails both
# ways: <Empty> is a HUD label a player reads, while <BR>/<NL>/<PAGE> are
# formatting. The pack's whole corpus uses 11 uppercase tokens, of which only
# these five are markup, plus lowercase tags and placeholder names.
MARKUP = re.compile(
    r"</?(?:BR|NL|PAGE|DIV|IMG|LINE|[a-z][A-Za-z0-9_:-]*)\s*/?>"
)


def load_unit(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        idx, ns, key, en = line.split("\t", 3)
        rows.append({"idx": idx, "ns": ns, "key": key, "en": en})
    return rows


def load_vi(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        idx, vi = line.split("\t", 1)
        out[idx] = vi
    return out


def check(en: str, vi: str, key: str) -> list[str]:
    bad = []
    if not vi.strip():
        return ["empty"]
    # Numbered tokens (%1$s) may legally move — Java fills them by index, and
    # Vietnamese word order often demands it. Bare tokens are positional, so
    # their ordered type sequence must survive exactly.
    en_tok, vi_tok = FORMAT.findall(en), FORMAT.findall(vi)
    if sorted(en_tok) != sorted(vi_tok):
        bad.append(f"token multiset {en_tok} != {vi_tok}")
    elif not any("$" in t for t in en_tok) and en_tok != vi_tok:
        bad.append(f"bare token order {en_tok} != {vi_tok}")
    if COLOR.findall(en) != COLOR.findall(vi):
        bad.append("colour codes differ")
    if sorted(URL.findall(en)) != sorted(URL.findall(vi)):
        bad.append("urls differ")
    if sorted(MARKUP.findall(en)) != sorted(MARKUP.findall(vi)):
        bad.append(f"markup {MARKUP.findall(en)} != {MARKUP.findall(vi)}")
    if en.count("\\n") != vi.count("\\n"):
        bad.append("literal \\n count")
    if "\n" in vi or "\r" in vi or "\t" in vi:
        bad.append("real newline/tab inside value")
    if en[:1].isspace() != vi[:1].isspace():
        bad.append("leading space changed")
    if en[-1:].isspace() != vi[-1:].isspace():
        bad.append("trailing space changed")
    if any(ord(c) > 0xFFFF for c in vi):
        bad.append("char above U+FFFF unrenderable in 1.12 font")
    if vi != unicodedata.normalize("NFC", vi):
        bad.append("not NFC")
    # Numbers must keep their value; 0,5 vs 0.5 has bitten this pack before.
    # Strip format tokens first so %1$d does not read as the number 1.
    en_n = re.findall(r"\d+(?:[.,]\d+)?", FORMAT.sub(" ", en))
    vi_n = re.findall(r"\d+(?:[.,]\d+)?", FORMAT.sub(" ", vi))
    if sorted(en_n) != sorted(vi_n):
        bad.append(f"numbers {en_n} != {vi_n}")
    # Only the literal syntax line must stay English: the pack ships 99
    # translated commands.* strings (descriptions, results, errors) against 28
    # kept ones, and every kept one is a usage line starting with "/".
    if en.lstrip().startswith("/") and vi.strip() != en.strip():
        bad.append("command usage should stay English")
    # A dropped tail is invisible to the token checks when the lost clause has
    # no %s in it. Vietnamese runs slightly longer than English, so a target
    # well under the source length means text went missing.
    # Measured over 163 long rows: median 0.92, 5th percentile 0.78. Every real
    # truncation found so far sat at or below 0.63, while the shortest fully
    # faithful translations reach 0.72, so 0.68 separates them.
    if len(en) > 120 and len(vi) < 0.68 * len(en):
        bad.append(f"suspiciously short: en={len(en)} vi={len(vi)} — dropped tail?")
    return bad


def main() -> dict:
    units_dir, vi_dir = UNITS, VI
    argv = sys.argv[1:]
    for flag, target in (("--units", "units"), ("--vi", "vi")):
        if flag in argv:
            value = Path(argv[argv.index(flag) + 1])
            if target == "units":
                units_dir = value
            else:
                vi_dir = value

    report = {"units": [], "total_rows": 0, "total_problems": 0}
    for unit in sorted(units_dir.glob("unit_*.txt")):
        vi_path = vi_dir / f"{unit.stem}.vi.txt"
        if not vi_path.is_file():
            continue
        rows = load_unit(unit)
        vi = load_vi(vi_path)
        problems = []
        if len(vi) != len(rows):
            problems.append(f"row count {len(vi)} != {len(rows)}")
        for row in rows:
            got = vi.get(row["idx"])
            if got is None:
                problems.append(f"{row['idx']} missing")
                continue
            for issue in check(row["en"], got, row["key"]):
                problems.append(f"{row['idx']} {row['key']}: {issue}")
        report["units"].append(
            {"unit": unit.stem, "rows": len(rows), "problems": problems[:40], "count": len(problems)}
        )
        report["total_rows"] += len(rows)
        report["total_problems"] += len(problems)
    return report


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
