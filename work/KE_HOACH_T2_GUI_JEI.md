# Kế hoạch dịch 6.447 nhãn GUI/JEI (nhóm T2)

Ngày lập: 2026-09-02. Số liệu lấy từ bản quét 223 mod JAR đang hoạt động.

## Vì sao nhóm này không thể dịch hàng loạt

Đây là nhóm nguy hiểm nhất trong bốn nhóm còn lại, dù câu ngắn nhất.

Đo được trên 6.351 dòng còn lại sau khi loại 96 dòng không thể dịch:

| Chỉ số | Giá trị | Hệ quả |
|---|---:|---|
| Độ dài trung vị | 11 ký tự | Không có ngữ cảnh trong chính chuỗi |
| Dòng ≤ 3 từ | 6.170 (97%) | Nghĩa phụ thuộc màn hình hiển thị |
| Key dạng tên | 1.771 | Có nguy cơ là tên registry |
| **Giá trị trùng PROTECTED_TERM** | **419** | **Dịch là hỏng tra cứu JEI** |

419 dòng đó là bằng chứng cứng: `container.abyssalcraft.crystallizer = Crystallizer`
trùng đúng tên khối `Crystallizer`. Dịch tiêu đề GUI mà không dịch tên khối thì
người chơi thấy hai tên khác nhau cho cùng một máy. Đây là lý do phải lọc trước,
không phải dịch trước rồi sửa sau.

## Nguyên tắc

1. **Lọc trước khi chia lô.** Lọc sau nghĩa là phải chia lại từ đầu.
2. **Một chuỗi English = một bản dịch.** 512 chuỗi lặp lại, phủ 1.577 dòng.
   Dịch `Enchantment` 17 lần theo 17 cách là lỗi nhất quán thấy rõ nhất trong game.
3. **Chia lô theo mod, không theo số thứ tự.** Nhãn cùng một mod xuất hiện cùng
   một màn hình; dịch lẫn lộn giữa các mod làm mất mạch thuật ngữ.
4. **Đông cứng manifest trước khi tích hợp**, giống cách đã làm với 500 key
   progression và 2.562 key T1.

## Giai đoạn

### Giai đoạn 0 — Lọc (bắt buộc, làm trước tiên)

Loại khỏi phạm vi:

- 419 dòng trùng `work/protected_terms.json` → giữ English, không bàn thêm.
- Trong 1.771 key dạng tên: đối chiếu từng key với `tile.*.name` / `item.*.name`
  của cùng mod. Trùng tên đăng ký → giữ English.
- Chuỗi chỉ có đơn vị, ký hiệu, token định dạng.

Ước tính còn lại thực sự cần dịch: **khoảng 5.500 dòng**.

Đầu ra: `work/approved_t2_corpus.json` — đông cứng, không sửa sau khi chốt.

### Giai đoạn 1 — Bảng thuật ngữ chung

Trước khi dịch dòng nào, chốt bản dịch cho 512 chuỗi lặp:

```
Enchantment → Phù Phép        None → Không
Potions → Thuốc               Empty → Trống
Ritual → Nghi Lễ              Corruptions → Tha Hoá
```

Bảng này là bắt buộc, không phải gợi ý. Mọi lô sau tra bảng trước khi tự dịch.

Đầu ra: `work/t2_glossary.json`.

### Giai đoạn 2 — Dịch theo lô

Chia theo mod, mỗi lô 120 dòng, ưu tiên theo tần suất người chơi mở giao diện:

| Đợt | Mod | Dòng | Lý do ưu tiên |
|---|---|---:|---|
| 1 | astralsorcery, botania, roots, bewitchment | 1.040 | Ma thuật — tiến trình chính |
| 2 | enderio, mekanism, industrialforegoing, extrautils2 | 718 | Máy móc dùng liên tục |
| 3 | tconstruct, plustic, enderutilities | 411 | Chế tác công cụ |
| 4 | journeymap, ftblib, bibliocraft, quark | 1.003 | Tiện ích, bản đồ |
| 5 | 68 mod còn lại | ~2.300 | Phần đuôi dài |

Mỗi lô phải qua kiểm tra tự động trước khi nhận:

- Số và thứ tự token `%s`, `%d`, `%n`, `%%` khớp tuyệt đối.
- Mã màu `§` khớp thứ tự.
- Không có xuống dòng thật trong giá trị.
- Chuẩn hoá NFC.
- Chuỗi English giống nhau phải cho ra bản dịch giống nhau.
- Không có dòng nào trùng `protected_terms.json`.

### Giai đoạn 3 — Đo bề rộng nút

Nhãn GUI bị cắt khi quá rộng, mà tiếng Việt thường dài hơn English 15–30%.
Chạy `tools/check_button_widths.py` sau khi tích hợp; nhãn tràn phải rút gọn,
không được để font tự co.

### Giai đoạn 4 — Tích hợp và kiểm tra

Theo đúng đường đã dùng cho T1: định tuyến key theo tiền tố registry, chạy
validator, build đủ bộ, chạy cả `unittest` lẫn `pytest`, rồi mới verify release.

## Khối lượng ước tính

| Giai đoạn | Ước tính |
|---|---|
| Lọc | 1 phiên |
| Bảng thuật ngữ | 1 phiên |
| Dịch 5 đợt | 5–7 phiên |
| Đo bề rộng + sửa | 1 phiên |
| Tích hợp + kiểm tra | 1 phiên |

## Rủi ro

- **Cao — dịch nhầm tên registry.** Giảm bằng giai đoạn 0 và guard PROTECTED_TERM
  trong `build_pack.py`.
- **Trung bình — nhãn tràn nút.** Giảm bằng giai đoạn 3.
- **Trung bình — thuật ngữ không nhất quán.** Giảm bằng giai đoạn 1.
- **Thấp — sai token định dạng.** Đã có kiểm tra tự động chặn.
