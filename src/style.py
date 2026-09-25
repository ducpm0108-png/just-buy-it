"""Lớp trang trí cho giao diện Streamlit.

Vì sao cần file này: `.streamlit/config.toml` đổi được **màu**, nhưng không
đổi được **hình khối và kiểu chữ**. Để nguyên thì app trông như mọi app
Streamlit khác: cùng nút +/− trên ô số, cùng nhãn, cùng cỡ chữ.

Bốn nguyên tắc, cả bốn đều rút ra từ lỗi đã thật sự gặp trên bản deploy:

1. **Không bao giờ đặt màu chữ.** Chỉ dùng `opacity` để làm nhạt. Chữ luôn
   thừa hưởng màu từ giao diện Streamlit, nên dù nền có lệch thì chữ vẫn
   đọc được.

2. **Không hỏi Python đang ở chế độ nào.** `st.context.theme.type` trả về
   giá trị suy đoán từ màu nền, và nó đã trả về "light" trong khi Streamlit
   vẽ chế độ tối. CSS chồng nền sáng dưới chữ kem — chữ biến mất.

3. **Không hỏi hệ điều hành đang ở chế độ nào.** Đây là lỗi lần hai, ngược
   chiều lỗi lần một. `prefers-color-scheme` đọc thiết lập của máy, còn
   Streamlit vẽ theo thiết lập riêng của nó; hai thứ đó lệch nhau được. Máy
   đặt chế độ tối mà Streamlit vẫn vẽ sáng thì tờ hoá đơn hoá đen giữa
   trang giấy trắng.

4. **Không gọi tên màu nào phải khớp với một chế độ.** Đây là kết luận
   chung của hai lỗi trên: mọi cách biết chế độ đều đoán được, nên đừng
   biết. Mọi màu bề mặt ở đây suy ra từ `currentColor` — màu chữ mà chính
   Streamlit đã đặt — nên chúng tự đúng theo đúng cái Streamlit vẽ, không
   phải theo cái ta tưởng nó vẽ.

   Cơ chế làm việc đó chạy được: biến CSS chưa đăng ký được thay thế
   dạng **văn bản** rồi mới tính giá trị tại chính phần tử dùng nó. Nên
   `currentColor` trong `--jbi-sheet` không tính ở `:root` mà tính ở tờ hoá
   đơn, nơi màu chữ đã là màu chữ thật của giao diện.

   Kiểm chứng được bằng `grep`: file này không còn một mã màu hex nào, và
   `test_khong_con_ma_mau_tuyet_doi` chặn việc thêm lại.

Nguyên tắc thứ năm, về chọn selector: **chỉ bám vào `data-testid` và
`st-key-*`**. Tên class kiểu `st-emotion-cache-1a2b3c` do Streamlit sinh ra
và đổi mỗi phiên bản — bám vào đó là giao diện vỡ ở lần cập nhật kế tiếp.

Ngoại lệ duy nhất của nguyên tắc 1 là `STAMP_COLORS` bên dưới: màu ở đó
**mang nghĩa** (xanh là mua, đỏ là đừng) chứ không mang bề mặt, nên phải gọi
tên thật. Đánh đổi là nó buộc phải kiểm tra trên cả hai mặt giấy, và
`test_mau_con_dau_doc_duoc_tren_ca_hai_mat_giay` làm việc đó.
"""

from typing import Dict

# Độ pha của các bề mặt, tính theo phần trăm màu chữ trộn vào nền. Đây là
# thứ thay cho bảng mã màu cũ: một con số thay vì hai mã màu, và không cần
# biết chế độ nào.
#
# Vì sao 5%: pha 5% màu chữ vào nền cho ra gần đúng hai màu giấy đã chọn tay
# trước đây (#F4F3EF ở chế độ sáng, #2D2A23 ở chế độ tối) — bằng chứng rằng
# cách tính tương đối không làm mất thiết kế, chỉ bỏ phần đoán chế độ.
MIX: Dict[str, int] = {
    "sheet": 5,      # tờ hoá đơn, nhạt hơn nền một bậc
    "rule": 22,      # đường kẻ ngang trong hoá đơn
    "hairline": 14,  # đường kẻ mảnh hơn, dưới thẻ tab
}

# Màu con dấu kết luận — bốn màu MANG NGHĨA, nên đây là chỗ duy nhất trong
# lớp trang trí được gọi tên màu thật.
#
# Ràng buộc: cùng một màu phải đọc được trên tờ giấy sáng (#F4F3EF) và tờ
# giấy tối (#2D2A23). Đặt bài toán ra thì thấy 4,5:1 trên cả hai mặt là
# KHÔNG thể: muốn đạt 4,5:1 trên giấy sáng thì độ sáng màu phải ≤ 0,160,
# muốn đạt trên giấy tối thì phải ≥ 0,280 — hai khoảng không giao nhau. Nên
# đích là 3:1, mức WCAG cho chữ lớn in đậm, và chữ tiêu đề trong con dấu
# được đặt 19px đậm để thật sự thuộc diện "chữ lớn".
#
# Bốn màu dưới đây đạt 3,4–3,8:1 trên cả hai mặt. Bộ màu cũ (#2E6B4F,
# #2B4C7E, #A2701B, #B3382C) chọn theo mắt trên nền sáng, và ba trong bốn
# chỉ đạt 1,7–2,4:1 trên giấy tối.
#
# Màu không phải tín hiệu duy nhất: chữ "MUA ĐI" hay "ĐỪNG MUA" đã nói rõ
# kết luận, nên người không phân biệt được màu vẫn đọc được kết quả.
STAMP_COLORS: Dict[str, str] = {
    "buy": "#3D8F69",    # cùng màu với vạch "dưới ngưỡng" của thanh điểm
    "wait": "#4E80C8",
    "plan": "#A87C22",
    "no": "#D2554A",     # cùng màu với vạch "vượt ngưỡng"
}

# Be Vietnam Pro là bộ chữ thiết kế cho tiếng Việt nên dấu đặt đúng chỗ,
# không chồng lên chữ hoa như nhiều bộ chữ phương Tây.
FONT_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Be+Vietnam+Pro:wght@400;500;600;700"
    "&family=IBM+Plex+Mono:wght@400;500;600"
    "&display=swap"
)
BODY_FONT = '"Be Vietnam Pro", system-ui, -apple-system, "Segoe UI", sans-serif'
# Chuỗi dự phòng có DejaVu Sans Mono và Consolas vì chúng chứa ký hiệu ₫;
# một số font đơn cách thiếu ký hiệu này và trình duyệt thay bằng glyph lạ.
MONO_FONT = (
    '"IBM Plex Mono", ui-monospace, "SFMono-Regular", Consolas, '
    '"DejaVu Sans Mono", monospace'
)


def _mix(key: str) -> str:
    """Một bề mặt, tính theo màu chữ hiện hành.

    Giá trị dự phòng là màu xám trung tính rất nhạt, đặt trước dòng
    `color-mix` để trình duyệt cũ vẫn có cái dùng. Xám trung tính chịu được
    cả hai chế độ: nó sáng hơn nền tối và tối hơn nền sáng, nên dù rơi về
    dự phòng thì bề mặt vẫn tách khỏi nền, chỉ là nhạt hơn ý muốn.
    """
    pct = MIX[key]
    return (
        f"rgba(128, 122, 110, {pct / 100:.2f});\n"
        f"  --jbi-{key}: color-mix(in srgb, currentColor {pct}%, transparent)"
    )


def css() -> str:
    """Trả về toàn bộ CSS trang trí.

    Không nhận tham số chế độ, và không chứa media query chế độ nào: chuỗi
    này giống nhau ở mọi chế độ, còn việc khớp màu do `currentColor` lo.
    """
    return f"""
<style>
@import url('{FONT_URL}');

/* ============================================================ BỀ MẶT

   Không có mã màu nào ở đây, và đó là chủ ý — xem nguyên tắc 4 trong
   docstring của src/style.py. Mỗi biến pha một ít màu chữ vào nền, nên
   chế độ sáng cho bề mặt sẫm hơn nền, chế độ tối cho bề mặt sáng hơn nền,
   mà CSS không cần biết mình đang ở chế độ nào. */

:root {{
  --jbi-sheet: {_mix('sheet')};
  --jbi-rule: {_mix('rule')};
  --jbi-hairline: {_mix('hairline')};
  /* Bóng đổ dùng một giá trị cho cả hai chế độ: ở chế độ tối nó gần như
     không thấy, nhưng lúc đó tờ giấy đã sáng hơn nền nên vẫn nổi. */
  --jbi-shadow: 0 10px 28px rgba(0, 0, 0, .16);
}}

/* ============================================================ CHỮ

   Font nạp bằng @import vì config.toml chỉ nhận URL của từng file font,
   còn @import nhận cả bộ qua một địa chỉ. */

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stSidebar"] {{
  font-family: {BODY_FONT};
}}

/* Số tiền dùng chữ đơn cách và chữ số cùng bề rộng, để các cột số thẳng
   hàng nhau — thứ tối thiểu của một công cụ tính tiền. */
[data-testid="stMetricValue"],
[data-testid="stNumberInputField"],
[data-testid="stSliderThumbValue"],
[data-testid="stSliderTickBar"] {{
  font-family: {MONO_FONT};
  font-variant-numeric: tabular-nums;
}}

[data-testid="stMetricValue"] {{
  letter-spacing: -.02em;
  font-weight: 600;
}}

[data-testid="stMetricLabel"] p {{
  font-size: .74rem;
  font-weight: 500;
  letter-spacing: .1em;
  text-transform: uppercase;
  opacity: .62;
}}

/* ============================================================ Ô NHẬP

   Bỏ hai nút +/− của ô số. Với tám ô số trên một trang, chúng là thứ làm
   giao diện trông "mặc định" nhất, mà gõ số vẫn nhanh hơn bấm nút.

   Cố tình KHÔNG đặt nền cho ô nhập: màu nền ô nhập nằm ở config.toml,
   trong `secondaryBackgroundColor` của từng chế độ, nơi Streamlit tự chọn
   đúng cái. Đó là chỗ duy nhất trong dự án được phép gọi tên màu theo chế
   độ, vì ở đó không ai phải đoán. */

[data-testid="stNumberInputStepUp"],
[data-testid="stNumberInputStepDown"] {{
  display: none !important;
}}

[data-testid="stNumberInputField"] {{
  text-align: right;
  font-size: .92rem;
  padding-right: 10px;
}}

[data-testid="stNumberInputContainer"],
[data-testid="stTextInputRootElement"] {{
  border-color: var(--jbi-rule);
}}

/* Nhãn ô nhập: nhỏ và nhạt hơn nội dung, để mắt đọc giá trị trước nhãn. */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {{
  font-size: .82rem;
  font-weight: 500;
  opacity: .72;
  margin-bottom: 1px;
}}

/* ============================================================ TIÊU ĐỀ NHÓM

   Thay cho việc in đậm một dòng chữ thường: chữ nhỏ, giãn cách, có đường
   kẻ dưới — giống dòng legend của một khối fieldset trên giấy tờ. */

.jbi-legend {{
  font-family: {MONO_FONT};
  font-size: .72rem;
  font-weight: 600;
  letter-spacing: .14em;
  text-transform: uppercase;
  opacity: .6;
  padding-bottom: 7px;
  margin: 26px 0 4px;
  border-bottom: 1px solid var(--jbi-rule);
}}

/* ============================================================ HOÁ ĐƠN

   Khối này được đánh dấu bằng key="receipt" trong app.py. Hai mép răng cưa
   trên dưới là chi tiết nhận dạng của cả sản phẩm — nó nói "đây là tờ hoá
   đơn" mà không cần một dòng chữ nào.

   Mép răng cưa nằm ngoài khung nên nền của nó chồng lên nền trang, và vì
   `--jbi-sheet` trong suốt một phần, chỗ đó tự pha ra đúng màu tờ giấy —
   không cần biết nền trang màu gì. */

.st-key-receipt {{
  position: relative;
  border: 0 !important;
  background: var(--jbi-sheet);
  padding: 26px 22px 30px !important;
  box-shadow: var(--jbi-shadow);
}}

.st-key-receipt::before,
.st-key-receipt::after {{
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  height: 9px;
  background: radial-gradient(
    circle at 6px 0, transparent 0 6px, var(--jbi-sheet) 6px
  ) 0 0 / 12px 9px repeat-x;
}}

.st-key-receipt::before {{ top: -8px; transform: scaleY(-1); }}
.st-key-receipt::after  {{ bottom: -8px; }}

/* ============================================================ THẺ TAB */

[data-testid="stTabs"] [role="tablist"] {{
  gap: 2px;
  border-bottom: 1px solid var(--jbi-hairline);
}}

[data-testid="stTabs"] [role="tab"] {{
  font-size: .9rem;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 3px 3px 0 0;
}}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
  font-weight: 600;
}}

/* ============================================================ VỤN VẶT */

[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {{
  letter-spacing: .01em;
  font-weight: 500;
}}

[data-testid="stCaptionContainer"] p {{
  font-size: .79rem;
  line-height: 1.5;
}}

[data-testid="stExpander"] details {{
  border-color: var(--jbi-rule);
}}

[data-testid="stDataFrame"] {{
  font-variant-numeric: tabular-nums;
}}

[data-testid="stFileUploaderDropzone"] {{
  padding: 12px 14px;
}}
</style>
"""
