"""Lớp trang trí cho giao diện Streamlit.

Vì sao cần file này: `.streamlit/config.toml` đổi được **màu**, nhưng không
đổi được **hình khối và kiểu chữ**. Để nguyên thì app trông như mọi app
Streamlit khác: cùng nút +/− trên ô số, cùng nhãn, cùng cỡ chữ.

Nguyên tắc khi viết CSS ở đây: **chỉ bám vào `data-testid` và `st-key-*`**.
Tên class kiểu `st-emotion-cache-1a2b3c` là do Streamlit sinh ra và đổi mỗi
phiên bản — bám vào đó là giao diện sẽ vỡ ở lần cập nhật kế tiếp.

`css()` là hàm thuần: nhận chế độ sáng/tối, trả về chuỗi CSS. Nhờ vậy kiểm
thử được mà không cần chạy Streamlit.
"""

from typing import Dict

# Bảng màu trùng với .streamlit/config.toml. Cần lặp lại ở đây vì Streamlit
# không phơi màu của giao diện ra thành biến CSS, nên CSS phải tự biết.
PALETTE: Dict[str, Dict[str, str]] = {
    "light": {
        "paper": "#FFFEFA",
        # Tờ hoá đơn cùng màu nền trang; bóng đổ là thứ tách nó ra.
        "sheet": "#FFFEFA",
        "sheet_shadow": "0 10px 28px rgba(30, 58, 51, .13)",
        "rule": "#D4CEC0",
        "ink": "#221F1A",
        "ink_soft": "#6B655A",
        "field": "#FFFFFF",
        "field_line": "#C6BFAE",
        "accent": "#B3382C",
    },
    "dark": {
        "paper": "#232019",
        # Trong đêm thì bóng đổ không thấy, nên tờ giấy phải sáng hơn nền
        # một chút mới đọc ra là một tờ riêng.
        "sheet": "#2B2720",
        "sheet_shadow": "0 10px 30px rgba(0, 0, 0, .35)",
        "rule": "#4A443A",
        "ink": "#EDE7D9",
        "ink_soft": "#9A9384",
        "field": "#2C2821",
        "field_line": "#4A443A",
        "accent": "#E06A5C",
    },
}

# Font chữ. Be Vietnam Pro là bộ chữ thiết kế cho tiếng Việt nên dấu đặt
# đúng chỗ, không bị chồng lên chữ hoa như nhiều bộ chữ phương Tây.
# IBM Plex Mono dùng cho số và hoá đơn.
FONT_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Be+Vietnam+Pro:wght@400;500;600;700"
    "&family=IBM+Plex+Mono:wght@400;500;600"
    "&display=swap"
)
BODY_FONT = '"Be Vietnam Pro", system-ui, -apple-system, "Segoe UI", sans-serif'
# Chuỗi dự phòng có DejaVu Sans Mono và Consolas vì chúng chứa ký hiệu ₫;
# một số font đơn cách thiếu ký hiệu này và trình duyệt sẽ thay bằng glyph
# trông lạ mắt.
MONO_FONT = (
    '"IBM Plex Mono", ui-monospace, "SFMono-Regular", Consolas, '
    '"DejaVu Sans Mono", monospace'
)


def css(mode: str = "light") -> str:
    """Trả về toàn bộ CSS trang trí, đã thay màu theo chế độ sáng hoặc tối."""
    c = PALETTE.get(mode, PALETTE["light"])

    return f"""
<style>
@import url('{FONT_URL}');

/* ============================================================ CHỮ

   Font đặt ở đây thay vì trong config.toml vì config chỉ nhận URL của
   từng file font, còn @import nhận được cả bộ qua một địa chỉ. */

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
  font-family: {BODY_FONT};
}}

/* Số liệu tiền tệ dùng chữ đơn cách và chữ số cùng bề rộng, để các cột số
   thẳng hàng nhau — thứ tối thiểu của một công cụ tính tiền. */
[data-testid="stMetricValue"],
[data-testid="stNumberInputField"],
[data-testid="stSliderThumbValue"],
[data-testid="stSliderTickBar"] {{
  font-family: {MONO_FONT};
  font-variant-numeric: tabular-nums;
}}

[data-testid="stMetricValue"] {{
  letter-spacing: -0.02em;
  font-weight: 600;
}}

[data-testid="stMetricLabel"] p {{
  font-size: 0.74rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: {c['ink_soft']};
}}

/* ============================================================ Ô NHẬP

   Bỏ hai nút +/− của ô số. Với tám ô số trên một trang, chúng là thứ làm
   giao diện trông "mặc định" nhất, mà gõ số thì nhanh hơn bấm nút. */

[data-testid="stNumberInputStepUp"],
[data-testid="stNumberInputStepDown"] {{
  display: none !important;
}}

[data-testid="stNumberInputField"] {{
  text-align: right;
  font-size: 0.92rem;
  padding-right: 10px;
}}

[data-testid="stNumberInputContainer"],
[data-testid="stTextInputRootElement"] {{
  border-color: {c['field_line']};
  background: {c['field']};
}}

[data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within {{
  border-color: {c['accent']};
}}

/* Nhãn ô nhập: nhỏ và nhạt hơn nội dung, để mắt đọc giá trị trước nhãn. */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {{
  font-size: 0.82rem;
  font-weight: 500;
  color: {c['ink_soft']};
  margin-bottom: 1px;
}}

/* ============================================================ TIÊU ĐỀ NHÓM

   Thay cho việc in đậm một dòng chữ thường: chữ nhỏ, giãn cách, có đường
   kẻ dưới — giống dòng legend của một khối fieldset trên giấy tờ. */

.jbi-legend {{
  font-family: {MONO_FONT};
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: {c['ink_soft']};
  padding-bottom: 7px;
  margin: 26px 0 4px;
  border-bottom: 1px solid {c['rule']};
}}

/* ============================================================ HOÁ ĐƠN

   Khối hoá đơn được đánh dấu bằng key="receipt" trong app.py. Hai mép răng
   cưa trên dưới là chi tiết nhận dạng của cả sản phẩm — nó nói "đây là tờ
   hoá đơn" mà không cần một dòng chữ nào. */

.st-key-receipt {{
  position: relative;
  border: 0 !important;
  background: {c['sheet']};
  padding: 26px 22px 30px !important;
  box-shadow: {c['sheet_shadow']};
}}

.st-key-receipt::before,
.st-key-receipt::after {{
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  height: 9px;
  background: radial-gradient(
    circle at 6px 0, transparent 0 6px, {c['sheet']} 6px
  ) 0 0 / 12px 9px repeat-x;
}}

.st-key-receipt::before {{ top: -8px; transform: scaleY(-1); }}
.st-key-receipt::after  {{ bottom: -8px; }}

/* ============================================================ THẺ TAB

   Tab trông như mép giấy nhô lên: tab đang chọn mang màu giấy, các tab
   khác lùi lại phía sau. */

[data-testid="stTabs"] [role="tablist"] {{
  gap: 2px;
  border-bottom: 1px solid {c['rule']};
}}

[data-testid="stTabs"] [role="tab"] {{
  font-size: 0.9rem;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 3px 3px 0 0;
}}

[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
  background: {c['paper']};
  font-weight: 600;
}}

/* ============================================================ NÚT

   Vuông vắn hơn, chữ giãn nhẹ — giấy tờ thì không bo góc tròn. */

[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {{
  letter-spacing: 0.01em;
  font-weight: 500;
}}

/* ============================================================ VỤN VẶT */

[data-testid="stCaptionContainer"] p {{
  font-size: 0.79rem;
  line-height: 1.5;
  color: {c['ink_soft']};
}}

/* Khối mở rộng phẳng hơn, đỡ tranh chú ý với nội dung chính. */
[data-testid="stExpander"] details {{
  border-color: {c['rule']};
}}

/* Bảng dữ liệu: số dùng chữ đơn cách cho thẳng cột. */
[data-testid="stDataFrame"] {{
  font-variant-numeric: tabular-nums;
}}

/* Ô tải file bớt cao, vì nó chỉ là tính năng phụ. */
[data-testid="stFileUploaderDropzone"] {{
  padding: 12px 14px;
}}
</style>
"""
