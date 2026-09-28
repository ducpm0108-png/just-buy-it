# Just Buy It?

Công cụ đánh giá một khoản mua sắm trước khi xuống tiền: nhập giá, tình
hình tài chính và lý do bạn muốn món đồ, nhận lại một hoá đơn cho biết
món đồ **thật sự** tốn bao nhiêu, kèm một trong bốn kết luận —
`MUA ĐI`, `CHỜ ĐÃ`, `LÊN KẾ HOẠCH`, `ĐỪNG MUA`.

Đồ án môn Lập trình cho phân tích dữ liệu — Nhóm 20, Đại học Ngoại thương.

## Chạy thử

Bản chính thức là một trang HTML cộng một API Python. Cùng một lệnh chạy
cả hai, trên cùng một cổng — giống hệt lúc deploy:

```bash
pip install -r requirements-dev.txt
uvicorn api.main:app --reload
```

Rồi mở http://localhost:8000. Tài liệu API tự sinh ở
http://localhost:8000/docs — bấm thử từng endpoint được, không cần viết
lệnh curl nào.

Muốn xem trước tab Hồ sơ mà chưa dùng đủ lâu thì bấm **Nạp dữ liệu mẫu**
trong tab Hồ sơ.

Chạy test:

```bash
pytest
```

Phần tính toán trong `src/` chỉ dùng thư viện chuẩn của Python. Test của
`src/` chạy được mà không cần cài gì thêm; test của API cần `fastapi` và
tự bỏ qua nếu thiếu.

Giao diện Streamlit cũ vẫn chạy được, và giữ lại có ích: hai giao diện gọi
cùng một `src/`, nên nếu chúng cho ra hai con số khác nhau thì đó là lỗi và
biết ngay.

```bash
pip install -r requirements-streamlit.txt
streamlit run app.py
```

## Cấu trúc

```
src/                  logic tính toán, không phụ thuộc giao diện
  models.py           các kiểu dữ liệu dùng chung
  metrics.py          chi phí mỗi lần dùng, số giờ đi làm, chi phí cơ hội
  scoring.py          mô hình tính điểm, ngưỡng, giá mục tiêu
  sale.py             phân tích đợt giảm giá có thời hạn
  calendar_vn.py      lịch giảm giá theo danh mục
  decay.py            thời gian bán rã của ham muốn
  db.py               lưu trữ bằng sqlite3 (chỉ bản Streamlit dùng)
  personalize.py      thời gian chờ riêng, báo cáo hiệu chỉnh
  style.py            lớp trang trí cho Streamlit
api/main.py           API HTTP: JSON vào, gọi src/, JSON ra
public/index.html     giao diện — không chứa một công thức nào
tests/                388 test, chạy bằng pytest
scripts/
  seed_demo.py        nạp dữ liệu mẫu để demo
  send_reminders.py   gửi email nhắc chấm lại
app.py                giao diện Streamlit cũ, giữ để đối chiếu
vercel.json           cấu hình deploy
pyproject.toml        phụ thuộc + entrypoint cho Vercel
uv.lock               khoá phiên bản, có commit để build nhanh
```

Bố cục theo đúng bài giảng: notebook và giao diện để *khám phá*, `src/` để
*lưu code ổn định*. Cả `api/main.py` lẫn `app.py` đều không chứa công thức
nào — chỉ đọc đầu vào, gọi `src/`, trả kết quả.

## Kiến trúc: một nguồn sự thật cho mọi con số

Dự án từng có **hai bản của mỗi công thức**: một trong `src/scoring.py`
cho bản Streamlit, một viết bằng JavaScript trong trang HTML. Hai bản là
hai nguồn sự thật, và khi chúng lệch nhau thì không có cách nào biết bản
nào đúng.

Giờ chỉ còn một:

```
public/index.html          api/main.py              src/
  đọc ô nhập        ──►   JSON → dataclass    ──►   mọi phép tính
  vẽ kết quả        ◄──   dataclass → JSON    ◄──   (thư viện chuẩn)
```

Trang không tính gì cả — kiểm chứng được bằng `grep`: trong JavaScript
không còn `Math.pow`, không còn hằng số `1.06` của lãi kép, không còn
`/ 176` của số giờ làm mỗi tháng.

Trang còn nạp cả **từ vựng** từ Python: nhãn danh mục, nhãn nguồn biết đến,
tên và công thức của từng yếu tố đều lấy qua `GET /api/meta`. Sửa một nhãn
trong `src/scoring.py` là giao diện đổi theo, không phải sửa hai nơi.

Chỗ yếu của cách tách này: đổi tên một trường bên Python mà quên sửa trang
thì **trang không báo lỗi** — nó chỉ hiện `—` hoặc `undefined`, và không ai
biết cho tới lúc trình bày. Nên hợp đồng giữa hai nửa được viết thành danh
sách và rà bằng test: `TRANG_DOC_EVALUATE`, `TRANG_DOC_PROFILE`,
`TRANG_DOC_META` trong `tests/test_api.py` liệt kê từng đường dẫn trang
thật sự đọc, và mỗi đường dẫn là một test.

### Ba endpoint

| Endpoint | Việc |
|---|---|
| `GET /api/meta` | Từ vựng giao diện: danh mục, nguồn, các yếu tố, bộ trọng số có sẵn |
| `POST /api/evaluate` | Toàn bộ nội dung tờ hoá đơn, một lần gọi |
| `POST /api/profile` | Hồ sơ mua sắm, tính từ các món client gửi lên |

Một endpoint cho cả tờ hoá đơn là có chủ ý: hoá đơn cập nhật theo từng lần
gõ, nên mỗi lần chỉ nên có đúng một vòng đi về. Trang gom 180ms rồi mới
gọi, và đánh số thứ tự để phản hồi về muộn của lần gõ cũ không ghi đè kết
quả của lần gõ mới.

### Không có cơ sở dữ liệu

API **không giữ trạng thái**. Dữ liệu người dùng nằm trong trình duyệt của
họ; endpoint nào cần lịch sử thì nhận lịch sử kèm trong request.

Đây không phải cách làm cho tiện. Trang là công khai và không có đăng nhập,
nên nếu dữ liệu nằm trên server thì ai mở link cũng đọc được thu nhập và
số tiền tiết kiệm của người khác. Không lưu gì thì không có gì để rò rỉ —
và nhờ vậy `allow_origins=["*"]` cũng an toàn, vì API không cho người gọi
bất cứ thứ gì mà họ chưa tự mang tới.

Đổi lại, API công khai thì ai cũng gửi được đầu vào lớn bao nhiêu cũng
được. Nên kích cỡ bị chặn ngay ở lớp kiểm tra: tối đa 2.000 món, 500 lần
chấm cho một món, 50 mục tiêu. Các mức này rộng hơn nhu cầu thật rất nhiều
nên không chặn ai, nhưng chúng biến "gửi 100.000 món" từ *hàm hết thời
gian, app trông như treo* thành một lỗi 422 có lời giải thích.

### Biên JSON

Python có `inf`, JSON thì không. `inf` xuất hiện thật: giá mỗi lần dùng là
vô hạn khi người dùng để số lần dùng bằng 0. Nếu để nó đi ra nguyên dạng,
`json.dumps` in ra chữ `Infinity`, và `JSON.parse` của trình duyệt coi đó
là lỗi cú pháp rồi ném — mất cả phản hồi, không phải sai một ô.

Nên `api/main.py` đổi mọi số không hữu hạn thành `null` ở đúng một chỗ, và
trang hiển thị `null` thành `∞` hoặc `—`. `null` nghĩa là "không tính
được", khác hẳn `0`; lẫn hai thứ thì hoá đơn báo món đồ miễn phí, tức là
sai theo hướng nguy hiểm nhất. Có bốn test chặn việc này, mỗi test một
cách làm cho phép tính ra vô hạn.

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

Có ở cả hai giao diện, cùng một `src/personalize.py`: tab **Hồ sơ** của bản
web và của bản Streamlit.


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

## Xuất và nhập dữ liệu

Tab **Hồ sơ** có **Tải dữ liệu về** (xuất JSON) và **Nạp dữ liệu từ file**.
Nạp có hai chế độ: thêm vào dữ liệu hiện có, hoặc thay thế toàn bộ.

Đây là cách giải quyết chuyện bản online không giữ được dữ liệu, thay vì
dựng database trên host. Lý do chọn hướng này: đưa database lên host mà app
vẫn công khai và không có xác thực thì **mọi người dùng chung một database
và ai cũng mở được hồ sơ của người khác** để xem thu nhập, tiền tiết kiệm.
Hai việc đó phải làm cùng nhau, nên cả hai nằm ở kế hoạch dài hạn. Xuất và
nhập file giữ dữ liệu trong tay người dùng, không cần tài khoản, và không
thêm chỗ nào có thể sập lúc demo.

File xuất ra có `version` để sau này lược đồ đổi thì vẫn đọc được file cũ,
và chỉ chứa **một hồ sơ** chứ không phải cả database. Phần nhập kiểm tra
định dạng trước, lọc bỏ những cột không có trong lược đồ, và bỏ qua dòng
rác thay vì làm sập cả lần nhập — file do người dùng tự chọn nên không tin
được ngay.

### File có chứa số liệu tài chính, và đó là một đánh đổi có chủ ý

Mỗi món lưu kèm **hoàn cảnh lúc quyết định**: số lần dùng, thời gian muốn,
nguồn biết đến, và cả thu nhập, chi phí cố định, số tiền đang có *vào đúng
lúc đó*.

Cần vậy để báo cáo hiệu chỉnh chạy được. Chạy lại mô hình bằng tình hình
tài chính *hôm nay* cho một quyết định sáu tháng trước thì điểm áp lực tài
chính vô nghĩa — mà kết quả vẫn trông như thật, nên sai kiểu đó tệ hơn là
không chạy lại. Có test bắt đúng chỗ này: cùng một món, chỉ khác thu nhập
lúc quyết định, phải ra điểm áp lực khác nhau.

Hệ quả: file xuất ra riêng tư hơn một danh sách mua sắm thường. Hướng dẫn
nhập/xuất trong app nói thẳng điều này, và câu cũ ("file không chứa thu
nhập") đã được sửa — để nguyên một câu hứa về quyền riêng tư đã thành sai
thì tệ hơn không hứa gì.

Món ghi trước khi tính năng này có thì **không có** hoàn cảnh. Chúng bị bỏ
qua khi chạy lại, và app nói rõ đã bỏ qua bao nhiêu món — thay vì để người
dùng tưởng mô hình đã xét hết mọi quyết định của họ.

## Giao diện

Bảng màu dùng chung cho cả hai giao diện (`public/index.html` và
`.streamlit/config.toml`), theo ẩn dụ tờ hoá đơn đặt trên mặt bàn: vùng nội
dung là giấy, thanh bên là mặt bàn, màu nhấn là màu mực con dấu. Mỗi chế độ
sáng/tối có bảng màu riêng.

Khác nhau ở chỗ **ai quyết định chế độ**. Trang web tự có công tắc
Tự động/Sáng/Tối, nên nó biết chắc mình đang vẽ chế độ nào và gọi tên màu
theo chế độ là an toàn. Bản Streamlit thì không biết — xem phần cuối mục
này.

Hai thanh điểm đổi màu theo **trạng thái**: dưới ngưỡng xanh, vượt ngưỡng
đỏ, kèm vạch dọc đánh dấu ngưỡng. Vạch đó là thứ làm con số có nghĩa — 47
tự nó không nói gì, nhưng "47 với vạch ngưỡng ở 40" thì thấy ngay là đã
vượt. Hai màu này đạt tương phản từ 3:1 trên cả nền giấy sáng và nền giấy
tối nên không cần đổi theo chế độ.

`toolbarMode = "minimal"` ẩn thanh công cụ của nhà phát triển (nút Edit,
biểu tượng GitHub) để người xem chỉ thao tác với chính trang web. Quản lý
app vẫn làm ở share.streamlit.io.

### Hướng dẫn nhập/xuất dữ liệu

Mục *Dữ liệu của bạn* ở tab Hồ sơ có một thẻ hướng dẫn hiện **một lần cho
mỗi hồ sơ**, và một nút **“?”** mở lại bất cứ lúc nào dưới dạng hộp thoại.
Nội dung nằm trong một hàm `data_help_body()` dùng chung cho cả ba chỗ hiện
(thẻ lần đầu, hộp thoại, bản dự phòng cho Streamlit cũ), nên không có hai
bản hướng dẫn lệch nhau.

Cờ “đã xem” lưu trong bảng `settings` theo từng hồ sơ nên tải lại trang vẫn
nhớ — khác với `st.session_state` vốn mất khi refresh.

Thẻ là **tại chỗ chứ không phải hộp thoại tự bật**, vì Streamlit chạy thân
của *mọi* tab ở mỗi lần vẽ lại: phía Python không có cách nào biết người
dùng vừa bấm sang tab Hồ sơ. Hộp thoại đặt trong tab đó sẽ bật ngay lúc mới
mở trang, trong khi người dùng đang nhìn tab Đánh giá.

Hướng dẫn nói ra hai hành vi không hiển nhiên của `db.import_profile`, và
`tests/test_huong_dan_du_lieu.py` rà để hướng dẫn không nói lệch với mã:

- Dữ liệu vào **hồ sơ đang chọn ở thanh bên**, không phải hồ sơ ghi trong file.
- **Cả hai cách nạp đều ghi đè** bộ trọng số và email của hồ sơ đang chọn,
  vì vòng lặp ghi `settings` nằm ngoài nhánh `replace`.

### Vì sao lớp trang trí không gọi tên màu nào

Chỗ này vỡ hai lần trên bản deploy, và hai lần đều cùng một nguyên nhân:
**đoán xem Streamlit đang vẽ chế độ nào.**

| Lần | Cách đoán | Kết quả |
|---|---|---|
| 1 | `st.context.theme.type` trong Python | Trả về `"light"` khi Streamlit vẽ tối → nền sáng chồng dưới chữ kem, **chữ biến mất** |
| 2 | `prefers-color-scheme` trong CSS | Đọc thiết lập của máy, không phải của Streamlit → máy tối mà Streamlit vẽ sáng thì **hoá đơn hoá đen giữa trang giấy trắng** |

Tài liệu Streamlit có nói `st.context.theme.type` là giá trị *suy ra từ màu
nền* và "có thể sai trong lúc đổi giao diện" — lần một là lỗi đọc mà vẫn
dùng. Lần hai đổi nguồn đoán chứ không bỏ việc đoán, nên lỗi quay lại theo
chiều ngược.

Cách sửa thật là bỏ câu hỏi. Mọi màu **bề mặt** trong `src/style.py` suy ra
từ `currentColor` — màu chữ mà chính Streamlit đã đặt — bằng `color-mix`:

```css
--jbi-sheet: color-mix(in srgb, currentColor 5%, transparent);
```

Biến CSS chưa đăng ký được thay thế dạng *văn bản* rồi mới tính giá trị tại
phần tử dùng nó, nên `currentColor` ở đây tính đúng ở tờ hoá đơn. Chế độ
sáng cho bề mặt sẫm hơn nền, chế độ tối cho bề mặt sáng hơn nền, và không
có nguồn sự thật thứ hai để mà lệch.

Kiểm chứng bằng `grep`: `src/style.py` không còn một mã màu hex nào và
không còn media query chế độ nào; hai test chặn việc thêm lại. Đo trong
trình duyệt thật ở cả bốn tổ hợp (Streamlit sáng/tối × máy sáng/tối), tương
phản chữ trên giấy là 11,6–14,8:1.

Hai chỗ **vẫn** gọi tên màu, có lý do:

- `.streamlit/config.toml` — ở đó mỗi chế độ có mục riêng và **Streamlit tự
  chọn** đúng mục, nên không ai phải đoán. Màu trắng của ô nhập đặt ở đây.
- `style.STAMP_COLORS` — bốn màu con dấu **mang nghĩa** (xanh là mua, đỏ là
  đừng) nên phải là màu thật. Đánh đổi là chúng phải đạt tương phản trên cả
  hai mặt giấy, và 4,5:1 cả hai là bất khả (muốn đạt trên giấy sáng thì độ
  sáng màu phải ≤ 0,160, trên giấy tối thì ≥ 0,280 — hai khoảng rời nhau).
  Nên đích là 3:1 cho chữ lớn in đậm; bốn màu hiện tại đạt 3,4–3,8:1 và
  `test_mau_con_dau_doc_duoc_tren_ca_hai_mat_giay` tính lại từ bảng màu
  trong config.toml mỗi lần chạy.

## Deploy lên Vercel

Vercel chạy được Python thật (3.12/3.13/3.14) và tự nhận FastAPI, nên cả
trang lẫn API nằm trong một dự án, cùng một tên miền.

1. vercel.com → **Add New → Project** → chọn repo này.
2. Framework Preset để **Other**, không đặt Build Command.
3. **Deploy**. Vercel đọc `requirements.txt`, thấy `fastapi`, và lấy
   entrypoint từ `[tool.vercel]` trong `pyproject.toml`.
4. Xong thì mở `https://<tên>.vercel.app/api/health` — phải trả về
   `{"status":"ok"}`. Rồi mở `/` để xem trang.

Ba cấu hình đáng để ý:

- **`pyproject.toml` khai cả phụ thuộc lẫn entrypoint.** Xem phần dưới —
  lần deploy đầu đổ đúng ở đây.
- **Chỉ một phụ thuộc: `fastapi`.** Vercel gói mọi thứ đọc được lúc build,
  nên để streamlit và pandas trong đó là cài cả trăm MB không dùng tới.
  Phụ thuộc của bản Streamlit nằm trong `requirements-streamlit.txt`. Hệ
  quả: bản Streamlit Cloud cũ sẽ không còn cài được streamlit — đúng ý
  muốn, vì Vercel thay nó.
- **`vercel.json` loại `tests/`, `data/`, `scripts/` khỏi gói.** Không loại
  `public/` — chính app Python phục vụ trang từ đó.

### Lần deploy đầu đổ, và vì sao

```
Installing required dependencies from pyproject.toml...
error: No `project` table found in: /vercel/path0/pyproject.toml
```

`pyproject.toml` lúc đó chỉ có bảng `[tool.vercel]` để chỉ entrypoint, cố
tình bỏ `[project]` để phụ thuộc chỉ khai một nơi là `requirements.txt`.

Chỗ sai: **chỉ cần pyproject.toml tồn tại là Vercel dùng `uv` đọc phụ thuộc
từ đó** và bỏ qua requirements.txt — mà `uv lock` bắt buộc có `[project]`.
Không có cách nào "vừa có pyproject để chỉ entrypoint, vừa để
requirements.txt lo phụ thuộc": có pyproject là nó lo cả hai.

Bản sửa khai `[project]` đầy đủ, cộng `[tool.uv] package = false` để uv
biết đây là ứng dụng chứ không phải thư viện cần build (thiếu dòng đó thì
uv đòi `[build-system]`).

`requirements.txt` giữ lại cho ai quen `pip install -r`, và
`test_phu_thuoc_khai_o_hai_noi_phai_khop` bắt hai chỗ lệch nhau — duplication
thì được, miễn có test giữ cho nó trung thực.

`uv.lock` **có** commit: với lock, Vercel resolve mất vài mili giây; không
có lock thì hơn một phút.

`tests/test_cau_hinh_deploy.py` có 16 test chặn cả loại lỗi này: có
`[project]` không, entrypoint trỏ tới file có thật không, `.python-version`
có thoả `requires-python` không, `vercel.json` có vô tình loại `public/`
không. Cấu hình sai mà chỉ lộ ra khi build thì mỗi lần thử mất vài phút —
đáng để rà bằng `pytest`.

### Vì sao API tự phục vụ luôn trang tĩnh

Khi dự án dùng preset framework, Vercel định tuyến **mọi** request vào hàm
Python. Nếu app không tự trả `public/index.html` thì `/` ra 404.

Để app tự phục vụ còn được thêm một điều: chạy `uvicorn api.main:app` ở máy
giống hệt lúc deploy — cùng một gốc cho cả trang lẫn API. Không có bước
định tuyến nào chỉ tồn tại ở một nơi rồi hỏng ở nơi kia.

### Trang chọn gốc API bằng cách thử, không đoán

Trang chạy ở ba nơi: trên Vercel (cùng gốc với API), mở thẳng bằng file, và
trong trình xem artifact. Hai nơi sau không cùng gốc nên phải gọi địa chỉ
tuyệt đối.

Thay vì đoán theo tên miền, trang gọi thử cùng gốc trước; hỏng thì mới dùng
địa chỉ dự phòng. Đoán theo tên miền là thứ sẽ sai ngay lần đầu dự án có
tên miền riêng.

Địa chỉ dự phòng nằm ở một thẻ `<meta>` trong `<head>`, không viết trong
JavaScript:

```html
<meta name="jbi-api" content="https://tên-của-bạn.vercel.app">
```

Để trống thì trang chỉ gọi cùng gốc — đúng cho bản trên Vercel. Điền vào
khi cần mở trang bằng file hoặc trong trình xem artifact. Đặt ở thẻ meta để
đổi tên miền là sửa một dòng HTML, không phải đi tìm trong hơn 1.200 dòng
script.

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
| Dài hạn | Đăng nhập thật **đi kèm** database trên host (hai việc không tách được), tự động lấy giá từ sàn, thống kê chéo nhiều người dùng, thay hiệu số trung bình bằng hồi quy logistic khi đủ dữ liệu |

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
