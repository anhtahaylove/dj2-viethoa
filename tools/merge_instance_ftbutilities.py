"""Merge only reviewed player-visible FTBUtilities text into a live instance config."""
from __future__ import annotations

import re
from pathlib import Path

BLOCK_FIELDS = ("motd",)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _block_pattern(field: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?ms)^(?P<indent>[ \t]*)S:{re.escape(field)}[ \t]*<\r?\n.*?^(?P=indent)[ \t]+>[ \t]*$"
    )


def _get_block(text: str, field: str) -> str:
    matches = list(_block_pattern(field).finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one S:{field} block, found {len(matches)}")
    return matches[0].group(0)


def without_reviewed_text(path: Path) -> str:
    text = _read(path)
    for field in BLOCK_FIELDS:
        text = _block_pattern(field).sub(f"__REVIEWED_TEXT_FIELD_{field.upper()}__", text)
    return text.replace("\r\n", "\n")


def merge(live_path: Path, canonical_path: Path, output_path: Path) -> set[str]:
    live = _read(live_path)
    canonical = _read(canonical_path)
    changed: set[str] = set()
    merged = live
    for field in BLOCK_FIELDS:
        canonical_block = _get_block(canonical, field)
        live_block = _get_block(merged, field)
        if live_block != canonical_block:
            merged, count = _block_pattern(field).subn(lambda _m: canonical_block, merged, count=1)
            if count != 1:
                raise ValueError(f"failed to replace exactly one S:{field} block")
            changed.add(field)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged, encoding="utf-8")
    if without_reviewed_text(output_path) != without_reviewed_text(live_path):
        output_path.unlink(missing_ok=True)
        raise RuntimeError("merge altered content outside reviewed text fields")
    return changed


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("live", type=Path)
    parser.add_argument("canonical", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(",".join(sorted(merge(args.live, args.canonical, args.output))))
