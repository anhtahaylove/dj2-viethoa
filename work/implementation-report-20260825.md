# Báo cáo triển khai Việt hóa DJ2 — 2026-08-25

## Đã triển khai

- Chuyển bốn input dùng chung Client/Server sang canonical `source/server_shared`; builder không còn đọc operational Server Pack.
- Việt hóa 8 biome-counter messages trong hai script, giữ nguyên tên biome và mọi lời gọi/logic gameplay.
- Thêm 161 key UI/help/status đã review cho FTBUtilities, FTBLib, FTBBackups, JEI, JEI Utilities, JEI Resources, Ender Utilities, Actually Additions và Extra Utilities 2.
- Giữ nguyên bản dịch Thermal Expansion đã có vì 28 candidate đều trùng key và bản canonical hiện tại đầy đủ hơn; không ghi đè bằng câu khác.
- Tạo deterministic Server Localization Overlay (7 entries), installer atomic, backup từng file, FTBUtilities MOTD-only merge và `resource-pack-sha1`-only property update.
- Thêm server delivery gate, release manifest hiện hành và final acceptance report.
- Chuyển metadata/ZIP legacy khỏi release root sang `build/archive/pre-current-manifest-20260825/`; không xóa lịch sử.
- Cài Client ZIP mới vào ElyPrism và cài overlay mới vào extracted Server Pack.
- Khởi động resource-pack helper hiện hữu; không khởi động Forge.

## Xác minh cuối

- Unit/regression: 43 tests, OK.
- `verify_release.py`: exit 0, deterministic true.
- `verify_server_delivery.py`: exit 0, hosted/canonical/declared SHA-1 bằng nhau.
- HTTP fetch qua địa chỉ đã cấu hình: 200, `application/zip`, bytes khớp canonical, SHA-1 khớp khai báo.
- Resource pack: 765 entries, CRC sạch, không duplicate/case collision.
- Client ZIP: 42 entries, giải nén vào root `minecraft`; live client pack khớp byte và `lang:vi_vn` còn hiệu lực.
- Server overlay: 7 entries; gameplay setting FTBUtilities ngoài MOTD được giữ nguyên.
- 161 key mới: không lỗi token `%`, mã `§`, URL, `|lf` hoặc raw newline.
- Không phát hiện dữ liệu riêng tư trong resource pack/Client ZIP. Bốn UUID trong Server overlay đã phân loại là SkullOwner NBT của recipe upstream, bắt buộc cho gameplay, không phải player/runtime data.

## Artifact cuối

| Artifact | Bytes | SHA-1 | SHA-256 |
|---|---:|---|---|
| `DJ2_Viet_Hoa_2.23.4.zip` | 1,615,038 | `aaa16c1fcb601c52e67ef23b5c51d4299247d786` | `7abdb9bca6e27ff622c99ac778e749e6d705667fda593590247619748206bff7` |
| `DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip` | 1,537,662 | `53d63583b580fb9545885316ba78fa35bdd58a9a` | `7a725cc81a1c02437685f6315d71ba2000cd60affcd7da95836d3b06685221d3` |
| `DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip` | 1,513,327 | `16bbfc02a35ee9c22126d5052ed2fb3dd7a5369e` | `50d2278c8b54f759aa9f2a0acdf05bdbb459919a14268c088a5dbcd35697dc8b` |

## Backup/rollback

- Client final-install backup: `work/instance-localization-backup-20260825_160146/`.
- Server installer backups: `work/server-overlay-backups/` (thư mục timestamp mới nhất thuộc lần cài cuối).

## Giới hạn còn lại

- Chưa smoke-test trực quan trong Minecraft vì launcher/game không chạy trong lúc cài và không tự khởi động game để tránh can thiệp phiên người dùng.
- Forge server không được khởi động; resource-pack HTTP helper đang chạy và đã được kiểm tra end-to-end.
- Đuôi English còn lại chủ yếu là item/block/machine/material/proper name, command literal hoặc nội dung kỹ thuật có rủi ro; giữ English có chủ đích để tra JEI/Wiki và tránh lỗi parser/mod.
