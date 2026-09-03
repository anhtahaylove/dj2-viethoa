# DJ2 Việt hóa — audit tiếp Client pack và Server pack

Ngày audit: 2026-08-25

Phạm vi được đọc trực tiếp:

- canonical project và hai ZIP trong `build/`;
- ElyPrism instance `Divine Journey 2/minecraft`;
- extracted Server Pack và Server Pack ZIP;
- mod JAR locale `en_us`/`en_US` đối chiếu với resource pack `vi_vn`.

Không sửa file trong đợt audit này.

## Kết luận

Bản hiện tại đã hoàn thiện phần cốt lõi: quest/book/Tips/menu/default language/Crash Assistant/Requious/Soulbound/P2 đã có, Client ZIP hợp lệ và instance khớp 40/42 mục; hai ngoại lệ là `ftbutilities.cfg` được merge có chủ đích và `HUONG_DAN_CAI_DAT.txt` không cần cài vào game.

Tuy nhiên vẫn còn một lỗi phát hành P0 ở Server pack, hai khoảng trống P1 rõ ràng và một đuôi dài P2 lớn.

## P0 — phải sửa trước lần chạy/phát hành server kế tiếp

### P0.1 Resource pack server đang cũ hơn canonical

- Hosted file: `Server_Pack/resourcepack/DJ2_Viet_Hoa_2.23.4.zip`
  - 1,607,242 byte
  - SHA-1 `814872a112ecfa0eb5ae22829c80b55dc172665e`
- Canonical mới:
  - 1,610,336 byte
  - SHA-1 `6c290383689565dd734c76264bd7a1183fac0d74`
- `server.properties:resource-pack-sha1` vẫn là hash cũ, nên hiện tự nhất quán với file cũ nhưng không phân phối bản Việt hóa cuối cùng.
- Port resource-pack và Forge hiện đều không lắng nghe, nên chưa thể smoke-test HTTP. Không có người chơi/runtime đang hoạt động trong lúc audit.

Cách sửa an toàn: copy đúng canonical ZIP sang `resourcepack/`, cập nhật riêng `resource-pack-sha1`, khởi động endpoint rồi GET bytes và đối chiếu SHA-1. Không đổi URL/bind/gameplay config.

### P0.2 Release verifier chưa gate Server pack

`tools/verify_release.py` kiểm tra resource pack và Client ZIP nhưng không kiểm tra hosted file/server.properties. Đây là nguyên nhân drift P0 không chặn build.

Cần thêm test/gate cho:

- hosted bytes == canonical bytes;
- declared SHA-1 == hosted bytes;
- Java-properties URL decode thành URL hợp lệ;
- HTTP GET bytes == declared SHA-1 khi endpoint đang chạy.

## P1 — nên hoàn thiện trong vòng tiếp theo

### P1.1 Tám thông báo đếm biome vẫn bằng English

Các dòng hoạt động:

- `scripts/ContentTweaker/ContentTweakerItems.zs:949-952`
- `scripts/ModSpecific/ContentTweakerRecipes.zs:1133-1136`

Bốn nhãn lặp hai lần: `Mortum biome matches`, `Hell biome matches`, `Magical Forest biome matches`, `Ocean biome matches`.

Nên đổi phần prose thành `Số biome ... khớp:` nhưng giữ nguyên tên biome English. Vì hai script tồn tại trên cả client/server và đang khớp byte, phải sửa canonical rồi phát hành đồng bộ hai phía.

### P1.2 Hoàn thiện FTBUtilities/FTBLib/FTBBackups UI và command feedback

Scan key-level vẫn còn nhiều key người chơi/admin gặp trực tiếp. Nhóm ưu tiên nhỏ thay vì dịch cả namespace:

- `/tpa`, teleport/home/chunk command usage, success/error/permission messages;
- server info, ranks, backup status/failure;
- AFK kick countdown;
- các nút/xác nhận FTB GUI.

Không dịch config metadata hoặc tên proper/mod. Mỗi key phải giữ chính xác `%s`, `%d`, `%%` và mã màu.

### P1.3 Server distributable ZIP chưa mang trạng thái Việt hóa runtime

ZIP gốc khác extracted server ở ít nhất `server.properties`, `ftbutilities.cfg`, `tips.cfg` và localized scripts. Điều này không phải lỗi của live server, nhưng dễ khiến khôi phục/cài mới quay lại English.

Nên có một Server localization overlay/bundle deterministic riêng, thay vì rebuild/copy cả Server Pack 423 MB hoặc ghi đè toàn bộ config.

## P2 — cải thiện theo batch có kiểm soát

Scan bảo thủ vẫn còn khoảng 2,556 key UI/prose giống English hoặc chưa có trong 131 namespace. Số này không đồng nghĩa tất cả nên dịch. Batch đáng làm tiếp:

1. `enderutilities`: info-area/tooltips dài, trực tiếp giải thích thao tác GUI.
2. `ftbutilities`, `ftblib`, `ftbbackups`: command/admin feedback.
3. `jei`, `jeiutilities`, `jeresources`: tooltip/help còn thiếu.
4. `actuallyadditions`, `thermalexpansion`, `extrautils2`, `botania`, `astralsorcery`, `bloodmagic`: chỉ GUI/tooltips/prose.
5. `groovyscript`: chỉ phần người chơi/maintainer thực sự nhìn thấy; không dịch toàn bộ wiki API 1,100+ key.

Tiếp tục loại trừ item/block/fluid/entity/biome/dimension/machine/proper names để tra JEI/wiki.

## Client pack — vấn đề chất lượng/phát hành

- Client ZIP: 42 mục, CRC đạt, không wrapper, không thấy IPv4/UUID/email/private key.
- Instance khớp 40 mục. `ftbutilities.cfg` khác có chủ đích vì merge bảo toàn setting; guide không cần copy vào root game.
- `config/tips.cfg`: đủ 129/129 tip, toàn bộ có tiếng Việt, client/server khớp byte.
- `HUONG_DAN_CAI_DAT.txt` dùng UTF-8 BOM. Không phải lỗi runtime, nhưng nên chuẩn hóa UTF-8 không BOM và LF/CRLF nhất quán.
- Thư mục `build/` còn ZIP legacy `Divine Journey 2 - Viet Hoa By huuhungn - ver 2.23.4.zip` (33 mục, hash cũ) và nhiều metadata/final-gate hash cũ. Dễ chọn nhầm artifact. Nên chuyển legacy sang `build/archive/` hoặc đổi tên rõ `LEGACY_DO_NOT_RELEASE`; giữ canonical source/history, không xóa bừa.
- `HUONG_DAN_CAI_DAT.txt` nói giải nén toàn bộ nhưng bản thân guide không cần ở instance; có thể ghi rõ đây là file hướng dẫn ngoài game.

## Server pack — phần đã tốt

- FTB MOTD đã Việt hóa; có `/tpa` và `/tpaccept`, không còn `Hello player!`.
- `server.properties` MOTD đã dùng Unicode escape hợp lệ.
- `server-ip` không wildcard và helper resource-pack bind địa chỉ cụ thể, không `0.0.0.0`.
- `white-list=true`.
- 129 Tips Việt hóa khớp client/server.
- Các script chung quan trọng hiện khớp byte giữa client/server.
- BetterQuesting world DB và default DB đều là JSON hợp lệ; world DB khác default là trạng thái runtime bình thường, không được ghi đè.
- Không phát hiện duplicate locale key. Bốn value rỗng đều tương ứng source English rỗng, không phải thiếu dịch.

## Rủi ro không nên xử lý như localization

- `online-mode=false` là rủi ro vận hành nhưng có thể là chủ ý cho mạng riêng; không tự đổi trong đợt Việt hóa.
- Extracted server khác stock archive ở nhiều config/runtime file; không copy nguyên stock archive hoặc nguyên config trở lại.
- Crash Assistant/defaultoptions/CustomMainMenu là client-facing; không cần ép bản vi_vn vào dedicated server trừ khi làm bundle cài mới dùng chung có chủ đích.

## Thứ tự triển khai đề xuất

1. Sửa P0 hosted resource pack + SHA-1, thêm server release gate.
2. Việt hóa 8 biome-counter messages, đồng bộ client/server.
3. Chọn batch khoảng 60-120 key FTB command/status GUI theo tần suất.
4. Tạo deterministic Server localization overlay và manifest.
5. Dọn cấu trúc release/legacy metadata.
6. Sau đó mới mở các batch P2 theo namespace.


## Bổ sung sau fan-out audit độc lập

Các phát hiện sau được kiểm tra lại trực tiếp sau khi ba audit độc lập hoàn tất:

### P1 — canonical client build còn phụ thuộc mutable Server Pack

`tools/build_client_bundle.py` đọc trực tiếp bốn input từ extracted operational Server Pack:

- `config/tips.cfg`
- `config/ftbutilities.cfg`
- `scripts/JEI/Excavator.zs`
- `scripts/ContentTweaker/ContentTweakerItems.zs`

Điều này khiến cùng source canonical có thể sinh Client ZIP khác nếu server được sửa. Cần đưa reviewed copies vào `source/server_shared/` (hoặc generator riêng), lưu upstream hash, và chỉ dùng operational server làm destination/verification target.

### P0 khi chia sẻ/publish workspace hoặc Server Pack — dữ liệu riêng nằm trong release-adjacent tree

Không có leak trong hai ZIP phát hành hiện tại. Tuy nhiên `work/backups/publish-*/server.properties`, Server `SETUP-NOTES.md` và launcher wrapper có shape địa chỉ mạng/đường dẫn vận hành/player-admin data. Server tree còn có nhiều bản resource pack alias và runtime/admin files.

Cần release allowlist nghiêm ngặt; không đưa `work/backups`, server notes, launch wrappers, `server.properties`, `ops.json`, `whitelist.json`, world/playerdata, logs, crash reports hay backup archives vào artifact công khai. Đây là rủi ro đóng gói/phân phối, không phải lý do xóa dữ liệu vận hành khỏi máy.

### P1 — ba bản resource pack cũ ở server

Server có ba alias/copy cũ: root, `resourcepack/`, và `resourcepacks/`; hai thế hệ hash khác nhau. Chỉ `resourcepack/` là path do helper hiện dùng. Sau khi xác minh consumer, nên chọn một hosted path duy nhất và quarantine/đánh dấu alias còn lại để không bị phục vụ nhầm.

### P2 — generated loose English resources

`minecraft/resources/.../en_us.lang` và `minecraft/groovy/assets/.../en_us.lang` vẫn là nguồn English do runtime sinh. Resource pack hiện overlay đủ các key đã review nên không phải blocker; cần periodic diff để bắt key mới sau mod/script update.
