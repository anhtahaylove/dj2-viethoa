"""Compare the newly built pack against the currently installed one."""
import json
import os
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLED = (Path(os.environ["APPDATA"]) / "ElyPrismLauncher" / "instances"
             / "Divine Journey 2" / "minecraft" / "resourcepacks"
             / "DJ2_Viet_Hoa_2.23.4.zip")


def load(path: Path) -> dict[tuple[str, str], str]:
    entries: dict[tuple[str, str], str] = {}
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            # Locale casing follows each JAR: vi_vn.lang or vi_VN.lang.
            match = re.match(r"assets/([^/]+)/lang/vi_vn\.lang$", member, re.IGNORECASE)
            if not match:
                continue
            text = archive.read(member).decode("utf-8-sig")
            for line in text.replace("\r\n", "\n").split("\n"):
                if "=" in line and not line.lstrip().startswith("#"):
                    key, _, value = line.partition("=")
                    entries[(match.group(1), key)] = value
    return entries


def main() -> int:
    old = load(INSTALLED)
    new = load(ROOT / "build" / "DJ2_Viet_Hoa_2.23.4.zip")
    corpus = {
        (row["namespace"], row["key"])
        for row in json.loads(
            (ROOT / "work" / "approved_t1_corpus.json").read_text(encoding="utf-8")
        )["rows"]
    }
    added = set(new) - set(old)
    missing = corpus - set(new)
    print(f"installed keys : {len(old)}")
    print(f"rebuilt keys   : {len(new)}")
    print(f"newly added    : {len(added)}")
    print(f"corpus rows    : {len(corpus)}")
    print(f"corpus shipped : {len(corpus & set(new))}")
    print(f"corpus missing : {len(missing)}")
    for item in sorted(missing)[:15]:
        print("   missing", item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
