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

The chain also syncs `release/` as its last step. That directory is what git
tracks as the shipped release, and it had no owning script: the manifest and
the verification reports sat three waves stale, describing a pack that had been
rebuilt twice, while every gate stayed green because the tests read `build/`.
Use `--no-sync` to build without touching it.

Validation stays outside this script on purpose -- validators must run BEFORE a
build to be worth anything. `verify_release.py` also stays outside: it is the
independent check that this script did its job, and a script that verified its
own output would prove nothing.
"""
from __future__ import annotations

import argparse
import hashlib
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

# Generated in build/, but shipped from release/ -- and nothing owned the copy.
# The manifest and the three verification reports each sat unrefreshed for
# three waves, still describing the wave-18 pack (1,931,901 bytes) while the
# artifacts next to them had been rebuilt twice. Every gate stayed green: the
# tests read the build/ copies, and SHA256SUMS.txt lists only the ZIPs.
SYNCED_EVIDENCE = (
    "FINAL_ACCEPTANCE_CURRENT.json",
    "RELEASE_MANIFEST_CURRENT.json",
    "client_bundle_verification.json",
    "publish_verification.json",
    "release_verification.json",
)

# Hashed into SHA256SUMS.txt, in the order the file lists them.
ARTIFACTS = (
    "DJ2_Viet_Hoa_2.23.4.zip",
    "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip",
    "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip",
)

RELEASE_DIR = ROOT / "release" / "DJ2_Viet_Hoa_2.23.4"

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


def sync_release_dir() -> dict:
    """Copy the artifacts and their evidence files into release/.

    Kept inside the chain because doing it by hand is what failed: publishing
    fans out to the hosted copies and leaves release/ alone, so the directory
    git tracks as the shipped release drifted away from the build silently.
    Byte-for-byte copies only -- this never regenerates content, so a file that
    the build did not produce cannot appear here.
    """
    report = {"copied": [], "unchanged": [], "absent": []}
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    for name in ARTIFACTS + SYNCED_EVIDENCE:
        source = ROOT / "build" / name
        if not source.is_file():
            report["absent"].append(name)
            continue
        target = RELEASE_DIR / name
        payload = source.read_bytes()
        if target.is_file() and target.read_bytes() == payload:
            report["unchanged"].append(name)
            continue
        target.write_bytes(payload)
        report["copied"].append(name)

    # Regenerate the checksums from the bytes now in release/, not from build/,
    # so the file certifies what it sits beside.
    lines = []
    for name in ARTIFACTS:
        target = RELEASE_DIR / name
        if target.is_file():
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            lines.append(f"{digest}  {name}")
    if lines:
        (RELEASE_DIR / "SHA256SUMS.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tests",
        help="test summary to record in the acceptance file, e.g. '176 passed'",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="build without refreshing release/ (leaves the shipped copy stale)",
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
        if not args.no_sync:
            print(f"{len(STEPS) + 1}. {'(sync release/)':32} copy artifacts + evidence, rehash SHA256SUMS.txt")
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

    if args.no_sync:
        print("\nSkipped release/ sync (--no-sync).")
    else:
        print(f"[{len(STEPS) + 1}/{len(STEPS) + 1}] sync release/ ... ", end="", flush=True)
        report = sync_release_dir()
        print(
            f"ok ({len(report['copied'])} copied, "
            f"{len(report['unchanged'])} already current)"
        )
        for name in report["copied"]:
            print(f"    updated  {name}")
        for name in report["absent"]:
            print(f"    MISSING in build/: {name}", file=sys.stderr)

    print("\nAll steps completed. Next:")
    print("  python -m pytest tools/ -q")
    print("  python tools/verify_release.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
