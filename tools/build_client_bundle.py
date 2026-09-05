from pathlib import Path
import hashlib
import importlib.util
import json
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "dj2-viethoa" / "build"
PACK = BUILD / "DJ2_Viet_Hoa_2.23.4.zip"
SHARED_ROOT = ROOT / "dj2-viethoa" / "source" / "server_shared"
TIPS = SHARED_ROOT / "config" / "tips.cfg"
FTBUTILITIES = SHARED_ROOT / "config" / "ftbutilities.cfg"
CLIENT_OVERLAY = ROOT / "dj2-viethoa" / "work" / "client_overlay_vi"
SERVER_SCRIPT_OVERLAYS = (
    "scripts/JEI/Excavator.zs",
    "scripts/ContentTweaker/ContentTweakerItems.zs",
    # The server already runs the Vietnamese copy of this one. It was left out
    # of the client bundle, so singleplayer and the integrated server still
    # printed the biome counter in English while multiplayer printed Vietnamese.
    "scripts/ModSpecific/ContentTweakerRecipes.zs",
    "scripts/Unique/HandFramingUses.zs",
)
OUTPUT = BUILD / "DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip"

OVERLAY_BUILDER = ROOT / "dj2-viethoa" / "tools" / "build_client_overlays.py"

README = """DJ2 Việt hóa 2.23.4 — gói cài trực tiếp

Giải nén TOÀN BỘ nội dung ZIP này ngay tại thư mục gốc của DJ2 client instance.
Cấu trúc sẽ tự vào:
- resourcepacks/DJ2_Viet_Hoa_2.23.4.zip
- config/tips.cfg
- config/ftbutilities.cfg
- config/CustomMainMenu/mainmenu.json và resources/mainmenu/*.png
- config/defaultoptions/options.txt
- config/crash_assistant/config.toml
- config/triumph/script/triumph/dj2/*.txt
- config/triumph/functions/triumph/*.txt
- scripts/JEI/Excavator.zs
- scripts/ContentTweaker/ContentTweakerItems.zs
- scripts/ModSpecific/ContentTweakerRecipes.zs
- scripts/Unique/HandFramingUses.zs

Sau khi giải nén, giao diện chính, ngôn ngữ mặc định, resource pack mặc định,
MOTD/TPA và các lớp script Việt hóa sẽ được đồng bộ. Gói không thay đổi quest progression,
recipe, criteria, reward hay mod JAR.

Các file cấu hình client này được tạo từ upstream DJ2, chỉ thay đổi trường hiển thị/ngôn ngữ đã review.
Sau đó mở game và kiểm tra ngôn ngữ Tiếng Việt (Việt Nam) cùng resource pack DJ2 Việt hóa 2.23.4 đã được bật.
Lưu ý: ftbutilities.cfg chỉ phục vụ thông báo đăng nhập/TPA trong integrated server; criteria, reward, recipe và progression được giữ nguyên.
""".encode("utf-8")


def build(output=OUTPUT):
    spec = importlib.util.spec_from_file_location("build_client_overlays", OVERLAY_BUILDER)
    overlay_builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay_builder)
    overlay_builder.build()

    entries = {
        "resourcepacks/DJ2_Viet_Hoa_2.23.4.zip": PACK.read_bytes(),
        "config/tips.cfg": TIPS.read_bytes(),
        "config/ftbutilities.cfg": FTBUTILITIES.read_bytes(),
        "HUONG_DAN_CAI_DAT.txt": README,
    }
    for path in sorted(CLIENT_OVERLAY.rglob("*")):
        if path.is_file():
            entries[path.relative_to(CLIENT_OVERLAY).as_posix()] = path.read_bytes()
    for relative in SERVER_SCRIPT_OVERLAYS:
        entries[relative] = (SHARED_ROOT / relative).read_bytes()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, entries[name])
    return entries


def verify(output=OUTPUT):
    expected = build(output)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(expected)
        for name, data in expected.items():
            assert archive.read(name) == data
    raw = output.read_bytes()
    return {
        "file": str(output),
        "bytes": len(raw),
        "sha1": hashlib.sha1(raw).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "entries": sorted(expected),
    }


if __name__ == "__main__":
    report = verify()
    (BUILD / "client_bundle_verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
