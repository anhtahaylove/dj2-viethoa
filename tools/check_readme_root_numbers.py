"""Check that the headline numbers in README.md match reality.

check_readme_numbers.py gates DOC_DAU_TIEN.md despite its name; README.md itself
went ungated. It drifted for three waves -- still advertising 83.5% coverage and
192 passed tests after the stores reached 84.1% and the suite reached 212 -- and
no gate complained, because no gate was reading it.

README.md is the first thing a visitor sees on the public repository page, so
every headline figure in it is re-derived here from the stores and the built
artifacts. A mismatch fails the build rather than shipping a front page that
misdescribes the release.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "README.md"
COVERAGE = ROOT / "work" / "coverage_report.json"
TIERS = ROOT / "work" / "missing_by_tier.json"
# Read the build/ copy: the chain writes it at step 8 and only syncs it into
# release/ at step 11, AFTER this gate runs. Pointing at release/ here made
# the gate judge the previous run and deadlock the chain against itself.
ACCEPTANCE = ROOT / "build" / "FINAL_ACCEPTANCE_CURRENT.json"
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"


def vi(number: int) -> str:
    """Vietnamese thousands separator: 22783 -> "22.783"."""
    return f"{number:,}".replace(",", ".")


def load_json(path: Path):
    if not path.exists():
        raise SystemExit(f"missing evidence file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def pack_facts() -> tuple[int, int]:
    """Return (shipped lines, namespaces) from the built resource pack.

    A missing pack must fail rather than skip: an unverifiable claim is not a
    verified one.
    """
    if not PACK.exists():
        raise SystemExit(
            f"missing {PACK.relative_to(ROOT)} -- build the pack before gating README"
        )
    lines = 0
    namespaces = set()
    with zipfile.ZipFile(PACK) as zf:
        for name in zf.namelist():
            if not name.endswith(".lang"):
                continue
            parts = name.split("/")
            if len(parts) > 1 and parts[0] == "assets":
                namespaces.add(parts[1])
            for line in zf.read(name).decode("utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    lines += 1
    return lines, len(namespaces)


def expected() -> list[tuple[str, str, str]]:
    coverage = load_json(COVERAGE)
    tiers = load_json(TIERS)
    acceptance = load_json(ACCEPTANCE)
    shipped_lines, namespaces = pack_facts()

    counts: dict[str, int] = {}
    for entry in tiers:
        counts[entry["tier"]] = counts.get(entry["tier"], 0) + 1

    tests_field = acceptance.get("tests")
    if not tests_field:
        raise SystemExit("FINAL_ACCEPTANCE_CURRENT.json has no 'tests' field")
    match = re.search(r"(\d+) passed", tests_field)
    if match is None:
        raise SystemExit(f"cannot read pass count from tests field: {tests_field!r}")
    pytest_passed = int(match.group(1))

    # This gate compares the README against the acceptance file, so a stale
    # count in BOTH files keeps it green while both disagree with reality.
    # Anchor the number to the suite itself: collect the real test count.
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT, capture_output=True, text=True,
    )
    found = re.search(r"(\d+) tests? collected", collected.stdout or "")
    if found is None:
        raise SystemExit("cannot collect the test suite to verify the count")
    if int(found.group(1)) != pytest_passed:
        raise SystemExit(
            f"acceptance file says {pytest_passed} passed but the suite has "
            f"{found.group(1)} tests; rerun pytest and refresh the evidence"
        )

    return [
        ("coverage percent",
         r"\| Phạm vi dịch \| \*\*([\d,]+)%\*\*",
         str(coverage["coverage_pct"]).replace(".", ",")),
        ("translated",
         r"\| Phạm vi dịch \| \*\*[\d,]+%\*\* \(([\d.]+) / [\d.]+ khóa trong phạm vi\)",
         vi(coverage["translated"])),
        ("in scope",
         r"/ ([\d.]+) khóa trong phạm vi",
         vi(coverage["in_scope"])),
        ("shipped lines (table)",
         r"\| Dòng đã ship \| ([\d.]+) dòng",
         vi(shipped_lines)),
        ("namespaces (table)",
         r"\| Dòng đã ship \| [\d.]+ dòng, (\d+) mod \|",
         str(namespaces)),
        ("shipped lines (prose)",
         r"\*\*([\d.]+) dòng\*\* đã dịch, trải trên",
         vi(shipped_lines)),
        ("namespaces (prose)",
         r"đã dịch, trải trên \*\*(\d+) mod\*\*",
         str(namespaces)),
        ("tier T2",
         r"\| Còn lại \| [\d.]+ khóa giữ tiếng Anh có chủ đích: ([\d.]+) tên khối/máy",
         vi(counts.get("T2", 0))),
        ("tier T3",
         r"tên khối/máy, ([\d.]+) chuỗi lệnh",
         vi(counts.get("T3", 0))),
        ("tier other",
         r"chuỗi lệnh, ([\d.]+) tên vật phẩm",
         vi(counts.get("other", 0))),
        ("pytest passed",
         r"\| pytest \| \*\*([\d.]+) passed\*\*",
         vi(pytest_passed)),
        ("identical to English",
         r"Thêm \*\*([\d.]+) dòng\*\* cố ý để nguyên tiếng Anh",
         vi(coverage["identical_to_english"])),
    ]


def main() -> int:
    if not DOC.exists():
        print(f"FAIL: {DOC.relative_to(ROOT)} does not exist")
        return 1

    text = DOC.read_text(encoding="utf-8")
    failures = []
    for label, pattern, want in expected():
        match = re.search(pattern, text)
        if match is None:
            failures.append(f"{label}: no line matching {pattern!r}")
            continue
        got = next((g for g in match.groups() if g is not None), None)
        if got != want:
            failures.append(f"{label}: README says {got!r}, evidence says {want!r}")

    if failures:
        print(f"FAIL: {DOC.relative_to(ROOT)} disagrees with the evidence files")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"ok: all {len(expected())} README numbers match the evidence files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
