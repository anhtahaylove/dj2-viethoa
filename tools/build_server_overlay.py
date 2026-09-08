#!/usr/bin/env python3
"""Build a deterministic, allowlisted DJ2 server localization overlay."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "source" / "server_shared"
PACK = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
OUTPUT = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip"

SHARED_ENTRIES = (
    "config/tips.cfg",
    "scripts/JEI/Excavator.zs",
    "scripts/ContentTweaker/ContentTweakerItems.zs",
    "scripts/ModSpecific/ContentTweakerRecipes.zs",
    "scripts/Unique/HandFramingUses.zs",
    "scripts/Unique/FixCopperOreSmelting.zs",
)
ALLOWED_ENTRIES = (*SHARED_ENTRIES, "resourcepack/DJ2_Viet_Hoa_2.23.4.zip", "SERVER_OVERLAY_MANIFEST.json", "HUONG_DAN_SERVER.txt")

GUIDE = """DJ2 Việt hóa 2.23.4 — Server Localization Overlay

Đây là overlay deterministic, không chứa server.properties, FTBUtilities gameplay config,
world, playerdata, whitelist, ops, log hay backup.

Cài bằng tools/install_server_overlay.py để:
- sao lưu từng file đích;
- thay atomically resource pack và các script/text đã review;
- merge riêng block MOTD từ canonical ftbutilities.cfg;
- cập nhật riêng resource-pack-sha1;
- giữ nguyên URL, bind, world và gameplay settings.
""".encode("utf-8")


def _manifest(entries):
    return {
        "schema": 1,
        "type": "dj2-server-localization-overlay",
        "entries": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(entries.items())
        },
    }


def build(output=OUTPUT):
    output = Path(output)
    entries = {name: (SHARED / name).read_bytes() for name in SHARED_ENTRIES}
    entries["resourcepack/DJ2_Viet_Hoa_2.23.4.zip"] = PACK.read_bytes()
    entries["HUONG_DAN_SERVER.txt"] = GUIDE
    entries["SERVER_OVERLAY_MANIFEST.json"] = (
        json.dumps(_manifest(entries), ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    if set(entries) != set(ALLOWED_ENTRIES):
        raise RuntimeError("Server overlay allowlist mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entries[name])
    return entries


if __name__ == "__main__":
    build()
