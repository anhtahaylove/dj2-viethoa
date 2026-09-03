#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
PACK = BUILD / "DJ2_Viet_Hoa_2.23.4.zip"
BUNDLE = BUILD / "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip"
SERVER_OVERLAY = BUILD / "DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip"
RELEASE_DIR = ROOT / "release" / "DJ2_Viet_Hoa_2.23.4"
REPORT = BUILD / "release_verification.json"


def digest(path, name):
    h = hashlib.new(name)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_pack(path):
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        lowered = [name.casefold() for name in names]
        bad = zf.testzip()
        for name in names:
            if name.endswith(".json"):
                json.loads(zf.read(name).decode("utf-8"))
        expected = {
            "assets/bigreactors/patchouli_books/erguide/book.json",
            "assets/chisel_guide/guide/index.json",
            "assets/enderio/book/vi_vn/modifiers/pickup.json",
            "assets/toolprogression/book/vi_vn/modifiers/magic_mushroom.json",
            "assets/galacticraftcore/manuals/gettingstarted.xml",
        }
        return {
            "entries": len(names),
            "crc_bad": bad,
            "duplicate_paths": len(names) - len(set(names)),
            "casefold_collisions": len(lowered) - len(set(lowered)),
            "json_files": sum(name.endswith(".json") for name in names),
            "vi_lang_files": sum(name.endswith("vi_vn.lang") for name in names),
            "patchouli_vi_json": sum("/patchouli_books/" in name and "/vi_vn/" in name and name.endswith(".json") for name in names),
            "tconstruct_vi_files": sum("/tconstruct/book/vi_vn/" in name for name in names),
            "missing_expected": sorted(expected - set(names)),
        }


def inspect_bundle(path):
    required = {
        "resourcepacks/DJ2_Viet_Hoa_2.23.4.zip",
        "config/tips.cfg",
        "scripts/JEI/Excavator.zs",
        "scripts/ContentTweaker/ContentTweakerItems.zs",
    }
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        bad = zf.testzip()
    return {
        "zip": str(path),
        "bytes": path.stat().st_size,
        "sha1": digest(path, "sha1"),
        "sha256": digest(path, "sha256"),
        "crc_ok": bad is None,
        "missing_required": sorted(required - names),
        "triumph_count": sum(name.startswith("config/triumph/script/triumph/dj2/") for name in names),
    }


def inspect_release_dir():
    """Compare the published share folder against build/.

    verify_release once passed while release/ still held a stale ZIP: it only
    ever looked at build/. Nothing copies build/ -> release/, so the published
    folder is checked here by content hash, not by trusting the build step.
    """
    out = {"dir": str(RELEASE_DIR), "exists": RELEASE_DIR.is_dir(),
           "stale": [], "missing": [], "checksum_mismatch": []}
    if not out["exists"]:
        return out
    for src in (PACK, BUNDLE, SERVER_OVERLAY):
        published = RELEASE_DIR / src.name
        if not src.exists():
            continue
        if not published.exists():
            out["missing"].append(src.name)
            continue
        if digest(published, "sha256") != digest(src, "sha256"):
            out["stale"].append({
                "name": src.name,
                "build_bytes": src.stat().st_size,
                "release_bytes": published.stat().st_size,
            })
    # The client bundle and server overlay each embed a COPY of the resource
    # pack. Hashing only the outer ZIPs missed a real ship bug: both bundles
    # carried a pre-wave-18 pack while the standalone ZIP was current, so the
    # translations were absent in game for anyone installing from a bundle.
    out["nested_pack_mismatch"] = []
    if PACK.exists() and RELEASE_DIR.joinpath(PACK.name).exists():
        canonical = hashlib.sha256(
            (RELEASE_DIR / PACK.name).read_bytes()
        ).hexdigest()
        for container in (BUNDLE, SERVER_OVERLAY):
            published = RELEASE_DIR / container.name
            if not published.exists():
                continue
            with zipfile.ZipFile(published) as zf:
                inner = [n for n in zf.namelist() if n.endswith(PACK.name)]
                if not inner:
                    out["nested_pack_mismatch"].append(
                        f"{container.name}: no embedded {PACK.name}")
                    continue
                for name in inner:
                    got = hashlib.sha256(zf.read(name)).hexdigest()
                    if got != canonical:
                        out["nested_pack_mismatch"].append(
                            f"{container.name}!{name}: differs from standalone pack")
    sums = RELEASE_DIR / "SHA256SUMS.txt"
    out["checksums_present"] = sums.exists()
    if sums.exists():
        for line in sums.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            expect, _, name = line.partition(" ")
            target = RELEASE_DIR / name.lstrip("*").strip()
            if not target.exists():
                out["checksum_mismatch"].append(f"{name}: missing")
            elif digest(target, "sha256") != expect:
                out["checksum_mismatch"].append(f"{name}: hash differs")
    return out


def main():
    if not PACK.exists() or not BUNDLE.exists():
        raise SystemExit("Missing release artifact")
    first = digest(PACK, "sha256")
    with tempfile.TemporaryDirectory() as td:
        second = Path(td) / PACK.name
        spec = importlib.util.spec_from_file_location("dj2_build_pack", ROOT / "tools" / "build_pack.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if module.build(output=second, stage=Path(td) / "stage") != 0:
            raise SystemExit("Deterministic rebuild failed validation")
        second_hash = digest(second, "sha256")
    report = {
        "zip": str(PACK),
        "bytes": PACK.stat().st_size,
        "sha1": digest(PACK, "sha1"),
        "sha256": first,
        **inspect_pack(PACK),
        "deterministic": first == second_hash,
        "second_sha256": second_hash,
        "client_bundle": inspect_bundle(BUNDLE),
        "published_release": inspect_release_dir(),
    }
    bundle = report["client_bundle"]
    bad = report["crc_bad"] or report["duplicate_paths"] or report["casefold_collisions"] or report["missing_expected"] or not report["deterministic"]
    bad = bad or not bundle["crc_ok"] or bundle["missing_required"] or bundle["triumph_count"] != 27
    pub = report["published_release"]
    if pub["exists"]:
        bad = bad or pub["stale"] or pub["missing"] or pub["checksum_mismatch"]
        bad = bad or pub.get("nested_pack_mismatch")
        bad = bad or not pub["checksums_present"]
    if bad:
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
