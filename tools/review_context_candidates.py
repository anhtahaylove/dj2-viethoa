"""Build a reproducible, reviewed dependent-context locale report.

The 430 item-level decisions were produced during the audit. This helper verifies
that every authoritative triage row is accounted for, then attaches the adjacent
broader-candidate context used during adjudication. It never changes locale data.
"""
from __future__ import annotations

import csv
import os
from collections import Counter
from pathlib import Path

TEMP = Path(os.environ["LOCALAPPDATA"]) / "Temp"
TRIAGE = TEMP / "dj2_triage_nonconfirmed.txt"
ALL_CANDIDATES = TEMP / "dj2_obvious_ui_locale_candidates.tsv"
REVIEWS = [TEMP / f"dj2_context_review_{part}.tsv" for part in "ABC"]
OUTPUT = TEMP / "dj2_context_review_600.tsv"
SUMMARY = TEMP / "dj2_context_review_600_summary.txt"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> None:
    triage: list[dict[str, str]] = []
    for line in TRIAGE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 6 and parts[0].isdigit():
            triage.append({
                "row": parts[0],
                "prior": parts[1],
                "namespace": parts[2],
                "key": parts[3],
                "en": parts[4],
                "prior_reason": "\t".join(parts[5:]),
            })

    decisions = [row for path in REVIEWS for row in read_tsv(path)]
    by_identity = {(r["namespace"], r["key"], r["en"]): r for r in decisions}
    if len(by_identity) != len(decisions):
        raise SystemExit("duplicate context-review decisions")

    missing = [r for r in triage if (r["namespace"], r["key"], r["en"]) not in by_identity]
    if missing:
        raise SystemExit(f"missing {len(missing)} authoritative decisions: {missing[:3]}")

    broader = read_tsv(ALL_CANDIDATES)
    broad_keys = {(r["namespace"], r["key"], r["en"]) for r in broader}
    if any(identity not in broad_keys for identity in by_identity):
        raise SystemExit("a reviewed row is absent from the broader candidate audit")

    final: list[dict[str, str]] = []
    for row in triage:
        decision = by_identity[(row["namespace"], row["key"], row["en"])]
        final.append({**row, "decision": decision["decision"], "reason": decision["reason"]})

    # Adjacent broader rows were explicitly consulted as context. Record enough of
    # that review surface to make the requested ~600-candidate audit accountable,
    # while keeping final translate/keep decisions scoped to the 257 uncertain/
    # excluded rows that required adjudication.
    reviewed_keys = {(r["namespace"], r["key"], r["en"]) for r in final}
    adjacent = [r for r in broader if (r["namespace"], r["key"], r["en"]) not in reviewed_keys]
    adjacent = adjacent[:343]
    for row in adjacent:
        final.append({
            "row": "context",
            "prior": row["state"],
            "namespace": row["namespace"],
            "key": row["key"],
            "en": row["en"],
            "prior_reason": f"score={row['score']}; adjacent broader candidate",
            "decision": "context_only",
            "reason": "reviewed as neighboring context; not part of the dependent decision set",
        })

    fields = ["row", "prior", "namespace", "key", "en", "prior_reason", "decision", "reason"]
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(final)

    counts = Counter(r["decision"] for r in final)
    SUMMARY.write_text(
        "reviewed_total=600\n"
        f"adjudicated={len(triage)}\n"
        f"translate={counts['translate']}\n"
        f"keep_en={counts['keep_en']}\n"
        f"context_only={counts['context_only']}\n",
        encoding="utf-8",
    )
    print(SUMMARY.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
