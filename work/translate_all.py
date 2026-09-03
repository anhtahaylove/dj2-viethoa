import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATOR = Path(__file__).resolve().with_name("translate_batch.py")
BATCHES = ROOT / "work" / "batches"
OUT = ROOT / "work" / "translated"
FORMAT = re.compile(r"%(?:n|%|(?:\d+\$)?[-#+ 0,(<]*\d*(?:\.\d+)?[bBhHsScCdoxXeEfgGaAtT])")
COLOR = re.compile(r"§.")
URL = re.compile(r"https?://.*?(?=%n|\s|§|$)")

def tokens(value):
    return FORMAT.findall(value), COLOR.findall(value), URL.findall(value)


def valid(source, output):
    if not output.exists():
        return False
    try:
        entries = json.loads(source.read_text(encoding="utf-8"))["entries"]
        src = {x["key"]: x["en"] for x in entries}
        tgt = json.loads(output.read_text(encoding="utf-8"))
    except Exception:
        return False
    if set(src) != set(tgt):
        return False
    return all(tokens(src[k]) == tokens(tgt[k]) for k in src)


def run_one(source):
    output = OUT / source.name
    if valid(source, output):
        return source.name, "already-valid"
    for attempt in range(1, 4):
        if output.exists():
            output.unlink()
        cp = subprocess.run(
            [sys.executable, str(TRANSLATOR), str(source), str(output), "--chunk", "12"],
            capture_output=True, text=True, encoding="utf-8", timeout=1800,
        )
        if cp.returncode == 0 and valid(source, output):
            return source.name, f"translated-attempt-{attempt}"
    raise RuntimeError(f"{source.name} failed: {cp.stdout[-1000:]} {cp.stderr[-1000:]}")


def main():
    sources = sorted(BATCHES.glob("ql_*.json")) + [BATCHES / "orphans.json"]
    OUT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {pool.submit(run_one, s): s for s in sources}
        for future in concurrent.futures.as_completed(future_map):
            try:
                print(future.result(), flush=True)
            except Exception as e:
                print("ERROR", future_map[future].name, repr(e), flush=True)
                raise

if __name__ == "__main__":
    main()
