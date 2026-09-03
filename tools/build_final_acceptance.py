#!/usr/bin/env python3
"""Generate the final acceptance record from the artifacts actually on disk.

README points at build/FINAL_ACCEPTANCE_CURRENT.json as the proof of what was
shipped. It used to be written by hand, so it drifted away from the real ZIPs
and kept describing decisions that had since been reversed — certifying a
release nobody was serving. Deriving it from the bytes removes that whole class
of failure: the record cannot claim a hash the artifact does not have.

Run after the artifacts are built and the suite is green:

    python tools/build_final_acceptance.py --tests "70 passed"
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
OUTPUT = BUILD / "FINAL_ACCEPTANCE_CURRENT.json"
OPTIONS = ROOT / "work" / "client_overlay_vi" / "config" / "defaultoptions" / "options.txt"

ARTIFACTS = {
    "resource_pack": "DJ2_Viet_Hoa_2.23.4.zip",
    "client_bundle": "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip",
    "server_overlay": "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip",
}


def _describe(path: Path) -> dict:
    data = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"CRC failure in {path.name}")
        entries = len(archive.infolist())
    return {
        "bytes": len(data),
        "entries": entries,
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _font_mode() -> str:
    """Read the shipped client options rather than restating an intention."""
    text = OPTIONS.read_text(encoding="utf-8")
    forced = "forceUnicodeFont:true" in text
    return (
        "enabled so every glyph comes from the pack's 16x16 unicode pages "
        "instead of mixing vanilla ascii.png with them"
        if forced
        else "disabled"
    )


def build(output=OUTPUT, tests: str | None = None) -> dict:
    record = {
        "generated": datetime.datetime.now().replace(microsecond=0).isoformat(),
        "tests": tests or "run `python -m unittest discover -s tools -p \"test_*.py\"`",
        "verify_release": "python tools/verify_release.py",
        "verify_server_delivery": "python tools/verify_server_delivery.py",
        "fixes": {
            "motd_colour_codes": "& -> section sign (FTBUtilities renders section sign only)",
            "mainmenu_mojibake": "3 strings made ASCII (CustomMainMenu reads platform charset, not UTF-8)",
            "bitmap_font": (
                "JetBrains Mono Bold rasterised at full 16x16 cell resolution to legacy "
                "unicode pages 00/01/1e/20 + glyph_sizes.bin"
            ),
            "glyph_width_table": (
                "low nibble stores the last inked column inclusively, matching vanilla, "
                "so Vietnamese advances are not one column wider than the ASCII beside them"
            ),
            "tone_mark_weight": "thin tone-mark rows padded to stay legible against the bold body",
            "dot_below": "redrawn two texels wide and detached from the letter body",
            "force_unicode_font": _font_mode(),
        },
        "artifacts": {
            name: _describe(BUILD / filename) for name, filename in ARTIFACTS.items()
        },
    }
    output = Path(output)
    output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", help="result of the regression suite, e.g. '70 passed'")
    args = parser.parse_args()
    print(json.dumps(build(tests=args.tests), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
