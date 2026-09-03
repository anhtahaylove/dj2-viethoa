"""Install the client bundle into the ElyPrism instance, with backups.

Path-checked extraction: a zip entry that escapes the instance directory is
refused rather than written, and any file about to be overwritten is copied to
work/client-overlay-backups/<timestamp>/ first.
"""
import argparse
import datetime as dt
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "build" / "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip"
DEFAULT_INSTANCE = Path.home() / "AppData/Roaming/ElyPrismLauncher/instances/Divine Journey 2/minecraft"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--instance", type=Path, default=DEFAULT_INSTANCE)
    args = parser.parse_args()

    instance = args.instance.resolve()
    if not instance.is_dir():
        raise SystemExit(f"instance not found: {instance}")

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = ROOT / "work" / "client-overlay-backups" / stamp
    written, backed_up = [], []

    with zipfile.ZipFile(args.bundle) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            target = (instance / info.filename).resolve()
            # Refuse anything that resolves outside the instance directory.
            if not target.is_relative_to(instance):
                raise SystemExit(f"unsafe entry escapes instance: {info.filename}")
            if target.exists():
                backup = backup_root / info.filename
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backed_up.append(info.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            written.append(info.filename)

    print(json.dumps({
        "instance": str(instance),
        "bundle": str(args.bundle),
        "written": len(written),
        "backed_up": len(backed_up),
        "backup_dir": str(backup_root) if backed_up else None,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
