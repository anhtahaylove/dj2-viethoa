"""Run translation jobs until exact source/target coverage is complete."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATOR = ROOT / "work" / "translate_lang_json.py"


def parse_lang(path: Path):
    result = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if raw and not raw.startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            result[key] = value
    return result


def translated(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run(source: Path, output: Path, max_attempts: int):
    expected = set(parse_lang(source))
    for attempt in range(1, max_attempts + 1):
        actual = translated(output)
        if set(actual) == expected:
            return source.stem, 0, len(actual), len(expected), attempt - 1
        cp = subprocess.run(
            [sys.executable, str(TRANSLATOR), str(source), str(output), "--chunk", "12"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10800,
        )
        actual = translated(output)
        print(source.stem, f"attempt={attempt}", f"coverage={len(actual)}/{len(expected)}", f"exit={cp.returncode}", flush=True)
    return source.stem, 1, len(translated(output)), len(expected), max_attempts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--attempts", type=int, default=30)
    args = parser.parse_args()
    source_dir, output_dir = Path(args.source_dir), Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(source_dir.glob("*.lang"))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(run, source, output_dir / f"{source.stem}.json", args.attempts) for source in sources]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    print(json.dumps(sorted(results), ensure_ascii=False, indent=2))
    return 1 if any(result[1] for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
