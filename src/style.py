"""Lớp trang trí cho giao diện Streamlit.

Vì sao cần file này: `.streamlit/config.toml` đổi được **màu**, nhưng không
đổi được **hình khối và kiểu chữ**. Để nguyên thì app trông như mọi app
Streamlit khác: cùng nút +/− trên ô số, cùng nhãn, cùng cỡ chữ.

Hai nguyên tắc, cả hai đều rút ra từ lỗi đã gặp:

1. **Không bao giờ đặt màu chữ.** Chỉ dùng `opacity` để làm nhạt. Chữ luôn
   thừa hưởng màu từ giao diện Streamlit, nên dù màu nền có lệch thì chữ
   vẫn đọc được. Bản trước đặt cả nền lẫn màu chữ theo chế độ đọc từ Python;
   khi Python đọc sai chế độ thì nền sáng chồng dưới chữ kem — chữ biến mất.

2. **Không hỏi Python đang ở chế độ nào.** Vì `toolbarMode = "minimal"` đã
   ẩn menu đổi giao diện, chế độ sáng/tối chỉ còn phụ thuộc thiết lập hệ
   điều hành — thứ mà CSS đọc trực tiếp được bằng `prefers-color-scheme`.
   Không còn khoảng lệch giữa lúc Python đoán và lúc trình duyệt vẽ.

Nguyên tắc thứ ba, về chọn selector: **chỉ bám vào `data-testid` và
`st-key-*`**. Tên class kiểu `st-emotion-cache-1a2b3c` do Streamlit sinh ra
và đổi mỗi phiên bản — bám vào đó là giao diện vỡ ở lần cập nhật kế tiếp.
"""

from typing import Dict

# Chỉ còn những màu **bề mặt** cần biết trước. Màu chữ không nằm ở đây, và
# đó là chủ ý: chữ luôn lấy từ giao diện Streamlit.
SURFACES: Dict[str, Dict[str, str]] = {
    "light": {
        # Tờ hoá đơn cùng màu nền trang; bóng đổ là thứ tách nó ra.
        "sheet": "#FFFEFA",
        "shadow": "0 10px 28px rgba(30, 58, 51, .13)",
    },
    "dark": {
        # Trong đêm bóng đổ không thấy, nên tờ giấy phải sáng hơn nền một
        # chút mới đọc ra là một tờ riêng.
        "sheet": "#2B2720",
        "shadow": "0 10px 30px rgba(0, 0, 0, .35)",
    },
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


def css() -> str:
    """Trả về toàn bộ CSS trang trí.

    Không nhận tham số chế độ: cả hai chế độ nằm trong cùng một chuỗi, và
    `prefers-color-scheme` chọn giúp.
    """
    light, dark = SURFACES["light"], SURFACES["dark"]

    return f"""
<style>
@import url('{FONT_URL}');

/* ============================================================ BIẾN MÀU

   Chỉ khai báo màu **bề mặt**. Đường kẻ và viền suy ra từ `currentColor`
   nên tự đúng ở cả hai chế độ mà không cần khai báo hai lần. */

:root {{
  --jbi-sheet: {light['sheet']};
  --jbi-shadow: {light['shadow']};
  /* Khai báo rgba trước làm dự phòng cho trình duyệt chưa có color-mix. */
  --jbi-rule: rgba(128, 122, 110, .38);
  --jbi-rule: color-mix(in srgb, currentColor 22%, transparent);
  --jbi-hairline: rgba(128, 122, 110, .22);
  --jbi-hairline: color-mix(in srgb, currentColor 14%, transparent);
}}

@media (prefers-color-scheme: dark) {{
  :root {{
    --jbi-sheet: {dark['sheet']};
    --jbi-shadow: {dark['shadow']};
  }}
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

   Cố tình KHÔNG đặt màu nền hay màu chữ cho ô nhập: để Streamlit tự tô
   theo chế độ của nó. Đây chính là chỗ bản trước làm sai. */

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
   đơn" mà không cần một dòng chữ nào. */

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
