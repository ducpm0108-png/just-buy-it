"""Kiểm thử lớp trang trí.

`style.css()` là hàm thuần nên kiểm thử được mà không cần chạy Streamlit.
Ba test đầu chặn đúng những lỗi đã thật sự xảy ra trên bản deploy.
"""

import re
import pytest

from src import style


# ------------------------------------------------- lỗi đã gặp

def test_khong_dat_mau_chu_o_bat_ky_dau():
    """Đây là lỗi làm chữ biến mất trên bản deploy.

    Bản trước đặt cả màu nền lẫn màu chữ theo chế độ đọc từ Python. Khi
    Python đọc sai chế độ, nền sáng chồng dưới chữ kem và chữ mất hẳn.
    Cách chặn: tuyệt đối không đặt `color:`, chỉ làm nhạt bằng `opacity`.
    """
    out = style.css()
    # Bỏ các dòng chú thích trước khi rà, vì chú thích có chữ "color-mix".
    body = "\n".join(
        ln for ln in out.splitlines()
        if not ln.strip().startswith(("/*", "*", "//"))
    )
    khai_bao_mau_chu = re.findall(r"(?<!-)\bcolor\s*:", body)
    assert not khai_bao_mau_chu, f"có {len(khai_bao_mau_chu)} chỗ đặt màu chữ"


def test_khong_dat_mau_nen_cho_o_nhap():
    """Ô nhập phải để Streamlit tự tô; đặt nền là nguồn gốc của lỗi trên."""
    out = style.css()
    m = re.search(r'\[data-testid="stNumberInputContainer"\][^{]*\{([^}]*)\}', out)
    assert m, "không tìm thấy khối quy định ô nhập số"
    assert "background" not in m.group(1)


def test_khong_hoi_python_ve_che_do():
    """css() không nhận tham số chế độ — CSS tự chọn bằng media query."""
    import inspect
    assert list(inspect.signature(style.css).parameters) == []
    assert "prefers-color-scheme" in style.css()


# ------------------------------------------------- hai chế độ

def test_co_ca_hai_mau_giay_trong_cung_mot_chuoi():
    out = style.css()
    assert style.SURFACES["light"]["sheet"] in out
    assert style.SURFACES["dark"]["sheet"] in out


def test_che_do_toi_ghi_de_trong_media_query():
    out = style.css()
    i = out.index("prefers-color-scheme: dark")
    sau = out[i:]
    assert style.SURFACES["dark"]["sheet"] in sau
    # Màu giấy chế độ sáng phải khai báo TRƯỚC media query.
    assert style.SURFACES["light"]["sheet"] in out[:i]


def test_bien_mau_co_gia_tri_du_phong():
    """Trình duyệt chưa hỗ trợ color-mix vẫn phải có màu để dùng."""
    out = style.css()
    assert out.count("--jbi-rule:") >= 2, "thiếu khai báo dự phòng cho --jbi-rule"
    assert "rgba(" in out


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


def test_the_style_dong_mo_day_du():
    out = style.css().strip()
    assert out.startswith("<style>") and out.endswith("</style>")
    assert out.count("<style>") == 1 and out.count("</style>") == 1


def test_khong_con_cho_thay_the_nao_bo_sot():
    """Ngoặc nhọn đơn lẻ còn lại là dấu hiệu f-string thay thế bị lỗi."""
    out = style.css()
    assert "{light[" not in out and "{dark[" not in out
    assert "{{" not in out and "}}" not in out
