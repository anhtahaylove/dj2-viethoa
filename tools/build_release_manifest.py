#!/usr/bin/env python3
"""Generate the sole current DJ2 localization release manifest."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
OUTPUT = BUILD / "RELEASE_MANIFEST_CURRENT.json"
ARTIFACTS = (
    "DJ2_Viet_Hoa_2.23.4.zip",
    "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip",
    "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip",
)


def _digest(data, algorithm):
    return hashlib.new(algorithm, data).hexdigest()


def build(output=OUTPUT):
    artifacts = {}
    for name in ARTIFACTS:
        path = BUILD / name
        data = path.read_bytes()
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"CRC failure: {name}")
            entries = len(archive.infolist())
        artifacts[name] = {
            "bytes": len(data),
            "entries": entries,
            "sha1": _digest(data, "sha1"),
            "sha256": _digest(data, "sha256"),
        }
    data = {
        "schema": 1,
        "release": "DJ2 Việt hóa 2.23.4",
        "artifacts": artifacts,
        "verification": {
            "command": 'python -m unittest discover -s tools -p "test_*.py" -q',
            "server_delivery_gate": "python tools/verify_server_delivery.py",
        },
    }
    output = Path(output)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return data


if __name__ == "__main__":
    build()
