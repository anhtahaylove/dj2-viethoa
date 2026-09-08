# DJ2 Việt hóa 2.23.4

Bản Việt hóa cho **Divine Journey 2 v2.23.4** (Minecraft 1.12.2).

Bản này ngoài phần dịch còn **sửa một lỗi công thức nung** khiến quặng đào ở
tầng đá đặc biệt không nung ra thỏi được.

---

## Tải file nào

| Bạn là | Tải file | Dung lượng |
|---|---|---:|
| **Người chơi** | `DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip` | 1,82 MB |
| **Chủ server** | thêm `DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip` | 1,76 MB |
| Chỉ muốn resource pack | `DJ2_Viet_Hoa_2.23.4.zip` | 1,85 MB |

### Cách cài cho người chơi

Giải nén toàn bộ gói Client vào thư mục gốc instance DJ2 — chỗ có sẵn `mods/`
và `config/`. Mở game là xong: ngôn ngữ, resource pack và font đã bật sẵn.

Nếu bạn tự đổi cài đặt trước đó, vào **Options → Language** chọn
**Tiếng Việt (Việt Nam)** và bật **Force Unicode Font: ON**. Không bật font
thì chữ có dấu sẽ hiển thị sai.

---

## Sửa lỗi: quặng không nung được

### Bạn gặp lỗi này nếu

Đào được quặng đồng, thiếc, nickel hoặc nhôm ở vùng đá granite, diorite,
đá phiến, đá vôi… bỏ vào lò nung thì **lò không chạy**, dù quặng bình thường
vẫn nung tốt.

### Vì sao

Modpack dùng mod Underground Biomes để đổi đá thường thành nhiều loại đá thật
(granite, andesite, đá vôi…). Khi đổi đá, mod tạo luôn phiên bản quặng tương
ứng cho từng loại đá, rồi sao chép công thức nung từ quặng gốc sang.

Vấn đề nằm ở **thứ tự nạp**: Underground Biomes sao chép công thức trước khi
Thermal Foundation kịp đăng ký công thức nung của quặng gốc. Không thấy gì để
sao chép, mod bỏ qua trong im lặng — không báo lỗi, không ghi log. Kết quả là
27 biến thể quặng ra đời mà không có công thức nung nào.

Lỗi này có sẵn trong modpack gốc, không phải do bản Việt hóa gây ra.

### Đã sửa thế nào

Thêm một script CraftTweaker đăng ký lại đúng 27 công thức nung còn thiếu,
cho 4 kim loại:

| Kim loại | Số biến thể được sửa |
|---|---:|
| Copper | 9 |
| Tin | 6 |
| Nickel | 6 |
| Aluminum | 6 |

Script chỉ **thêm** công thức nung đã thiếu. Không sửa mod, không đổi tỷ lệ
sinh quặng, không đụng vào nhiệm vụ hay tiến trình chơi.

### Bạn cần làm gì

Không cần tạo thế giới mới. Công thức được đăng ký lúc game khởi động, nên
quặng cũ đang nằm trong rương cũng nung được ngay sau khi cài và vào lại game.

Chủ server cài gói Server Overlay thì cả server được sửa, người chơi không cần
làm gì thêm.

### Đã kiểm chứng

Bật server thật, dùng lệnh `/ct recipes furnace` lấy toàn bộ 1.191 công thức
nung đang chạy trong game rồi đối chiếu: **27/27 biến thể có công thức, và cả
27 đều ra đúng thỏi kim loại**.

Đã rà thêm các hệ thống khác — ore dictionary, 13.766 công thức bàn chế tạo,
máy nghiền/lò hồ quang — **không có chỗ nào hỏng tương tự**. Máy móc tra quặng
qua ore dictionary, mà phần đó Underground Biomes sao chép thành công, nên chỉ
riêng lò nung bị ảnh hưởng.

Các quặng khác đã kiểm và **không cần sửa**: Silver và Lead vốn đã có công
thức đầy đủ; Mithril và Redstone của Thermal Foundation không sinh ra trong
thế giới của modpack này.

---

## Phần dịch

- **22.783 dòng** đã dịch, trải trên **169 mod**
- **581 trang** sách Patchouli
- **3.532 dòng** nhiệm vụ BetterQuesting
- Font Việt vẽ riêng, dấu rõ ở cỡ chữ nhỏ
- Mẹo màn hình chờ, bảng thông tin khi ngắm khối, giao diện JEI
- Trọn bộ Tinkers' Construct: mô tả công cụ, modifier, vật liệu

Độ phủ **84,1%** trên 27.075 dòng thực sự cần dịch.

### Vì sao vẫn còn tiếng Anh

Giữ nguyên **có chủ ý**, không phải dịch sót:

- **Tên vật phẩm, khối, máy** — để tra JEI và wiki. Dịch tên ra tiếng Việt là
  bạn mất khả năng tìm kiếm.
- **Tên phép, nghi lễ, chòm sao** — trùng với tên trong hướng dẫn tiếng Anh.
- **Cú pháp lệnh** — phải gõ đúng nguyên văn mới chạy.

Phần mô tả, hướng dẫn, nhiệm vụ và giao diện quanh chúng đều đã dịch.

Chi tiết đầy đủ về cách đo độ phủ và những phần chưa dịch nằm trong
`DOC_DAU_TIEN.md` kèm theo gói.

---

## Kiểm tra file tải về

Đối chiếu SHA-256 với `SHA256SUMS.txt` trong cùng thư mục:

```
12ffe68566d824119773030553ea5671ee7455d75350b6aed2ebf91e015518f8  DJ2_Viet_Hoa_2.23.4.zip
726164de11929358d6dfc60831db33a805a91c5783c517db0a39508d1228cf52  DJ2_Viet_Hoa_2.23.4_Client_Extract_To_Instance.zip
c159b96d8cf96abb2c0b4838cdb91524899226ee60df95115a87190c5f8e99db  DJ2_Viet_Hoa_2.23.4_Server_Localization_Overlay.zip
```

---

## Gỡ ra

Xóa `resourcepacks/DJ2_Viet_Hoa_2.23.4.zip` và các file script đã thêm trong
`scripts/Unique/`. Thế giới và tiến trình chơi không bị ảnh hưởng.
