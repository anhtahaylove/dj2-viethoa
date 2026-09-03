# Audit Việt hóa instance ElyPrism — Divine Journey 2

Ngày: 2026-08-25  
Phạm vi: read-only  
Instance: `C:\Users\Administrator\AppData\Roaming\ElyPrismLauncher\instances\Divine Journey 2`  
Root Minecraft thực: `...\Divine Journey 2\minecraft`

## Kết luận ngắn

Instance đã được Việt hóa phần lớn và đang chạy đúng locale `vi_vn` với resource pack DJ2.  
Vẫn còn vài khoảng trống **nên làm thêm**, trong đó có 2–3 hạng mục ưu tiên cao và một đuôi dài UI mod chung.

Không nên sửa trực tiếp instance nguồn. Mọi bổ sung nên đi qua source overlay → `work/translated` → rebuild pack/Client ZIP.

## Trạng thái runtime đã xác minh

| Hạng mục | Giá trị |
|---|---|
| Pack version | Divine Journey 2 `2.23.4` |
| Minecraft / Forge | `1.12.2` / `14.23.5.2860` |
| `options.txt` lang | `vi_vn` |
| `forceUnicodeFont` | `true` |
| Resource packs bật | `Aether b1.7.3 Textures`, `DJ2_Viet_Hoa_2.23.4.zip` |
| Quest keys tham chiếu | `3532/3532` có trong `vi_vn.lang` |
| Tips Việt | `129/129`, không còn dòng English thuần |
| Triumph DJ2 scripts | khớp Client ZIP |
| Script overlay chính | `scripts/JEI/Excavator.zs`, `scripts/ContentTweaker/ContentTweakerItems.zs` khớp Client ZIP |
| Log missing-translation chính xác | không có hit thực sự |
| So sánh Client ZIP | 30 file khớp, 2 file khác, 1 file hướng dẫn thiếu |

### Override runtime cần lưu ý

Log gọi `minecraft/resources` là `CustomOverridingResources`; lớp này được nạp sau resource pack. Đây không phải resource-pack ZIP riêng mà là lớp tài nguyên do modpack/script sinh ra. Nó có 5 locale English (`betterquesting`, `contenttweaker`, `crafttweaker`, `enchantment_descriptions`, `requious_frakto`) và không có `vi_vn`.

Với locale `vi_vn`, resource pack DJ2 vẫn phủ các key đã dịch. Khi một key chưa có bản Việt, game fallback về English từ lớp này. Hai gap cụ thể đã xác minh là `requious_frakto` và một enchantment description.

## So với bản Việt hóa canonical hiện tại

| Artifact | Instance | Canonical / Client ZIP | Kết luận |
|---|---|---|---|
| Resource pack entries | 760 | 760 | Cùng tập file |
| Pack SHA-1 | `a3d6fe3ded9317913d6cf402530ac88ade29993f` | `814872a112ecfa0eb5ae22829c80b55dc172665e` | **Instance đang dùng pack cũ hơn** |
| Diff locale trong pack | thiếu TPA/`click_here` | đã có | Cần cập nhật pack |
| `config/tips.cfg` | khớp | khớp | OK |
| `config/ftbutilities.cfg` | MOTD English cũ + setting khác | MOTD Việt + hướng dẫn `/tpa` | Nên đồng bộ có chọn lọc |
| `HUONG_DAN_CAI_DAT.txt` | thiếu | có | Chỉ hướng dẫn, không ảnh hưởng gameplay |

### Diff pack quan trọng

Instance thiếu các key mới trong:

- `assets/ftbutilities/lang/vi_vn.lang` (`/tpa`, `/tpaccept`, `/tpdeny`, thông báo TPA)
- `assets/ftblib/lang/vi_vn.lang` (`click_here`)

## Những gì đã Việt hóa tốt / không cần làm thêm

1. **Quest book BetterQuesting**  
   `DefaultQuests.json` chỉ dùng language keys; toàn bộ key được cover.  
   Có **96 giá trị `vi_vn` vẫn giống English**: 91 title và 5 description. Năm description là rỗng hoặc rune/encoded text nên giữ nguyên. Phần lớn title là item/machine/proper name, nhưng khoảng 10–12 title prose/pun cần review và có thể dịch, ví dụ `The Collector`, `Part of the Golden Club`, `Compressor Automation`, `The PenULTIMATE Crafting Table`, `Yet Another Machiavellian Machine Frame (YAMMF)`, `The Enderest of Enderer Pearls`.

2. **Tips loading screen**  
   `config/tips.cfg` đã Việt hóa đầy đủ.

3. **CraftTweaker / DJ2 tooltips chính**  
   Namespace `crafttweaker` đủ key; phần identical chủ yếu là dimension/item/proper name.

4. **ContentTweaker item/fluid names**  
   730 key English còn lại đều là `.name` / fluid names → **giữ English** theo policy JEI/wiki.

5. **Patchouli / books / manuals trong pack**  
   Manifest Patchouli `579` khớp số file `vi_vn` trong pack; còn book/manual artifacts khác.

6. **Enchantment descriptions**  
   Loose English file còn tồn tại; hầu hết đã có bản Việt trong các `vi_vn.lang` của pack.  
   Ngoại lệ nhỏ: `enchantment.endercore.soulbound.desc` (`Item is not dropped on death.`) chưa có trong pack.  
   Source cũ từng ghi nhầm thành `enchantment.enderio.soulbound.desc` — nên sửa key này khi làm đợt tiếp.

## Khoảng trống nên / cần Việt hóa thêm

### P0 — Nên làm ngay (ảnh hưởng thực tế, phạm vi nhỏ)

1. **Cập nhật resource pack instance lên bản canonical có TPA**  
   Người chơi dùng `/tpa` trên client này vẫn có thể thấy chuỗi English thiếu locale.

2. **Đồng bộ phần text Việt trong `ftbutilities.cfg`**  
   Ít nhất MOTD và usage hướng dẫn `/tpa` / `/tpaccept`.  
   Không copy nguyên file nếu không muốn kéo theo thay đổi gameplay server-oriented (`fly/god/heal`, auto-shutdown, PVP...).

### P1 — Đáng làm tiếp theo (nhìn thấy rõ, ít rủi ro)

3. **Custom Main Menu**  
   Chữ English được bake vào PNG:
   - `SINGLEPLAYER`
   - `MULTIPLAYER`
   - `OPTIONS`
   - `MODS`
   - `VERSION HISTORY`
   - `QUIT GAME`  
   Tooltip/label text còn English:
   - `Join the Divine Journey 2 Discord Server!`
   - `Language`
   - `#modsloaded# Mods Loaded`  
   Nên giữ nguyên: `Divine Journey 2`, `Divine Journey 2.23.4`, credit creator, `Copyright Mojang AB`.

4. **Requious Frakto JEI categories** — `resources/requious_frakto/lang/en_us.lang`  
   10 title JEI vẫn English, ví dụ:
   - `Excavator Veins`
   - `Activate Block or Entity`
   - `Configure Block`
   - `Explore the World`
   - `Roots Entity Summoning Helper`  
   Đây là gap nhỏ, rõ ràng, phù hợp overlay `vi_vn.lang`.

5. **Enchantment description còn sót**  
   `enchantment.endercore.soulbound.desc` chưa có trong pack Việt hóa.

6. **Quest titles còn English nhưng không phải tên item thuần**  
   Review thủ công 91 title identical; chỉ dịch nhóm prose/pun. Không dịch các title chính là item/machine/dimension/proper name. Không sửa `DefaultQuests.json`; chỉ cập nhật `assets/betterquesting/lang/vi_vn.lang` qua source/`work/translated`.

7. **DefaultOptions / Crash Assistant**  
   `config/defaultoptions/options.txt` vẫn là `lang:en_us`, `resourcePacks:[]`, `forceUnicodeFont:false`. Nó không ảnh hưởng profile hiện tại nhưng có thể làm options tạo mới trở về English. Crash Assistant có `default_lang="en_us"` và không có override Việt; UI crash/help có thể còn English. Đây là client-config overlay riêng, không phải locale resource pack thông thường.

### P2 — Có thể làm nếu muốn phủ rộng UI mod

Quét effective locale còn khoảng **~8.8k candidate UI keys / 136 namespaces** chưa có `vi_vn` hiệu dụng.  
Top namespace theo số lượng:

- `chisel` (~2817)
- `groovyscript` (~647)
- `roots` (~297)
- `enderutilities` (~245)
- `immersiveengineering` (~227)
- `tconstruct` (~203)
- rồi Actually Additions, Astral Sorcery, BiblioCraft, Integrated Tunnels, AbyssalCraft, FTB, Ender IO, JourneyMap, JEI...

Đây là đuôi dài UI/tooltip/config chung của mod, **không phải lỗ hổng DJ2-core**. Chỉ nên làm theo đợt có ưu tiên người chơi thật sự gặp.

## Không nên Việt hóa

- Tên item / block / mob / dimension / multiblock / proper name
- `DefaultQuests.json` progression/criteria/reward
- Mod JAR gốc
- Recipe / script logic
- Credit Mojang / tên pack / tên tác giả modpack

## Khuyến nghị hành động

1. Rebuild/publish không cần nếu canonical đã sẵn; chỉ cần **cập nhật pack + MOTD/TPA text** vào instance bằng Client ZIP hoặc copy chọn lọc.
2. Thêm overlay:
   - `requious_frakto` JEI titles
   - CustomMainMenu PNG + tooltip text
3. Nếu muốn phase 2: chọn 5–10 namespace UI người chơi hay gặp nhất thay vì dịch hết 8k key.

## Artifact phụ

- `work/elyprism-locale-gap-candidates.json`
- `work/elyprism-effective-ui-gaps.json`
- `work/custom-main-menu-assets-contact-sheet.png`

## Triển khai hoàn tất — 2026-08-25

Đã triển khai theo hướng **canonical source → deterministic build → regression → cài instance → byte-level verification**. Không sửa mod JAR, `DefaultQuests.json`, registry, recipe, criteria, reward hay progression.

### Nội dung đã triển khai

- Resource pack canonical mới đã được build và cài vào instance.
- `config/ftbutilities.cfg`: chỉ thay block `S:motd`; toàn bộ nội dung ngoài trường này giữ nguyên byte-ngữ nghĩa so với bản live trước khi merge. MOTD có hướng dẫn `/tpa` và `/tpaccept`.
- Custom Main Menu:
  - Việt hóa sáu PNG: `CHƠI ĐƠN`, `CHƠI MẠNG`, `TÙY CHỌN`, `MOD`, `LỊCH SỬ PHIÊN BẢN`, `THOÁT GAME`.
  - Việt hóa tooltip Discord/Language và nhãn `#modsloaded# Mod đã tải`.
  - Giữ nguyên action, URL, vị trí, version, credit và tên `Divine Journey 2`.
- Requious Frakto: thêm đủ 10 JEI category title.
- Enchantment Descriptions: đã có `enchantment.enderio.soulbound.desc=Vật phẩm không rơi ra khi chết.` (key runtime thực tế; không tạo key giả `endercore.soulbound`).
- BetterQuesting: review đủ 91 title từng giống English; dịch 17 title prose/pun, giữ 74 title item/mod/machine/proper name bằng English. Năm description kỹ thuật/rune tiếp tục giữ nguyên. Hai pun vật liệu được bổ sung từ review độc lập cuối: `Yeet-rium` → `Yttrium quăng bay`, `Chad-mium` → `Cadmium chuẩn Chad`.
- Default profile:
  - `lang:vi_vn`
  - `resourcePacks:["DJ2_Viet_Hoa_2.23.4.zip"]`
  - `forceUnicodeFont:true`
- Crash Assistant: `default_lang = "vi_vn"`.
- P2 chọn lọc, key-level (không dịch registry names): 29 Chisel + 7 GroovyScript + 43 Roots = **79** key UI/tooltip/JEI prose.

### Build và kiểm thử

- Full regression: **36/36 đạt**.
- Resource pack:
  - bytes: `1,610,336`
  - entries: `762`
  - `vi_vn.lang`: `103`
  - SHA-1: `6c290383689565dd734c76264bd7a1183fac0d74`
  - SHA-256: `9389b47382706d2088c9549ae13292b539c655096ec14d315a58ff26907b0867`
  - CRC: đạt; deterministic rebuild: đạt.
- Client ZIP:
  - bytes: `1,532,892`
  - entries: `42`; không có thư mục bọc ngoài.
  - SHA-1: `820d30f7810b1741eb0f46f9df43388facf643be`
  - SHA-256: `43b222da1a8e696182de328e7d4a24915e195a006ac3d2d5ce5b3fa81a8340b9`
  - CRC: đạt; chứa đúng bytes resource pack canonical.

### Xác minh instance sau cài

- 40 file bundle áp dụng trực tiếp khớp byte; 0 mismatch.
- Resource pack instance SHA-1 khớp canonical và ZIP CRC đạt.
- `options.txt` hiện tại vẫn là `vi_vn` và vẫn bật pack.
- Default Options, Crash Assistant, menu literal, sáu PNG và MOTD đều đạt kiểm tra.
- Không còn `Hello player!`; có cả `/tpa` và `/tpaccept`.
- Không có file tạm `.hermes-new` còn sót.
- Backup trước thay đổi: `work/instance-localization-backup-20260825_141946/`.

### Đuôi dài còn lại

Các namespace lớn vẫn còn nhiều registry/item/block/proper-name hoặc prose giá trị thấp chưa dịch. Đợt này cố ý dừng ở batch 79 key được review thủ công; không nhập hàng nghìn tên Block/item của Chisel/Roots để giữ khả năng tra JEI/wiki và tránh dịch máy lan rộng.
