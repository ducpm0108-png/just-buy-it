# Just Buy It?

Công cụ đánh giá một khoản mua sắm trước khi xuống tiền: nhập giá, tình
hình tài chính và lý do bạn muốn món đồ, nhận lại một hoá đơn cho biết
món đồ **thật sự** tốn bao nhiêu, kèm một trong bốn kết luận —
`MUA ĐI`, `CHỜ ĐÃ`, `LÊN KẾ HOẠCH`, `ĐỪNG MUA`.

Đồ án môn Lập trình cho phân tích dữ liệu — Nhóm 20, Đại học Ngoại thương.

## Chạy thử

```bash
pip install -r requirements.txt
streamlit run app.py
```

Muốn xem trước tab Hồ sơ mà chưa dùng đủ lâu thì nạp dữ liệu mẫu — bấm
nút trong tab Hồ sơ, hoặc chạy:

```bash
python -m scripts.seed_demo
```

Chạy test:

```bash
pytest
```

Phần tính toán trong `src/` chỉ dùng thư viện chuẩn của Python, nên chạy
test không cần cài Streamlit.

## Cấu trúc

```
src/                  logic tính toán, không phụ thuộc giao diện
  models.py           các kiểu dữ liệu dùng chung
  metrics.py          chi phí mỗi lần dùng, số giờ đi làm, chi phí cơ hội
  scoring.py          mô hình tính điểm, ngưỡng, giá mục tiêu
  sale.py             phân tích đợt giảm giá có thời hạn
  calendar_vn.py      lịch giảm giá theo danh mục
  decay.py            thời gian bán rã của ham muốn
  db.py               lưu trữ bằng sqlite3
  personalize.py      thời gian chờ riêng, báo cáo hiệu chỉnh
tests/                172 test, chạy bằng pytest
scripts/
  seed_demo.py        nạp dữ liệu mẫu để demo
  send_reminders.py   gửi email nhắc chấm lại
docs/prototype.html   bản dựng thử giao diện, dùng làm bản thiết kế
app.py                giao diện Streamlit
```

Tách `src/` khỏi `app.py` theo đúng bố cục dự án trong bài giảng: notebook
và giao diện để *khám phá*, `src/` để *lưu code ổn định*. `app.py` không
chứa một công thức nào — chỉ đọc ô nhập, gọi hàm trong `src/`, vẽ kết quả.

## Cá nhân hoá mà không cần đăng nhập

Cá nhân hoá cần **danh tính** (biết dòng dữ liệu nào của ai), không cần
**xác thực** (chứng minh bạn đúng là người đó). Bảng `items` có cột
`profile`, người dùng chọn tên hồ sơ ở thanh bên, mọi truy vấn lọc theo
tên đó. Không mật khẩu, không session, không màn hình đăng nhập.

Trên nền đó có ba việc cá nhân hoá thật, cả ba đều tính từ dữ liệu người
dùng tự tạo ra — xem `src/personalize.py`:

**1. Thời gian chờ riêng.** Bảy ngày là con số tuỳ tiện. Người có ham muốn
nguội sau 3 ngày thì chờ 7 ngày là thừa; người nguội sau 30 ngày thì chờ 7
ngày chẳng nói lên điều gì. Thời gian chờ được đặt bằng đúng thời gian bán
rã đo được của chính người dùng, chặn trong khoảng 2–21 ngày — dưới 2 ngày
thì không kịp nguội, trên 21 ngày thì người dùng bỏ luôn công cụ, mà một
lời khuyên không ai theo là vô dụng.

**2. Trọng số riêng, lưu lại được.** Lưu trong bảng `settings` theo từng
hồ sơ, dạng khoá–giá trị. Đổi hồ sơ thì nạp lại bộ của hồ sơ đó. Nếu trọng
số mất khi đóng app thì công sức hiệu chỉnh thành vô nghĩa.

**3. Báo cáo hiệu chỉnh.** Chạy lại mô hình với trọng số hiện tại trên
chính những quyết định đã qua của người dùng, đối chiếu với kết quả thật,
rồi chỉ ra nên chỉnh gì. Chi tiết ở mục dưới.

Đây vẫn là danh tính chứ không phải xác thực — xem phần Giới hạn.

## Cách hoạt động

### Chỉ số quan trọng nhất: giá mỗi lần dùng

```
giá mỗi lần dùng = giá ÷ (số lần dùng mỗi tháng × số tháng sở hữu)
```

Cùng một chiếc tai nghe 4,5 triệu: dùng 20 lần mỗi tháng trong hai năm là
**9.375₫ một lần**; dùng 2 lần mỗi tháng là **93.750₫ một lần**. Cùng một
món đồ, cùng một cái giá, hai quyết định hoàn toàn khác nhau.

### Hai trục thay cho một điểm tổng

"Không đủ tiền" và "đang mua quá vội" là hai vấn đề khác nhau, cần hai
lời khuyên khác nhau. Gộp thành một điểm sẽ làm mất sự phân biệt đó, nên
mô hình chấm hai trục riêng rồi xếp vào ma trận:

|                    | Bốc đồng thấp   | Bốc đồng cao |
|--------------------|-----------------|--------------|
| **Áp lực thấp**    | MUA ĐI          | CHỜ ĐÃ       |
| **Áp lực cao**     | LÊN KẾ HOẠCH    | ĐỪNG MUA     |

Mỗi trục gộp từ nhiều yếu tố, mỗi yếu tố được quy về thang 0–1 bằng một
công thức ghi rõ trong `scoring.FACTORS`, rồi nhân trọng số. Điểm cuối là
trung bình có trọng số nhân 100. Trọng số không cần cộng lại bằng 100 —
chỉ tỷ lệ giữa chúng là quan trọng, và có test bảo đảm điều đó
(`test_diem_khong_doi_khi_nhan_doi_moi_trong_so`).

### Giá mục tiêu tìm bằng chia đôi khoảng

Cả bốn yếu tố áp lực tài chính đều tăng theo giá, nên điểm áp lực là hàm
đơn điệu không giảm theo giá. Nhờ tính đơn điệu đó, mức giá cao nhất còn
đạt ngưỡng tìm được bằng **chia đôi khoảng** (binary search) thay vì thử
từng giá:

```python
low, high = 0, price
for _ in range(40):
    mid = (low + high) / 2
    if strain_at(mid) < threshold:
        low = mid
    else:
        high = mid
```

Mỗi vòng thu hẹp khoảng tìm kiếm một nửa. Tính đơn điệu — điều kiện để
thuật toán này đúng — được kiểm tra bằng test
(`test_ap_luc_tang_don_dieu_theo_gia`).

### Thời gian bán rã của ham muốn

Khi kết quả là "chờ đã", món đồ được lưu kèm mức thèm muốn lúc đó. Đến
hạn, người dùng chấm lại **mà không thấy điểm cũ**. Từ các cặp điểm
trước–sau, ước tính số ngày để mức muốn giảm đi một nửa:

```
T = t × ln(2) ÷ -ln(v₁ / v₀)
```

Con số này vừa là kết quả phân tích cá nhân hoá cho người dùng, vừa được
dùng ngược lại để ước tính khả năng họ còn muốn món đồ sau một tuần — đầu
vào cho phần so sánh thiệt hại kỳ vọng khi món đồ đang giảm giá.

### Phát hiện giảm giá ảo

Nếu người dùng nhập giá thấp nhất 30 ngày qua, webapp so giá sale với mức
đó. Giá sale **không** thấp hơn đáy 30 ngày là dấu hiệu của chiêu nâng giá
gốc lên rồi giảm lại.

## Báo cáo hiệu chỉnh: đo thay vì đoán

Điểm yếu lớn nhất của một mô hình có trọng số là câu hỏi "trọng số đâu ra".
Thay vì tự nhận là đúng, công cụ tự đo mình trên dữ liệu người dùng.

**Gán nhãn kết quả.** Một quyết định được coi là đã biết kết quả khi người
dùng đã chấm lại **và** đã đánh dấu đã mua hoặc đã bỏ qua. Bốn nhãn:

| Trạng thái | Lần chấm gần nhất | Nhãn |
|---|---|---|
| đã mua | ≥ 6/10 | Mua và vẫn thấy đáng |
| đã mua | ≤ 4/10 | Mua rồi hết muốn |
| đã bỏ qua | ≤ 4/10 | Bỏ qua và không tiếc |
| đã bỏ qua | ≥ 6/10 | Bỏ qua nhưng vẫn muốn |

Điểm 5/10 bị bỏ qua: không rõ là còn muốn hay hết muốn.

**Chạy lại mô hình.** `decision_context()` dựng lại đầy đủ bối cảnh lúc ra
quyết định — giá, hoàn cảnh tài chính, mức thèm muốn **lần chấm đầu tiên**,
số giờ còn lại của đợt sale tại thời điểm đó, và cả giờ trong ngày (để yếu
tố "giờ khuya" đúng). Rồi chấm lại bằng trọng số **hiện tại**: câu hỏi cần
trả lời là "bộ cài đặt bây giờ có bắt được món tôi đã mua hớ không", không
phải "hồi đó tôi cài gì".

**Ma trận nhầm lẫn.** Hai loại lỗi có hậu quả khác nhau nên không gộp:

|                          | Hoá ra đáng | Hoá ra không đáng |
|--------------------------|-------------|-------------------|
| Công cụ khuyên tiến tới  | đúng        | **khuyên mua mà hối** |
| Công cụ khuyên dừng      | khuyên dừng mà vẫn muốn | đúng |

"Khuyên mua mà hối" là lỗi nặng hơn — đúng việc mà công cụ này sinh ra để
làm. "Khuyên dừng mà vẫn muốn" gây khó chịu nhưng không mất tiền.

**Yếu tố nào mang thông tin.** Với mỗi yếu tố, tính giá trị trung bình trên
nhóm mua hớ và trên nhóm mua đúng, rồi lấy chênh lệch. Chênh lệch lớn thì
yếu tố đó phân biệt tốt, nên tăng trọng số; gần 0 thì với người này nó
không nói lên gì, nên hạ xuống. Đây là hiệu số trung bình — cách đo đơn
giản nhất có ý nghĩa, không cần thư viện ngoài. Với vài trăm quyết định thì
bước tiếp theo là hồi quy logistic, nhưng vài chục thì hiệu số trung bình
đã đủ để biết nên chỉnh thanh nào.

Công cụ **không bao giờ tự đổi trọng số**, chỉ nói nên chỉnh gì. Và dưới 5
quyết định thì nói thẳng là chưa đủ dữ liệu thay vì đưa ra tỷ lệ nhiễu.

Một lựa chọn có thể bàn, nên nêu khi trình bày: `LÊN KẾ HOẠCH` được xếp vào
nhóm "tiến tới", vì nội dung của nó là khẳng định món đồ đáng mua, chỉ hoãn
vì chưa đủ tiền. Xếp nó vào nhóm "dừng" cũng có lý và sẽ ra tỷ lệ khác.

## Hiệu chỉnh trọng số bằng tay

Bộ trọng số mặc định là điểm xuất phát, không phải chân lý. Cách hiệu
chỉnh cho riêng mình:

1. Chọn một bộ dựng sẵn gần hoàn cảnh của bạn nhất — `student`,
   `saver` hoặc `stable` trong `scoring.PRESETS`.
2. Nghĩ ra ba món đã mua trước đây: một món rất đáng tiền, một món bạn
   tiếc, một món ở giữa. Nhập lại từng món với hoàn cảnh lúc mua.
3. Xem kết luận. Món đáng tiền nên ra `MUA ĐI` hoặc `LÊN KẾ HOẠCH`; món
   đáng tiếc nên ra `CHỜ ĐÃ` hoặc `ĐỪNG MUA`.
4. Nếu sai, xem phần đóng góp của từng yếu tố (`Score.top_parts`) để biết
   yếu tố nào đang kéo điểm, rồi chỉnh trọng số đó.
5. Chỉ chỉnh ngưỡng sau khi trọng số đã ổn, mỗi lần 5 điểm.

## Giới hạn đã biết

- **Webapp không tự đọc giá từ các sàn.** Giá là do người dùng tự ghi.
  Lấy giá tự động cần vượt cơ chế chống bot của sàn, thuộc kế hoạch dài hạn.
- **Lịch giảm giá là dữ liệu tham khảo**, gom từ các đợt sale định kỳ,
  không phải dự báo giá. Chưa tính các đợt quanh Tết vì Tết theo lịch âm.
- **Mô hình suy giảm ham muốn giả định hàm mũ.** Đây là một giả định đơn
  giản hoá; với dữ liệu thật hoàn toàn có thể kiểm tra xem hàm mũ có khớp
  hơn một đường thẳng hay không.
- **Không có xác thực.** Tên hồ sơ chỉ để tách dữ liệu; ai cũng chọn được
  hồ sơ của người khác và xem được thu nhập, tiền tiết kiệm của họ. Triển
  khai thật cần đăng nhập, vì đây là thông tin cá nhân. Với đồ án chạy
  trên một máy thì đổi lại được sự đơn giản.
- Đây là công cụ để nhìn lại thói quen chi tiêu, **không phải lời khuyên
  tài chính**.

## Kế hoạch

| Trạng thái | Nội dung |
|---|---|
| Đã hoàn thiện | Mô hình tính điểm hai trục, hoá đơn chi phí, giá mục tiêu, phát hiện giảm giá ảo, lịch sale theo danh mục, nhật ký hoãn mua, thời gian bán rã, so sánh mục tiêu thay thế, lưu dữ liệu bằng sqlite3, cá nhân hoá theo hồ sơ, báo cáo hiệu chỉnh, script gửi email nhắc |
| Ngắn hạn | Đưa database lên host để nhắc tự động hằng ngày |
| Dài hạn | Tự động lấy giá từ sàn, đăng nhập thật, thống kê chéo nhiều người dùng, thay hiệu số trung bình bằng hồi quy logistic khi đủ dữ liệu |

## Gửi email nhắc

```bash
# Xem trước, không gửi gì
python -m scripts.send_reminders --dry-run

# Gửi thật
export JBI_SMTP_USER="ban@gmail.com"
export JBI_SMTP_PASS="app password 16 ký tự"
python -m scripts.send_reminders
```

Gmail cần **app password** (bật xác thực hai bước rồi tạo riêng), không
phải mật khẩu tài khoản. Địa chỉ nhận đặt trong thanh bên của app.

Email cố tình **không nhắc lại điểm thèm muốn cũ** — cả cơ chế đo độ nguội
dựa vào việc người dùng chấm lại mà không bị điểm cũ neo vào. Có test bảo
đảm điều này (`test_email_khong_nhac_lai_diem_cu`).

Script hiện chạy thủ công. Tự động hằng ngày cần database nằm trên host để
máy khác đọc được — đó là việc duy nhất còn lại trong kế hoạch ngắn hạn.

## Lưu ý khi làm việc trên repo này

File `data/*.db` chứa thu nhập, tiền tiết kiệm và chi phí cố định của
người dùng. Đã có trong `.gitignore` — đừng commit nó. App password của
Gmail dùng cho script gửi mail cũng vậy: để trong `.env` hoặc
`.streamlit/secrets.toml`, không viết thẳng vào code.
