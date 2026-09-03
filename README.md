# Divine Journey 2 v2.23.4 — Việt hóa

Bộ Việt hóa dành cho **Divine Journey 2 v2.23.4 / Minecraft 1.12.2**, gồm resource pack, gói cài client và overlay server có allowlist.

## Artifact phát hành hiện hành

- `build/DJ2_Viet_Hoa_2.23.4.zip` — resource pack dành cho client và server phân phối qua HTTP.
- `build/DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip` — giải nén **trực tiếp vào thư mục `minecraft`** của instance; không có thư mục bọc ngoài.
- `build/DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip` — chỉ chứa các file server localization đã review; không chứa world, playerdata, tài khoản hay cấu hình mạng.
- `build/RELEASE_MANIFEST_CURRENT.json` — hash/kích thước/entry count hiện hành.
- `build/FINAL_ACCEPTANCE_CURRENT.json` — kết quả kiểm định cuối.

Metadata và artifact cũ được giữ trong `build/archive/`, không còn nằm lẫn ở release root.

## Cài đặt client

### Khuyến nghị

1. Tắt Minecraft/launcher của instance.
2. Sao lưu các file sẽ bị ghi đè.
3. Giải nén `DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip` thẳng vào root `minecraft`.
4. Mở game và kiểm tra:
   - `Tiếng Việt (Việt Nam)` đang được chọn;
   - `DJ2_Viet_Hoa_2.23.4.zip` đang bật;
   - menu, Quest Book, JEI và tooltip hiển thị đúng dấu.

Có thể cài riêng resource pack vào `resourcepacks`, nhưng Client ZIP còn mang theo menu, Default Options, Tips, script message và các overlay an toàn khác.

## Cài đặt server

```bash
python tools/build_server_overlay.py
python tools/install_server_overlay.py
python tools/verify_server_delivery.py
```

Installer:

- tạo backup theo từng file;
- chỉ cài các path trong allowlist;
- merge riêng MOTD của FTBUtilities;
- giữ nguyên mọi gameplay setting khác;
- cập nhật riêng `resource-pack-sha1` theo bytes canonical;
- không chạm world, BetterQuesting world DB, recipe/progression hoặc player data ngoài những script message đã review.

Sau khi resource-pack helper chạy, phải tải ngược file qua URL đã cấu hình và xác minh HTTP bytes/SHA-1 trước khi cho người chơi kết nối.

## Phạm vi Việt hóa

- BetterQuesting quest text đầy đủ và UI BetterQuesting.
- Tips, guide books, Patchouli/Tinkers manuals, advancement prose và tooltip đã review.
- Client menu/default language/config và các message script an toàn.
- Batch UI/command/status/help mới cho FTBUtilities, FTBLib, FTBBackups, JEI, JEI Utilities, JEI Resources, Ender Utilities, Actually Additions và Extra Utilities 2.
- Biome-counter message được dịch nhưng vẫn giữ `Mortum`, `Hell`, `Magical Forest`, `Ocean` bằng English.

Tên item, block, fluid, mob, biome, dimension, machine, multiblock, material, mod và proper name quan trọng tiếp tục giữ English để tra JEI/Wiki và tránh phá registry/parser.

## Build và kiểm định

```bash
python tools/build_pack.py
python tools/build_client_bundle.py
python tools/build_server_overlay.py
python tools/build_release_manifest.py
python -m unittest discover -s tools -p "test_*.py" -q
python tools/verify_release.py
python tools/verify_server_delivery.py
```

Các gate kiểm tra key-set, duplicate/case-collision, placeholder `%`, mã màu `§`, URL/line control, UTF-8, JSON, CRC, deterministic bytes, Client ZIP root structure, canonical shared inputs, server allowlist, hosted bytes và SHA-1 khai báo.
