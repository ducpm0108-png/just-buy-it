"""Kiểm thử lớp trang trí.

`style.css()` là hàm thuần nên kiểm thử được mà không cần chạy Streamlit.
Bốn test đầu chặn đúng những lỗi đã thật sự xảy ra trên bản deploy.
"""

import pathlib
import re
import tomllib

import pytest

from src import style

CONFIG = pathlib.Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"


def _rgb(hexa):
    h = hexa.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _mau_giay():
    """Tính hai màu tờ giấy đúng cách trình duyệt tính.

    Đọc bảng màu thật từ config.toml rồi pha `MIX["sheet"]` phần trăm màu
    chữ vào màu nền — y hệt việc `color-mix` làm lúc chạy. Nhờ vậy nếu ai
    đổi bảng màu trong config.toml thì test này tự tính lại và bắt được màu
    con dấu nào không còn đọc được.
    """
    cfg = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    a = style.MIX["sheet"] / 100
    out = {}
    for mode in ("light", "dark"):
        bg, ink = _rgb(cfg["theme"][mode]["backgroundColor"]), _rgb(
            cfg["theme"][mode]["textColor"])
        out[mode] = tuple(ink[i] * a + bg[i] * (1 - a) for i in range(3))
    return out


def _khong_chu_thich(css: str) -> str:
    """Bỏ chú thích khỏi CSS, vì chú thích có nhắc tên thuộc tính lẫn mã màu."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


# ------------------------------------------------- lỗi đã gặp

def test_khong_dat_mau_chu_o_bat_ky_dau():
    """Lỗi lần một: chữ biến mất trên bản deploy.

    Bản cũ đặt cả màu nền lẫn màu chữ theo chế độ đọc từ Python. Khi Python
    đọc sai chế độ, nền sáng chồng dưới chữ kem và chữ mất hẳn. Cách chặn:
    tuyệt đối không đặt `color:`, chỉ làm nhạt bằng `opacity`.
    """
    body = _khong_chu_thich(style.css())
    khai_bao_mau_chu = re.findall(r"(?<!-)\bcolor\s*:", body)
    assert not khai_bao_mau_chu, f"có {len(khai_bao_mau_chu)} chỗ đặt màu chữ"


def test_khong_dat_mau_nen_cho_o_nhap():
    """Ô nhập phải để Streamlit tự tô; đặt nền là nguồn gốc của lỗi trên."""
    out = style.css()
    m = re.search(r'\[data-testid="stNumberInputContainer"\][^{]*\{([^}]*)\}', out)
    assert m, "không tìm thấy khối quy định ô nhập số"
    assert "background" not in m.group(1)


def test_khong_hoi_python_ve_che_do():
    """css() không nhận tham số chế độ — Python không được biết chế độ."""
    import inspect
    assert list(inspect.signature(style.css).parameters) == []


def test_khong_hoi_he_dieu_hanh_ve_che_do():
    """Lỗi lần hai, ngược chiều lỗi lần một.

    `prefers-color-scheme` đọc thiết lập của máy, còn Streamlit vẽ theo
    thiết lập riêng của nó. Máy đặt tối mà Streamlit vẽ sáng thì tờ hoá đơn
    hoá đen giữa trang giấy trắng.
    """
    assert "prefers-color-scheme" not in style.css()


def test_khong_con_ma_mau_tuyet_doi():
    """Kết luận chung của hai lỗi trên, viết thành một điều kiện rà được.

    Mọi màu bề mặt phải suy ra từ `currentColor`. Một mã màu hex quay lại
    file này nghĩa là có ai đó vừa gọi tên màu của một chế độ cụ thể — đúng
    cái đã làm vỡ giao diện hai lần.

    Ngoại lệ được phép: màu dự phòng dạng `rgba()` xám trung tính, vì xám
    trung tính không thuộc chế độ nào, và bóng đổ đen trong suốt.
    """
    body = _khong_chu_thich(style.css())
    hex_mau = re.findall(r"#[0-9a-fA-F]{3,8}\b", body)
    assert not hex_mau, f"có mã màu tuyệt đối: {hex_mau}"


def test_moi_be_mat_deu_suy_ra_tu_mau_chu():
    out = style.css()
    for ten in style.MIX:
        assert f"--jbi-{ten}: color-mix(in srgb, currentColor" in out, ten


# ------------------------------------------------- dự phòng

def test_bien_mau_co_gia_tri_du_phong():
    """Trình duyệt chưa hỗ trợ color-mix vẫn phải có màu để dùng."""
    out = style.css()
    for ten in style.MIX:
        assert out.count(f"--jbi-{ten}:") == 2, f"{ten} thiếu dòng dự phòng"
    assert "rgba(128, 122, 110" in out


def test_du_phong_la_xam_trung_tinh():
    """Xám trung tính chịu được cả hai chế độ: sáng hơn nền tối, tối hơn nền
    sáng. Nếu dự phòng nghiêng về một chế độ thì nó lại là lỗi cũ."""
    for m in re.finditer(r"rgba\((\d+), (\d+), (\d+),", style.css()):
        r, g, b = (int(x) for x in m.groups())
        if (r, g, b) == (0, 0, 0):
            continue                     # bóng đổ, không phải bề mặt
        assert max(r, g, b) - min(r, g, b) <= 24, f"rgba({r},{g},{b}) quá lệch màu"
        assert 96 <= (r + g + b) / 3 <= 160, f"rgba({r},{g},{b}) không trung tính"


# ------------------------------------------------- màu mang nghĩa

@pytest.mark.parametrize("ket_luan", sorted(style.STAMP_COLORS))
def test_mau_con_dau_doc_duoc_tren_ca_hai_mat_giay(ket_luan):
    """Con dấu là dòng quan trọng nhất trên trang, nên phải đọc được ở cả
    hai chế độ.

    Đích là 3:1 vì 4,5:1 trên cả hai mặt là bất khả — xem phần tính toán ở
    `style.STAMP_COLORS`. Bù lại, chữ tiêu đề đặt 19px đậm nên thuộc diện
    chữ lớn, mức 3:1 là đúng chuẩn cho nó.
    """
    mau = _rgb(style.STAMP_COLORS[ket_luan])
    for mode, giay in _mau_giay().items():
        ty_le = _contrast(mau, giay)
        assert ty_le >= 3.0, f"{ket_luan} trên giấy {mode}: {ty_le:.2f}:1"


def test_bon_mau_con_dau_khac_nhau():
    assert len(set(style.STAMP_COLORS.values())) == len(style.STAMP_COLORS)


def test_app_dung_bang_mau_chung_khong_tu_dat_tai_cho():
    """Bộ màu đặt tại chỗ trong app.py là bộ chỉ đúng trên nền sáng."""
    src = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8")
    assert "style.STAMP_COLORS[verdict.key]" in src
    for cu in ("#2E6B4F", "#2B4C7E", "#A2701B"):
        assert cu not in src, f"màu cũ {cu} vẫn còn trong app.py"


# ------------------------------------------------- selector ổn định

def test_khong_bam_vao_class_do_streamlit_sinh():
    """Bám vào `st-emotion-cache-*` là giao diện sẽ vỡ ở bản Streamlit sau."""
    out = style.css()
    assert "st-emotion-cache" not in out
    assert not re.search(r"\.e[a-z0-9]{8,}\b", out), "có vẻ đang bám vào class băm"


# ------------------------------------------------- nội dung

def test_an_nut_tang_giam_cua_o_so():
    out = style.css()
    assert "stNumberInputStepUp" in out
    assert "stNumberInputStepDown" in out
    assert "display: none" in out


def test_co_nap_font_va_dung_font_do():
    out = style.css()
    assert "@import" in out and "fonts.googleapis.com" in out
    assert "Be Vietnam Pro" in out
    assert "IBM Plex Mono" in out


def test_font_du_phong_co_font_chua_ky_hieu_dong():
    """₫ là ký hiệu nhiều font đơn cách không có; cần font dự phòng chứa nó."""
    assert "DejaVu Sans Mono" in style.css()


def test_hoa_don_va_mep_rang_cua_dung_cung_mot_be_mat():
    """Mép răng cưa phải cùng màu tờ giấy, không thì thấy đường ghép."""
    out = style.css()
    khoi = out[out.index(".st-key-receipt"):out.index("THẺ TAB")]
    assert khoi.count("var(--jbi-sheet)") == 2


def test_the_style_dong_mo_day_du():
    out = style.css().strip()
    assert out.startswith("<style>") and out.endswith("</style>")
    assert out.count("<style>") == 1 and out.count("</style>") == 1


def test_khong_con_cho_thay_the_nao_bo_sot():
    """Ngoặc nhọn đơn lẻ còn lại là dấu hiệu f-string thay thế bị lỗi."""
    out = style.css()
    assert "{light[" not in out and "{dark[" not in out
    assert "{{" not in out and "}}" not in out
