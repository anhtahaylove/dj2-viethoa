"""Translate conservative player-facing tooltip/prose locale sources."""
from __future__ import annotations

import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "tooltips"
OUT = ROOT / "work" / "translated" / "tooltips"
TRANSLATOR = ROOT / "work" / "translate_lang_json.py"


def source_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8-sig").splitlines() if line and not line.startswith("#") and "=" in line)


def output_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(json.loads(path.read_text(encoding="utf-8")))


def translate(path: Path):
    output = OUT / (path.stem + ".json")
    cp = subprocess.run(
        [sys.executable, str(TRANSLATOR), str(path), str(output), "--chunk", "12"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10800,
    )
    return path.stem, cp.returncode, output_count(output), source_count(path), cp.stdout[-500:], cp.stderr[-500:]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = sorted(path for path in SOURCE.glob("*.lang"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(translate, path) for path in sources]
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), flush=True)


if __name__ == "__main__":
    main()
