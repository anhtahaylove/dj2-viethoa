#!/usr/bin/env python3
"""Atomically publish the verified DJ2 resource pack and verify HTTP bytes."""
from __future__ import annotations
import datetime
import hashlib
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "dj2-viethoa"
BUILD = PROJECT / "build" / "DJ2_Viet_Hoa_2.23.4.zip"
SERVER = ROOT / "Divine_Journey_2.23.4_Server_Pack"
HOSTED_CANDIDATES = (
    SERVER / "resourcepack" / BUILD.name,
    SERVER / "resourcepacks" / BUILD.name,
    # The server root copy is served too, so it must be republished with the
    # others — leaving it behind hands players a pack whose bytes no longer
    # match the SHA-1 in server.properties, and the download is rejected.
    SERVER / BUILD.name,
)
PROPERTIES = SERVER / "server.properties"
REPORT = PROJECT / "work" / "audit" / "publish_report.json"


def digest(data: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, data).hexdigest()


def main() -> None:
    artifact = BUILD.read_bytes()
    sha1 = digest(artifact, "sha1")
    sha256 = digest(artifact, "sha256")
    props = PROPERTIES.read_text(encoding="utf-8")
    url_match = re.search(r"(?m)^resource-pack=(.+)$", props)
    if not url_match or not url_match.group(1).strip():
        raise SystemExit("server.properties has no resource-pack URL")
    # Java .properties escapes ':' as '\\:'; unescape for Python's HTTP client.
    url = url_match.group(1).strip().replace("\\:", ":")

    # The already-running host may have been started with either historical
    # directory spelling. Publish identical bytes to both safe local targets.
    hosted_targets = [path for path in HOSTED_CANDIDATES if path.parent.exists()]
    if not hosted_targets:
        hosted_targets = [HOSTED_CANDIDATES[0]]

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = PROJECT / "work" / "backups" / f"publish-{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for source in (*hosted_targets, PROPERTIES):
        if source.exists():
            shutil.copy2(source, backup / source.name)

    for hosted in hosted_targets:
        hosted.parent.mkdir(parents=True, exist_ok=True)
        staged = hosted.with_suffix(hosted.suffix + ".new")
        staged.write_bytes(artifact)
        if digest(staged.read_bytes(), "sha1") != sha1:
            raise SystemExit("Staged artifact hash mismatch")
        os.replace(staged, hosted)

    updated, count = re.subn(r"(?m)^resource-pack-sha1=.*$", f"resource-pack-sha1={sha1}", props)
    if count != 1:
        raise SystemExit("Expected exactly one resource-pack-sha1 property")
    PROPERTIES.write_text(updated, encoding="utf-8")

    # Publishing must still work while the host is down — otherwise the local
    # copies and server.properties drift out of sync with the built pack and the
    # next server start hands players a hash the file no longer matches. The HTTP
    # check is kept as a hard gate whenever the host answers at all.
    http_verified = False
    status = cache_control = content_length = None
    served_sha1 = ""
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            served = response.read()
            status = getattr(response, "status", None)
            cache_control = response.headers.get("Cache-Control", "")
            content_length = response.headers.get("Content-Length", "")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        reachable_error = str(exc)
    else:
        reachable_error = ""
        served_sha1 = digest(served, "sha1")
        if served != artifact:
            raise SystemExit(f"HTTP bytes mismatch: served sha1={served_sha1}, expected={sha1}")
        http_verified = True
    if f"resource-pack-sha1={sha1}" not in PROPERTIES.read_text(encoding="utf-8"):
        raise SystemExit("server.properties read-back mismatch")

    report = {
        "artifacts": [str(path) for path in hosted_targets],
        "bytes": len(artifact),
        "sha1": sha1,
        "sha256": sha256,
        "property_updated": True,
        "http_verified": http_verified,
        "http_error": reachable_error,
        "http_status": status,
        "http_bytes": len(served) if http_verified else 0,
        "http_sha1": served_sha1,
        "cache_control": cache_control,
        "content_length": content_length,
        "backup": str(backup),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    safe = dict(report)
    safe.pop("artifacts", None)
    safe.pop("backup", None)
    print(json.dumps(safe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
