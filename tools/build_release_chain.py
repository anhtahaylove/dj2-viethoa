#!/usr/bin/env python3
"""Run the whole release chain in order, so no step can be forgotten.

Every builder here already worked in isolation; what kept breaking was the
ORDER and the COMPLETENESS of the sequence. The chain has a real dependency
chain -- the resource pack feeds the client bundle, the bundle and the server
overlay feed the manifest, and the acceptance record hashes all three -- so
running a subset leaves the later files describing artifacts that no longer
exist.

That is exactly what happened at the end of the last two waves. The pack was
rebuilt with a new translation, but `build_final_acceptance.py` was not re-run,
so `FINAL_ACCEPTANCE_CURRENT.json` still certified the previous wave's hashes
and the acceptance test failed. The record was correct for a release nobody was
serving any more. Chaining the steps removes the chance to skip one by hand.

    python tools/build_release_chain.py                # build + record
    python tools/build_release_chain.py --tests "176 passed"
    python tools/build_release_chain.py --dry-run      # just list the steps

Validation and verification stay outside this script on purpose: validators
must run BEFORE a build to be worth anything, and `verify_release.py` reads the
`release/` tree, which is populated by a separate publishing decision.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"

# In dependency order. The acceptance record is deliberately last: it hashes the
# artifacts the preceding steps produce, so it is only truthful once they exist.
STEPS = (
    # Coverage first: it regenerates work/coverage_report.json and
    # work/missing_by_tier.json from the stores, so the numbers quoted in the
    # README and the acceptance record describe the artifacts built below.
    ("measure_coverage.py", "coverage report"),
    ("build_pack.py", "resource pack"),
    ("build_client_overlays.py", "client overlays"),
    ("build_client_bundle.py", "client bundle"),
    ("build_server_overlay.py", "server overlay"),
    ("build_release_manifest.py", "release manifest"),
    ("build_final_acceptance.py", "acceptance record"),
)

# Only this step takes the test summary; passing it to the others would fail.
TESTS_ARG_STEP = "build_final_acceptance.py"


def run_step(script: str, label: str, tests: str | None = None) -> dict:
    command = [sys.executable, str(TOOLS / script)]
    if tests and script == TESTS_ARG_STEP:
        command += ["--tests", tests]

    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    return {
        "script": script,
        "label": label,
        "returncode": result.returncode,
        "seconds": round(elapsed, 1),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tests",
        help="test summary to record in the acceptance file, e.g. '176 passed'",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the ordered steps without running them",
    )
    args = parser.parse_args()

    if args.dry_run:
        for index, (script, label) in enumerate(STEPS, start=1):
            print(f"{index}. {script:32} {label}")
        return 0

    for index, (script, label) in enumerate(STEPS, start=1):
        print(f"[{index}/{len(STEPS)}] {label} ({script}) ... ", end="", flush=True)
        outcome = run_step(script, label, args.tests)
        if outcome["returncode"] != 0:
            # Stop at the first failure: continuing would build later artifacts
            # on top of a broken earlier one and hide which step actually broke.
            print(f"FAILED (exit {outcome['returncode']})")
            if outcome["stdout"]:
                print(outcome["stdout"].rstrip())
            if outcome["stderr"]:
                print(outcome["stderr"].rstrip(), file=sys.stderr)
            print(
                f"\nChain stopped at step {index} ({script})."
                " Later artifacts were NOT rebuilt,"
                "\nso the acceptance record still describes the previous build.",
                file=sys.stderr,
            )
            return outcome["returncode"]
        print(f"ok ({outcome['seconds']}s)")

    print("\nAll steps completed. Next:")
    print("  python -m pytest tools/ -q")
    print("  python tools/verify_release.py        # after syncing release/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
