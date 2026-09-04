# Divine Journey 2 v2.23.4 — Việt hóa

Bộ Việt hóa dành cho **Divine Journey 2 v2.23.4 / Minecraft 1.12.2**, gồm resource pack, gói cài client và overlay server có allowlist.

Repo này chứa **mã nguồn và công cụ dựng**, không chứa artifact đã build: mọi
zip, bundle và ảnh poster đều sinh lại được từ `source/` + `work/` bằng các
script trong `tools/`.

## Tình trạng hiện tại

| Chỉ số | Giá trị |
|---|---|
| Coverage | **83,5%** (22.618 / 27.075 khóa trong phạm vi) |
| Backlog T2 / T3 / chưa phân tier | 270 / 189 / 563 |
| Nợ dịch thật trong backlog | **0** (cả ba tier) |
| Khóa trùng English đã rà | 3.280 (còn lại đều cố ý giữ English) |
| Validator | 0 lỗi |
| pytest | 192 passed |
| `verify_release.py` | exit 0 |

Backlog không phải là "nợ dịch" thuần: phần lớn dòng T2 còn lại là tên chòm sao
Astral Sorcery, tên nghi lễ và phép AbyssalCraft/Blood Magic — những chuỗi **cố
ý giữ English**. Con số coverage vì vậy sẽ không bao giờ chạm 100%.

Wave 20 đã rà hết cả ba tier bằng `tools/triage_other_tier.py`: **1.022 dòng
còn lại đều cố ý giữ English, không còn nợ dịch nào**. Phân bố lý do:

| Lý do giữ English | T2 | T3 | `other` |
|---|---|---|---|
| Protected term / tên item, block, registry | 206 | — | 265 |
| Tên riêng (chòm sao, nghi lễ, phép, brew, biome, potion, entity) | 41 | — | 131 |
| Cú pháp lệnh người chơi phải gõ | — | 98 | 12 |
| Tên mod bên thứ ba (`cfg.universaltweaks.*`) | — | 91 | — |
| Khuôn format, ký hiệu, mã màu, đơn vị, notation | 12 | — | 61 |
| Id nội bộ (shader, loot table, structure, transformer, style) | 1 | — | 46 |
| Khuôn tên item (`%s Bolt`, GregTech) | — | — | 39 |
| Tiêu đề màn hình lặp lại tên registry | 10 | — | 9 |
| **Tổng** | **270** | **189** | **563** |

Chạy `python tools/triage_other_tier.py --tier <T2\|T3\|other>` để xem thống kê,
thêm `--list <namespace>` để xem chi tiết từng mod.

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
|---|---|
| `source/` | Văn bản English trích từ modpack, dùng làm đầu vào chuẩn |
| `work/translated/` | Bản dịch tiếng Việt, tách theo quest text và runtime locale |
| `work/runtime_locale_sources/` | Nửa English tương ứng, giữ key set 1:1 với bản dịch |
| `work/protected_terms.json` | Thuật ngữ bắt buộc giữ English, được validator kiểm tự động |
| `tools/` | Script build, validator, installer và test |
| `release/` | Artifact phát hành hiện hành; ZIP không track, còn manifest/acceptance/verification/checksum thì có (bằng chứng đã ship) |

### Công cụ kiểm tra bổ sung

| Script | Mục đích |
|---|---|
| `tools/restore_english_sources.py` | Dựng lại nửa English của `work/runtime_locale_sources/` từ JAR và `resources/`. Chạy `--write` để ghi, không tham số để xem báo cáo. |
| `tools/check_button_widths.py` | Đo bề rộng pixel chuỗi Việt bằng `glyph_sizes.bin` thật, so với bản English và mẫu tham chiếu, phát hiện nguy cơ tràn nút. |
| `tools/triage_other_tier.py` | Phân loại backlog T2/T3/`other` thành "cố ý giữ English" và "nợ dịch thật", kèm thống kê lý do và namespace (`--tier`, `--list`). |
| `tools/report_cross_store_conflicts.py` | Tìm khoá mà hai store **cùng nạp vào một namespace** lại có bản dịch khác nhau (exit 1 nếu có); `--all` in cả các cặp vô hại. |
| `tools/test_extract_runtime_sources.py` | Ngoài test harvest, còn có `EnglishSourcePurityTests` chống việc `work/runtime_locale_sources/` bị nhiễm tiếng Việt trở lại. |

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
| `41ed0a0` | Cập nhật README theo wave 18 | 82,4% |
| `d73eb7c` | Khôi phục nguồn English thật, sửa các lỗi bị che | 82,4% |
| `d56786e` | 428 nhãn `other` thuộc 60 namespace, dọn xung đột cross-family | 83,5% |
| `ee628a0` | Rà hết T2/T3/`other`: 0 nợ dịch còn lại, thêm pytest gate xung đột | 83,5% |
| wave 21 | Rà 3.286 khóa trùng English (6 nợ ẩn), gate EOL, chuỗi build hợp nhất | 83,5% |

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
- **Nguồn English bị nhiễm tiếng Việt** (wave 19): 7.014 khóa trong
  `work/runtime_locale_sources/` chứa **bản dịch tiếng Việt thay vì English
  gốc**. Vì mọi validator và test đều so `source` với `translated`, chúng thực
  chất đang so tiếng Việt với chính nó — guard trở nên **mù hoàn toàn** trên
  phần lớn corpus. Sau khi dựng lại nguồn từ JAR + `resources/`
  (`tools/restore_english_sources.py`), các gate lập tức phát hiện 74 lỗi
  consistency và 38 lỗi định dạng đã tồn tại từ nhiều wave trước, trong đó có
  6 chuỗi CraftTweaker **mất toàn bộ mã màu `§`**. Bản dịch không mất chữ nào —
  6.373/6.396 khóa vẫn khớp — nhưng bài học là: nếu một gate không bao giờ đỏ,
  hãy nghi ngờ dữ liệu đầu vào của chính nó.
- **Bundle lồng nhau bị cũ** (wave 19): `verify_release.py` chỉ hash các ZIP
  ngoài, nên client bundle và server overlay từng mang resource pack **trước
  wave 18** mà vẫn exit 0. Đã bổ sung `nested_pack_mismatch`: mở ZIP lồng, so
  hash với bản standalone; gate được kiểm bằng cách cố tình chèn pack cũ và xác
  nhận verify chuyển sang exit 1.
- **Key `button.*` không phải lúc nào cũng là mặt nút** (wave 19): bốn khóa
  `button.*.name` của Guide-API bị `check_button_widths.py` báo tràn khung suốt
  nhiều wave. Đọc bytecode (`javap -c ButtonBack.class`) cho thấy chúng được
  dùng trong `getHoveringText()` — tức là **tooltip khi rê chuột**, còn nút thật
  chỉ là texture 18×10 không vẽ chữ. Tooltip không bị giới hạn bởi bề rộng nút,
  nên đây là cảnh báo giả; đã thêm `NOT_BUTTON_FACE` kèm chú giải nguồn gốc.
  Bài học: trước khi rút gọn một nhãn cho vừa khung, hãy xác minh trong mod xem
  chuỗi đó có thật sự được vẽ lên mặt nút hay không.
- **File dịch chết** (wave 19): `work/translated/p2_thermalexpansion.json` và
  `work/translated/orphans-test.json` không nằm trong `include_stems` của
  `build_pack.py`, nên **chưa bao giờ được ship**. Chúng vẫn tạo ra 22 "xung đột
  cross-family" giả trong `report_cross_store_conflicts.py`. Điều đáng chú ý:
  bản dịch trong file chết lại **đúng convention hơn** bản đang ship (sentence
  case so với Title Case), nên trước khi xoá phải đối chiếu từng khoá — 20 nhãn
  `thermalexpansion` đã được sửa theo tiền lệ corpus rồi mới xoá file.
- **"Xung đột" giữa hai store không cùng namespace là báo giả** (wave 20):
  `report_cross_store_conflicts.py` từng so mọi cặp store, nên 7.354 khoá trùng
  giá trị và 28 khoá ở namespace khác nhau đều bị đếm là xung đột. Build merge
  theo **từng namespace**, nên chỉ khi hai store cùng nạp vào một namespace mà
  giá trị khác nhau thì mới có khoá bị ghi đè. Đã viết lại reporter dùng chung
  `lang_family_specs()` với `build_pack.py` (một nguồn sự thật cho ánh xạ
  store → namespace) và thêm `tools/test_report_cross_store_conflicts.py` để
  chặn hồi quy; gate được kiểm bằng mutation: chèn một giá trị khác vào
  `p2_roots.json` làm pytest exit 1, khôi phục thì xanh lại.
- **Regex triage bỏ sót placeholder có số** (wave 20): `COMMAND` chỉ khớp
  `<abc>`/`[abc]` nên `<x1> <y1> [dim1]` và `[params...]` bị coi là nợ dịch, dù
  đó là cú pháp lệnh người chơi phải gõ. Sau khi mở rộng regex và bổ sung các
  quy tắc suy ra từ corpus (giá trị là protected term của **bất kỳ** mod nào,
  tiêu đề màn hình lặp lại tên registry cùng namespace, tên mod bên thứ ba,
  khuôn format không còn chữ nào để dịch), backlog 1.022 dòng còn lại **không
  còn nợ dịch nào**. Mọi quy tắc mới đều được kiểm ngược trên toàn corpus đã
  ship để chắc chắn không có false positive (0 dòng đã dịch bị quy tắc mới
  nhận nhầm là "giữ English").
- **`OK` không dịch, nhưng `Confirm` thì dịch** (wave 20): hai khoá
  `generic.ok.txt` và `singles.buildinggadgets.confirm` có giá trị English là
  `OK`/`Ok`. Corpus cho thấy `Cancel` → `Hủy` và `Confirm` → `Xác Nhận`, nhưng
  `OK` được giữ nguyên ở **mọi** vị trí đã ship (`actuallyadditions`, `waila`).
  Bài học: quyết định theo tiền lệ của **chính chuỗi đó**, không suy từ chuỗi
  cùng nhóm chức năng.
- **`Void` là hai từ khác nhau** (wave 20): `roots.modifiers.modifiers.shatter_void`
  = `Voiding` (động từ, "phá huỷ vật phẩm" → `Hủy Vật Phẩm`) còn
  `forge.biome.tags.void.name` = `Void` (danh từ, "Hư không"). Khi dịch
  `voiding_scythe` theo tiền lệ động từ, validator consistency báo lệch thuật
  ngữ. Đây là homograph thật nên đã thêm `CONSISTENCY_EXEMPT` đúng khoá, và
  mutation-test xác nhận exemption không che lệch ở các khoá `Void` khác.

## Build và kiểm định

```bash
# 1. Kiểm tra bản dịch trước khi build
python tools/validate_runtime_locales.py
python tools/validate_translated_locales.py
python tools/check_line_endings.py

# 2. Dựng artifact + tự đồng bộ release/ (coverage -> pack -> ... -> acceptance -> sync)
#    Bước cuối copy artifact và 5 file bằng chứng sang release/ rồi tạo lại SHA256SUMS.txt.
python tools/build_release_chain.py
# xem thứ tự mà không chạy: python tools/build_release_chain.py --dry-run

# 3. Kiểm định
python -m pytest tools/ -q
python tools/verify_release.py
python tools/verify_server_delivery.py

# Đo tiến độ bất cứ lúc nào
python tools/measure_coverage.py
python tools/tier_missing.py
```

Các gate kiểm tra key-set, duplicate/case-collision, placeholder `%`, mã màu `§`, URL/line control, UTF-8, JSON, CRC, deterministic bytes, Client ZIP root structure, canonical shared inputs, server allowlist, hosted bytes và SHA-1 khai báo.
