# Divine Journey 2 v2.23.4 — Việt hóa

Bộ Việt hóa dành cho **Divine Journey 2 v2.23.4 / Minecraft 1.12.2**, gồm resource pack, gói cài client và overlay server có allowlist.

Repo này chứa **mã nguồn và công cụ dựng**, không chứa artifact đã build: mọi
zip, bundle và ảnh poster đều sinh lại được từ `source/` + `work/` bằng các
script trong `tools/`.

## Tình trạng hiện tại

| Chỉ số | Giá trị |
|---|---|
| Coverage | **82,4%** (22.321 / 27.075 khóa trong phạm vi) |
| Backlog T2 / T3 / chưa phân tier | 271 / 189 / 991 |
| Validator | 0 lỗi |
| pytest | 142 passed |
| `verify_release.py` | exit 0 |

Backlog không phải là "nợ dịch" thuần: phần lớn dòng T2 còn lại là tên chòm sao
Astral Sorcery, tên nghi lễ và phép AbyssalCraft/Blood Magic — những chuỗi **cố
ý giữ English**. Con số coverage vì vậy sẽ không bao giờ chạm 100%.

Riêng T2 đã cạn trên thực tế: trong 271 dòng còn lại chỉ có 2 dòng là ký hiệu
thuần (`%s`, `%s/%s`), phần còn lại là registry mirror, tên riêng, protected
term hoặc ký hiệu. Số này sẽ không giảm thêm.

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
|---|---|
| `source/` | Văn bản English trích từ modpack, dùng làm đầu vào chuẩn |
| `work/translated/` | Bản dịch tiếng Việt, tách theo quest text và runtime locale |
| `work/runtime_locale_sources/` | Nửa English tương ứng, giữ key set 1:1 với bản dịch |
| `work/protected_terms.json` | Thuật ngữ bắt buộc giữ English, được validator kiểm tự động |
| `tools/` | Script build, validator, installer và test |
| `release/` | Artifact phát hành hiện hành (không track trong Git) |

## Artifact phát hành hiện hành

Nằm trong `release/DJ2_Viet_Hoa_2.23.4/` sau khi chạy chuỗi build:

- `DJ2_Viet_Hoa_2.23.4.zip` — resource pack dành cho client và server phân phối qua HTTP.
- `DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip` — giải nén **trực tiếp vào thư mục `minecraft`** của instance; không có thư mục bọc ngoài.
- `DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip` — chỉ chứa các file server localization đã review; không chứa world, playerdata, tài khoản hay cấu hình mạng.
- `RELEASE_MANIFEST_CURRENT.json` — hash/kích thước/entry count hiện hành.
- `FINAL_ACCEPTANCE_CURRENT.json` — kết quả kiểm định cuối.
- `SHA256SUMS.txt` — checksum của toàn bộ artifact.

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
- Nhãn giao diện Astral Sorcery (journal, perk), EnderIO, Mekanism, BiblioCraft,
  Botania, Bewitchment, EvilCraft, ProjectE, Tinkers' Construct và Quark.
- Biome-counter message được dịch nhưng vẫn giữ `Mortum`, `Hell`, `Magical Forest`, `Ocean` bằng English.

Tên item, block, fluid, mob, biome, dimension, machine, multiblock, material, mod và proper name quan trọng tiếp tục giữ English để tra JEI/Wiki và tránh phá registry/parser.

## Quy tắc dịch

Bốn quy tắc quyết định một chuỗi được dịch hay giữ English:

1. **Tên tra cứu được thì giữ English.** Item, block, máy, chất lỏng, nâng cấp,
   mod và tên riêng đều giữ nguyên để người chơi còn gõ được vào JEI và wiki.
   Trong batch EnderIO Dark Steel gần nhất, 58/74 dòng giữ English vì chúng là
   tên nâng cấp chứ không phải câu.
2. **Khuôn sinh tên vật phẩm thì giữ English.** Chuỗi như `%s Bolt`, `%s Ingot`
   hay `Block of %s` là khuôn ghép tên registry, không phải nhãn giao diện.
   Dịch chúng sẽ làm hỏng hàng loạt tên trong JEI.
3. **Tiền lệ trong corpus thắng cách dịch mới.** Nếu một thuật ngữ đã có bản
   dịch từng phát hành thì tái sử dụng, kể cả khi cách dịch mới nghe hay hơn.
   Validator consistency là trọng tài cho quy tắc này.
4. **`protected_terms.json` thắng tất cả.** Được kiểm tự động; không sửa file
   này để một bản dịch đi qua được validator.

Với chuỗi vừa có phần chung vừa có tên riêng thì dịch phần chung và giữ tên
riêng: `Root: Aevitas` → `Cội: Aevitas`.

Cú pháp lệnh giữ nguyên English vì người chơi phải gõ đúng từng ký tự
(`/team create <id> [color]`); chỉ dịch phần văn bản trò chơi in ra.

Đồng âm khác nghĩa xử lý bằng `CONSISTENCY_EXEMPT` trong
`tools/validate_translated_locales.py`, kèm chú giải lý do — ví dụ `Ocean` là
biome vanilla, khác `Ocean` là tên chòm sao Octans; hay `Pillar` là chế độ xây
của Mercurial Eye, khác `Pillar` là tên hình dạng microblock.

Một số chuỗi trông như từ nhưng không phải: `pe.transmutation.learned*` của
ProjectE là animation hiện từng **ký tự** của chữ "Learned!", nên toàn bộ nhóm
key này giữ English.

## Lịch sử phát hành

Mỗi wave đều đi hết chuỗi validator → build → publish → install → verify →
pytest trước khi commit.

| Commit | Nội dung | Coverage |
|---|---|---|
| `e7c76c1` | Đưa dự án vào Git, 2.535 file | — |
| `3cb7738` | 64 nhãn config UniversalTweaks | — |
| `8a45f78` | Sửa 2 khuôn tên item GregTech + 5 nhãn UI | 79,8% |
| `70b3c1f` | 419 nhãn Astral Sorcery, Extra Utilities 2, EnderIO | 81,0% |
| `936a6fc` | 438 nhãn thuộc 28 namespace | 82,0% |
| `6613794` | 404 nhãn thuộc 8 namespace | 82,4% |
| `f7dabd4` | Sửa tên đơn vị Quintillion trong EMC postfix | 82,4% |

Vài lỗi đáng nhớ mà các gate đã bắt được:

- **Khuôn tên item bị dịch** (`8a45f78`): `base.part.bolt` và `base.part.round`
  của GregTech là khuôn `%s Bolt`/`%s Round`, dịch chúng làm hỏng hàng loạt tên
  trong JEI.
- **Key tự bịa** (`70b3c1f`): trong lúc sửa consistency collision đã tạo một key
  không tồn tại trong JAR; từ đó mọi sửa đổi phải kiểm `set(vi) ⊆ set(source)`.
- **Dịch từng ký tự** (`6613794`): 16 key animation của ProjectE bị dịch theo
  từng chữ cái và làm mất một key.
- **Sai bậc đơn vị** (`f7dabd4`): `Quintillion` (10¹⁸) bị dịch thành "Tỷ tỷ"
  trong khi chuỗi trước đó là 10¹² "Nghìn tỷ" → 10¹⁵ "Triệu tỷ"; test doubling
  bắt được, giá trị đúng là "Nghìn triệu tỷ".

## Build và kiểm định

```bash
# 1. Kiểm tra bản dịch trước khi build
python tools/validate_runtime_locales.py
python tools/validate_translated_locales.py

# 2. Dựng resource pack và các bundle
python tools/build_pack.py
python tools/build_client_overlays.py
python tools/build_client_bundle.py
python tools/build_server_overlay.py
python tools/build_release_manifest.py
python tools/build_final_acceptance.py

# 3. Kiểm định
python -m pytest tools/ -q
python tools/verify_release.py
python tools/verify_server_delivery.py

# Đo tiến độ bất cứ lúc nào
python tools/measure_coverage.py
python tools/tier_missing.py
```

Các gate kiểm tra key-set, duplicate/case-collision, placeholder `%`, mã màu `§`, URL/line control, UTF-8, JSON, CRC, deterministic bytes, Client ZIP root structure, canonical shared inputs, server allowlist, hosted bytes và SHA-1 khai báo.
