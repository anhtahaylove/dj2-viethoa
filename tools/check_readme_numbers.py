"""Check that the reader-facing numbers in DOC_DAU_TIEN.md match reality.

DOC_DAU_TIEN.md is the first thing anyone opens before installing, and it is the
one shipped file no builder writes. It went three waves untouched while every
headline figure drifted: it still advertised 20,119 translated lines and 74.3%
coverage after the stores had reached 22,618 and 83.5%, and it undercounted the
mods and Patchouli pages in the pack sitting beside it.

The five JSON evidence files drifted the same way and are now synced by the
release chain. This file cannot be synced -- it is prose, written by hand -- so
it is gated instead: every number below is re-derived from the stores and the
built artifacts, and a mismatch fails the build rather than shipping a document
that misdescribes the ZIPs next to it.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "release" / "DJ2_Viet_Hoa_2.23.4" / "DOC_DAU_TIEN.md"
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
COVERAGE = ROOT / "work" / "coverage_report.json"
TIERS = ROOT / "work" / "missing_by_tier.json"
QUESTS = ROOT / "source" / "betterquesting-quests.lang"
GUI = ROOT / "source" / "betterquesting-gui.lang"


def vi(number: int) -> str:
    """Vietnamese thousands separator: 22618 -> "22.618"."""
    return f"{number:,}".replace(",", ".")


def count_lang_lines(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    return sum(1 for line in lines if "=" in line and not line.lstrip().startswith("#"))


def expected() -> list[tuple[str, str, str]]:
    """(label, regex over the document, expected text) derived from real data."""
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    tiers = json.loads(TIERS.read_text(encoding="utf-8"))
    counts = {"T1": 0, "T2": 0, "T3": 0, "other": 0}
    for row in tiers:
        counts[row["tier"]] = counts.get(row["tier"], 0) + 1

    with zipfile.ZipFile(PACK) as archive:
        names = archive.namelist()
    namespaces = {
        name.split("/")[1]
        for name in names
        if name.startswith("assets/") and len(name.split("/")) > 2
    }
    patchouli = [n for n in names if "/patchouli_books/" in n and n.endswith(".json")]

    # The pack ships quests and GUI strings in one betterquesting lang file; the
    # document quotes the quest lines alone, so subtract the GUI store.
    quest_lines = count_lang_lines(QUESTS)

    return [
        ("translated lines",
         r"\*\*([\d.]+) dòng\*\* văn bản đã dịch",
         vi(coverage["translated"])),
        ("mod namespaces",
         r"trải trên \*\*(\d+) mod\*\*",
         str(len(namespaces))),
        ("Patchouli pages",
         r"\*\*(\d+) trang\*\* sách Patchouli",
         str(len(patchouli))),
        ("quest lines",
         r"\*\*([\d.]+) dòng\*\* nhiệm vụ BetterQuesting",
         vi(quest_lines)),
        ("jar keys total",
         r"\| Tổng chuỗi trong tất cả mod \| ([\d.]+) \|",
         vi(coverage["jar_keys_total"])),
        ("registry names",
         r"cố ý giữ tiếng Anh\*\* \| ([\d.]+) \|",
         vi(coverage["excluded_registry_names"])),
        ("dev-only strings",
         r"\| Tài liệu chỉ dành cho lập trình viên \| ([\d.]+) \|",
         vi(coverage["excluded_dev_only"])),
        ("empty strings",
         r"\| Chuỗi rỗng \| ([\d.]+) \|",
         vi(coverage["excluded_empty"])),
        ("in scope",
         r"\| \*\*Phần thực sự cần dịch\*\* \| \*\*([\d.]+)\*\* \|",
         vi(coverage["in_scope"])),
        ("translated (table)",
         r"\| Đã dịch \| ([\d.]+) \|",
         vi(coverage["translated"])),
        ("coverage percent",
         r"\| \*\*Tỷ lệ\*\* \| \*\*([\d,]+)%\*\* \|",
         str(coverage["coverage_pct"]).replace(".", ",")),
        ("tier T1",
         r"\| Tooltip, tin nhắn, thành tựu \| ([\d.]+) \|",
         vi(counts["T1"])),
        ("tier T2",
         r"\| Nhãn giao diện, JEI, phím tắt \| ([\d.]+) \|",
         vi(counts["T2"])),
        ("tier T3",
         r"\| Màn hình cấu hình, lệnh, công cụ quản trị \| ([\d.]+) \|",
         vi(counts["T3"])),
        ("tier other",
         r"\| Chuỗi lẻ chưa phân nhóm \| ([\d.]+) \|",
         vi(counts["other"])),
        ("dev-only prose",
         r"còn \*\*([\d.]+) dòng\*\* chỉ dành cho lập trình viên",
         vi(coverage["excluded_dev_only"])),
        ("identical to English",
         r"Thêm \*\*([\d.]+) dòng\*\* hiện để nguyên tiếng Anh",
         vi(coverage["identical_to_english"])),
    ]


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    failures = []
    for label, pattern, want in expected():
        match = re.search(pattern, text)
        if match is None:
            failures.append(f"{label}: no line matching {pattern!r}")
        elif match.group(1) != want:
            failures.append(f"{label}: document says {match.group(1)}, data says {want}")

    if failures:
        print("DOC_DAU_TIEN.md disagrees with the data it describes:")
        for failure in failures:
            print(f"  {failure}")
        print("\nThis file is prose and no builder rewrites it. Update it by hand,")
        print("then re-run this check.")
        return 1

    print(f"DOC_DAU_TIEN.md: all {len(expected())} figures match the stores and the pack.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
