#!/usr/bin/env python3
"""Verify DJ2 canonical pack, hosted bytes, and server property hash."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "dj2-viethoa"
SERVER = ROOT / "Divine_Journey_2.23.4_Server_Pack"
PACK = PROJECT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
HOSTED = SERVER / "resourcepack" / PACK.name
PROPERTIES = SERVER / "server.properties"


def _java_unescape(value):
    return value.replace("\\:", ":")


def verify(pack=PACK, hosted=HOSTED, properties=PROPERTIES, server=SERVER):
    pack = Path(pack)
    hosted = Path(hosted)
    properties = Path(properties)
    canonical = pack.read_bytes()
    hosted_bytes = hosted.read_bytes() if hosted.exists() else b""
    sha1 = hashlib.sha1(canonical).hexdigest()
    text = properties.read_text(encoding="iso-8859-1") if properties.exists() else ""
    declared = next((line.split("=", 1)[1].strip() for line in text.splitlines() if line.startswith("resource-pack-sha1=")), "")
    raw_url = next((line.split("=", 1)[1].strip() for line in text.splitlines() if line.startswith("resource-pack=")), "")
    parsed = urlparse(_java_unescape(raw_url))
    stale = []
    server = Path(server)
    if server.exists():
        for path in server.rglob(pack.name):
            rel = path.relative_to(server).as_posix()
            if "backup" in rel.lower():
                continue
            if path.read_bytes() != canonical:
                stale.append(rel)
    result = {
        "canonical_sha1": sha1,
        "hosted_sha1": hashlib.sha1(hosted_bytes).hexdigest() if hosted_bytes else None,
        "declared_sha1": declared,
        "bytes_equal": hosted_bytes == canonical,
        "url_valid": parsed.scheme in {"http", "https"} and bool(parsed.netloc),
        "stale_pack_copies": stale,
    }
    result["ok"] = result["bytes_equal"] and declared == sha1 and result["url_valid"] and not stale
    return result


def main():
    result = verify()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
