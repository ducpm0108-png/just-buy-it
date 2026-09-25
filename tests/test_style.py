"""Kiểm thử lớp trang trí.

`style.css()` là hàm thuần nên kiểm thử được mà không cần chạy Streamlit.
Các test ở đây chủ yếu chặn hai loại lỗi: quên một chế độ màu, và bám vào
tên class do Streamlit sinh ra (sẽ vỡ khi Streamlit cập nhật).
"""

import re
import pytest

from src import style


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_moi_che_do_dung_dung_bang_mau_cua_no(mode):
    out = style.css(mode)
    c = style.PALETTE[mode]
    assert c["sheet"] in out
    assert c["rule"] in out
    assert c["accent"] in out


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_hai_che_do_khong_lan_mau_cua_nhau(mode):
    other = "dark" if mode == "light" else "light"
    out = style.css(mode)
    # Màu giấy của chế độ kia không được xuất hiện.
    assert style.PALETTE[other]["sheet"] not in out


def test_che_do_la_thi_dung_sang():
    assert style.css("không-tồn-tại") == style.css("light")


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_khong_bam_vao_class_do_streamlit_sinh(mode):
    """Bám vào `st-emotion-cache-*` là giao diện sẽ vỡ ở bản Streamlit sau.

    Chỉ được dùng `data-testid` và `st-key-*` — hai thứ Streamlit giữ ổn định.
    """
    out = style.css(mode)
    assert "st-emotion-cache" not in out
    assert not re.search(r"\.e[a-z0-9]{8,}\b", out), "có vẻ đang bám vào class băm"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_an_nut_tang_giam_cua_o_so(mode):
    out = style.css(mode)
    assert "stNumberInputStepUp" in out
    assert "stNumberInputStepDown" in out
    assert "display: none" in out


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_co_nap_font_va_dung_font_do(mode):
    out = style.css(mode)
    assert "@import" in out and "fonts.googleapis.com" in out
    assert "Be Vietnam Pro" in out
    assert "IBM Plex Mono" in out


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_font_du_phong_co_font_chua_ky_hieu_dong(mode):
    """₫ là ký hiệu nhiều font đơn cách không có; cần font dự phòng chứa nó."""
    assert "DejaVu Sans Mono" in style.css(mode)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_style_dong_mo_day_du(mode):
    out = style.css(mode).strip()
    assert out.startswith("<style>") and out.endswith("</style>")
    assert out.count("<style>") == 1 and out.count("</style>") == 1


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_khong_con_cho_thay_the_nao_bo_sot(mode):
    """Chuỗi f-string còn dấu ngoặc nhọn đơn lẻ là dấu hiệu thay thế bị lỗi."""
    out = style.css(mode)
    assert "{c[" not in out
    assert "{{" not in out and "}}" not in out
