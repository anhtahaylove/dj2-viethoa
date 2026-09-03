"""Fail when a tracked text file's line endings drift from its committed bytes.

`.gitattributes` sets `* -text`, so git stores and checks out these files
byte-for-byte and will never normalise an end-of-line for us. That is deliberate
-- the `.lang`/`.json` bytes are the deliverable and every release is verified by
SHA256 -- but it also means nothing in git warns us when a tool rewrites a file
in the wrong newline style.

That failure mode has already bitten this project twice. Both times a helper
opened a file with text-mode Python (`Path.write_text()`, or `json.dump()` to a
handle without `newline=""`) and Windows silently expanded every `\n` into
`\r\n`. Because `-text` disables normalisation, git faithfully recorded the
churn: a one-line edit to `roots.lang` came back as a whole-file diff, and the
`build_pack.py` refactor produced a 753-line diff for what should have been a
pure extraction. Nothing was semantically wrong either time, so the tests still
passed; only the diff size gave it away, and a smaller edit could easily have
slipped through unnoticed.

So this gate compares the working tree against `HEAD` and reports files whose
newline STYLE changed, ignoring content edits entirely. Adding a CRLF line to a
CRLF file is fine; converting that file to LF is not. New files are checked for
internal consistency only -- they have no committed bytes to diverge from, and
this repo legitimately mixes styles (tools are LF, several mod `.lang` files
arrived from upstream as CRLF, and `journeymap.json` is CRLF while its sibling
stores are LF), so a repo-wide "one true newline" rule would be wrong.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files whose bytes we care about: the deliverable data and the tools that write
# it. Binary artifacts are excluded -- they have no line endings to speak of and
# `git show` would only waste memory on them.
CHECKED_SUFFIXES = (".lang", ".json", ".py", ".cfg", ".md", ".txt", ".gitattributes")

# Generated trees are rebuilt wholesale rather than edited, so their newline
# style is whatever the writer produced and comparing against HEAD is noise.
SKIP_PREFIXES = ("build/", "release/", "work/backups/")


def _git(*args):
    result = subprocess.run(
        ("git",) + args, cwd=ROOT, capture_output=True, check=False
    )
    return result


def classify(data: bytes) -> str:
    """Name the newline style of `data`: 'crlf', 'lf', 'mixed', or 'none'."""
    crlf = data.count(b"\r\n")
    # A lone \r would be classic Mac line endings; count it so a stray one shows
    # up as mixed instead of being silently folded into the LF tally.
    bare_lf = data.count(b"\n") - crlf
    bare_cr = data.count(b"\r") - crlf
    if crlf and (bare_lf or bare_cr):
        return "mixed"
    if crlf:
        return "crlf"
    if bare_lf or bare_cr:
        return "lf"
    return "none"


def is_checked(rel_path: str) -> bool:
    if any(rel_path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    return rel_path.endswith(CHECKED_SUFFIXES)


def tracked_text_files():
    result = _git("ls-files", "-z")
    if result.returncode != 0:
        return []
    names = result.stdout.decode("utf-8").split("\0")
    return [name for name in names if name and is_checked(name)]


def committed_styles(rel_paths):
    """Map each path to its newline style in HEAD (absent paths are omitted).

    One `git cat-file --batch` beats one `git show` per file by two orders of
    magnitude here: the repository tracks thousands of `.lang`/`.json` files, and
    paying process-spawn latency per file made this gate slower than the entire
    rest of the suite.
    """
    rel_paths = list(rel_paths)
    if not rel_paths:
        return {}
    query = "".join(f"HEAD:{path}\n" for path in rel_paths).encode("utf-8")
    result = subprocess.run(
        ("git", "cat-file", "--batch"),
        cwd=ROOT,
        input=query,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {}

    styles = {}
    stream = result.stdout
    offset = 0
    for path in rel_paths:
        newline = stream.find(b"\n", offset)
        if newline == -1:
            break
        header = stream[offset:newline]
        if header.endswith(b" missing"):
            # Not committed yet; leave it out so callers treat it as new.
            offset = newline + 1
            continue
        # Header format: "<sha> <type> <size>"; the blob follows, then a newline.
        size = int(header.rsplit(b" ", 1)[1])
        start = newline + 1
        styles[path] = classify(stream[start : start + size])
        offset = start + size + 1
    return styles


def findings():
    """Files whose newline style drifted from HEAD, or is internally mixed."""
    problems = []
    tracked = tracked_text_files()
    original_styles = committed_styles(tracked)
    for rel_path in tracked:
        working_path = ROOT / rel_path
        if not working_path.exists():
            continue  # staged deletion; nothing to compare
        current_style = classify(working_path.read_bytes())
        original_style = original_styles.get(rel_path)

        if original_style is None:
            # Brand-new file: no baseline, so only flag self-inconsistency.
            if current_style == "mixed":
                problems.append(
                    {
                        "path": rel_path,
                        "problem": "mixed line endings in a new file",
                        "expected": "one consistent style",
                        "actual": current_style,
                    }
                )
            continue

        if current_style == original_style:
            continue
        if original_style == "none" or current_style == "none":
            # A file that gained or lost its only line is not an EOL rewrite.
            continue
        problems.append(
            {
                "path": rel_path,
                "problem": "line endings changed against HEAD",
                "expected": original_style,
                "actual": current_style,
            }
        )
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="print the findings as JSON"
    )
    args = parser.parse_args()

    problems = findings()
    if args.json:
        print(json.dumps({"errors": problems}, ensure_ascii=False, indent=2))
    elif problems:
        print(f"{len(problems)} file(s) changed newline style:")
        for problem in problems:
            print(
                f"  {problem['path']}: {problem['problem']}"
                f" (HEAD={problem['expected']}, working tree={problem['actual']})"
            )
        print(
            "\n.gitattributes sets `* -text`, so git will not fix this for you."
            "\nRe-write the file with the original newline style: read/write bytes,"
            "\nor pass newline='' when opening it in text mode."
        )
    else:
        print("No line-ending drift against HEAD.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
