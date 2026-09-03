#!/usr/bin/env python3
"""Install the allowlisted DJ2 server localization overlay atomically."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = PROJECT.parent / "Divine_Journey_2.23.4_Server_Pack"
DEFAULT_OVERLAY = PROJECT / "build" / "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip"
SHARED = PROJECT / "source" / "server_shared"
DIRECT_ENTRIES = (
    "config/tips.cfg",
    "scripts/JEI/Excavator.zs",
    "scripts/ContentTweaker/ContentTweakerItems.zs",
    "scripts/ModSpecific/ContentTweakerRecipes.zs",
    "resourcepack/DJ2_Viet_Hoa_2.23.4.zip",
)
# Legacy publishers also wrote these copies. Keep them byte-identical so a
# helper pointed at any of them can never serve a pack that fails the
# declared resource-pack-sha1 check.
PACK_ALIASES = (
    "DJ2_Viet_Hoa_2.23.4.zip",
    "resourcepacks/DJ2_Viet_Hoa_2.23.4.zip",
)


def _load_merge():
    path = PROJECT / "tools" / "merge_instance_ftbutilities.py"
    spec = importlib.util.spec_from_file_location("merge_server_ftbutilities", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".hermes-new")
    staged.write_bytes(data)
    os.replace(staged, path)


def install(server=DEFAULT_SERVER, overlay=DEFAULT_OVERLAY, backup_root=None):
    server = Path(server)
    overlay = Path(overlay)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path(backup_root) if backup_root else PROJECT / "work" / "server-overlay-backups" / stamp
    backup.mkdir(parents=True, exist_ok=True)
    props = server / "server.properties"
    ftb = server / "config" / "ftbutilities.cfg"
    with zipfile.ZipFile(overlay) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Server overlay CRC failure")
        for rel in DIRECT_ENTRIES:
            dst = server / rel
            if dst.exists():
                old = backup / rel
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, old)
            _atomic_write(dst, archive.read(rel))
    if props.exists():
        old = backup / "server.properties"
        old.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(props, old)
    pack = server / "resourcepack" / "DJ2_Viet_Hoa_2.23.4.zip"
    pack_bytes = pack.read_bytes()
    aliases = []
    for rel in PACK_ALIASES:
        dst = server / rel
        if not dst.exists():
            continue
        if dst.read_bytes() == pack_bytes:
            continue
        old = backup / rel
        old.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, old)
        _atomic_write(dst, pack_bytes)
        aliases.append(rel)
    sha1 = hashlib.sha1(pack_bytes).hexdigest()
    text = props.read_text(encoding="iso-8859-1")
    updated, count = re.subn(r"(?m)^resource-pack-sha1=.*$", f"resource-pack-sha1={sha1}", text)
    if count != 1:
        raise RuntimeError("Expected one resource-pack-sha1 property")
    _atomic_write(props, updated.encode("iso-8859-1"))
    if ftb.exists():
        old = backup / "config" / "ftbutilities.cfg"
        old.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ftb, old)
        merge = _load_merge()
        temp = ftb.with_name(ftb.name + ".merged")
        changed = merge.merge(ftb, SHARED / "config" / "ftbutilities.cfg", temp)
        if changed not in ({"motd"}, set()):
            temp.unlink(missing_ok=True)
            raise RuntimeError(f"Unexpected FTBUtilities fields: {changed}")
        os.replace(temp, ftb)
    report = {"backup": str(backup), "resource_pack_sha1": sha1, "direct_entries": list(DIRECT_ENTRIES), "pack_aliases_synced": aliases, "ftbutilities_merged": ftb.exists()}
    (backup / "install-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", type=Path, default=DEFAULT_SERVER)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY)
    args = parser.parse_args()
    result = install(args.server, args.overlay)
    safe = dict(result)
    safe.pop("backup", None)
    print(json.dumps(safe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
