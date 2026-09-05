# DJ2 Việt hóa 2.23.4

Bản Việt hóa cho **Divine Journey 2 v2.23.4** (Minecraft 1.12.2).

Dịch nhiệm vụ, sách hướng dẫn, mô tả vật phẩm và giao diện. Tên vật phẩm/mod
giữ nguyên tiếng Anh để tra JEI và wiki.

Không sửa mod JAR, công thức, nhiệm vụ hay tiến trình chơi. Chỉ thay chữ.

---

## Tải về

**Người chơi** — tải `DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip`

Giải nén toàn bộ vào thư mục gốc instance DJ2 (nơi có `mods/`, `config/`).
Mở game là xong — ngôn ngữ, resource pack và font đã tự bật.

**Chủ server** — tải thêm `DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip`

Giải nén vào thư mục server, đọc `HUONG_DAN_SERVER.txt` bên trong.

**Chỉ muốn resource pack** — tải `DJ2_Viet_Hoa_2.23.4.zip`

Bỏ vào `resourcepacks/` rồi bật trong game. Bản này thiếu phần cấu hình
giao diện chính và font mặc định, nên khuyến nghị dùng gói Client ở trên.

---

## Yêu cầu

Vào **Options → Language** chọn **Tiếng Việt (Việt Nam)**.

Bật **Force Unicode Font: ON** — không bật thì chữ có dấu hiển thị sai.
Gói Client đã đặt sẵn hai mục này.

---

## Có gì trong bản này

- **22.767 dòng** văn bản đã dịch, trải trên **169 mod**
- **581 trang** sách Patchouli
- **3.532 dòng** nhiệm vụ BetterQuesting
- Font Việt vẽ riêng, dấu rõ ở cỡ chữ nhỏ
- Mẹo màn hình chờ, bảng thông tin khi ngắm khối, giao diện JEI
- Trọn bộ Tinkers' Construct: mô tả công cụ, modifier, vật liệu
- **26 tên cúp** thành tựu và các script hiển thị trong JEI

---

## Đã dịch được bao nhiêu

Đo bằng cách quét toàn bộ **223 file mod** trong instance, lấy hết chuỗi
tiếng Anh gốc rồi so với nội dung gói này.

| Hạng mục | Số dòng |
|---|---:|
| Tổng chuỗi trong tất cả mod | 52.434 |
| Tên vật phẩm/khối/mob — **cố ý giữ tiếng Anh** | 22.536 |
| Tài liệu chỉ dành cho lập trình viên | 2.772 |
| Chuỗi rỗng | 51 |
| **Phần thực sự cần dịch** | **27.075** |
| Đã dịch | 22.767 |
| **Tỷ lệ** | **84,1%** |

Phần đã dịch được chọn theo mức độ người chơi hay gặp: toàn bộ nhiệm vụ,
sách hướng dẫn, tiến trình chơi chính và giao diện dùng thường xuyên.

Những bản trước ghi "91,1%". Con số đó đo trên phần văn bản đã đưa vào gói,
không phải trên toàn bộ chữ của 223 mod, nên đã nói quá độ phủ thật. Bảng
trên là cách đo đúng, sinh ra từ `tools/measure_coverage.py`.

### Còn lại chưa dịch

| Nhóm | Số dòng | Gặp khi nào |
|---|---:|---|
| Tooltip, tin nhắn, thành tựu | 0 | Chơi bình thường |
| Nhãn giao diện, JEI, phím tắt | 270 | Mở giao diện mod |
| Màn hình cấu hình, lệnh, công cụ quản trị | 189 | Chủ yếu cho chủ server |
| Chuỗi lẻ chưa phân nhóm | 563 | Rải rác |

Ngoài bốn nhóm trên còn **2.772 dòng** chỉ dành cho lập trình viên —
`groovyscript` (tài liệu API) và `chisel` (tên biến thể khối). Nhóm này không
xuất hiện trong lối chơi bình thường và không nằm trong kế hoạch dịch.

Thêm **3.286 dòng** hiện để nguyên tiếng Anh trong gói. Đợt rà soát gần nhất
đã soi toàn bộ 3.286 dòng loại này: 1.756 dòng được đọc thủ công theo ngữ cảnh
từng mod, tìm ra 6 dòng bỏ sót thật và đã sửa. Sáu dòng gần nhất được bổ sung
vào nhóm này là mã locale, tên mũi tên hiệu ứng và tên Aspect Thaumcraft, đều
thuộc diện giữ tiếng Anh. Số còn lại là danh từ riêng, tên
phím, đơn vị hoặc thuật ngữ kỹ thuật giữ tiếng Anh có chủ đích.

---

## Vì sao vẫn còn tiếng Anh

Một phần giữ nguyên **có chủ ý**:

- **Tên vật phẩm, mod, khối** — để tra JEI và wiki. Dịch "Big Soul Item Filter"
  thành tiếng Việt là bạn không tìm được nó trong JEI nữa.
- **Cú pháp lệnh** như `/bloodmagic network syphon` — gõ nguyên văn mới chạy.
- **Trang mật mã trong Codex Infernalis** — đó là câu đố của modpack.

Phần còn lại là chưa dịch tới, không phải cố ý. Bảng ở trên nói rõ nhóm nào.

---

## Kiểm tra file tải về

So với `SHA256SUMS.txt` kèm theo:

```
certutil -hashfile DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip SHA256
```

---

## Báo lỗi

Gặp chữ lỗi font, dịch sai nghĩa hay chỗ chưa dịch — chụp màn hình kèm tên
vật phẩm/nhiệm vụ. Sửa từng điểm nhanh hơn nhiều so với rà lại toàn bộ.

Bản này **không kèm ảnh so sánh** — ảnh của các bản trước đã cũ so với nội
dung hiện tại, nên gỡ đi thay vì để lại ảnh không còn đúng.
