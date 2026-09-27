"""Kiểm thử phần hướng dẫn nhập/xuất dữ liệu.

`app.py` import streamlit và chạy cả app khi được import, nên không gọi
`data_help_body()` trực tiếp được. Thay vào đó rà trên mã nguồn — và rà
đúng những điều dễ mục ruỗng âm thầm: **hướng dẫn nói một đằng, mã làm một
nẻo**. Một dòng hướng dẫn sai còn tệ hơn không có hướng dẫn, vì người dùng
tin nó rồi mất dữ liệu.
"""

import pathlib

import pytest

GOC = pathlib.Path(__file__).resolve().parents[1]
APP = (GOC / "app.py").read_text(encoding="utf-8")
DB = (GOC / "src" / "db.py").read_text(encoding="utf-8")


# ------------------------------------------- hướng dẫn khớp với hành vi thật

def test_huong_dan_noi_du_lieu_vao_ho_so_dang_chon():
    """Điều bất ngờ thứ nhất: dữ liệu vào hồ sơ đang chọn ở thanh bên, không
    phải hồ sơ ghi trong file. Hướng dẫn phải nói, và mã phải đúng thế."""
    assert "hồ sơ đang chọn ở thanh bên" in APP
    # App truyền tên hồ sơ hiện tại vào, nên tham số `profile` của file bị bỏ.
    assert "data, profile=profile," in APP


def test_huong_dan_noi_nap_file_ghi_de_trong_so():
    """Điều bất ngờ thứ hai: settings trong file ghi đè settings đang có, ở
    CẢ HAI cách nạp — vì vòng lặp ghi settings nằm ngoài nhánh `replace`."""
    assert "Cả hai cách đều ghi đè" in APP
    assert "ON CONFLICT(profile, key) DO UPDATE" in DB


def test_huong_dan_noi_thay_the_toan_bo_xoa_ca_cai_dat():
    assert "xoá sạch dữ liệu của hồ sơ đang chọn" in APP
    assert 'conn.execute("DELETE FROM settings WHERE profile = ?", (target,))' in DB


def test_huong_dan_canh_bao_nhan_doi_khi_nap_lai():
    """Nạp lại cùng file ở chế độ thêm vào thì món bị nhân đôi — mã không
    chống trùng, nên hướng dẫn phải nói trước."""
    assert "nhân đôi" in APP
    assert "INSERT OR IGNORE INTO items" not in DB  # không có chống trùng


def test_huong_dan_canh_bao_file_chua_so_lieu_tai_chinh():
    """File xuất ra có thu nhập, chi phí cố định, tiền đang có."""
    for cot in ("income", "fixed_costs", "savings"):
        assert cot in DB
    # Rà cụm nằm gọn trong một chuỗi; câu đầy đủ bị ngắt dòng giữa hai chuỗi.
    assert "đừng đẩy lên GitHub" in APP


# ------------------------------------------- chỗ đặt hộp thoại

def test_hop_thoai_goi_o_cap_ngoai_cung_khong_long_trong_tab():
    """Hộp thoại phải gọi trước khi dựng các tab.

    Streamlit chạy thân của MỌI tab ở mỗi lần vẽ lại, nên gọi trong
    `with tab_profile:` thì hộp thoại nằm lồng trong khối tab.
    """
    goi = APP.index("    show_data_help()")
    tabs = APP.index("tab_eval, tab_wait, tab_profile, tab_weights = st.tabs(")
    assert goi < tabs


def test_co_nut_hoi_mo_lai_huong_dan():
    assert 'st.session_state.show_data_help = True' in APP
    assert 'help="Hướng dẫn nhập/xuất dữ liệu"' in APP


def test_the_lan_dau_dung_cung_mot_khoa_de_doc_va_ghi():
    """Đọc một khoá, ghi một khoá khác thì thẻ hiện lại mãi mãi."""
    assert APP.count('"data_help_seen"') == 2
    assert 'db.get_setting(profile, "data_help_seen"' in APP
    assert 'db.set_setting(profile, "data_help_seen", "1"' in APP


def test_ban_du_phong_cho_streamlit_cu():
    """Streamlit cũ không có st.dialog; phải còn nhánh expander."""
    assert APP.count("def show_data_help()") == 2
    assert 'hasattr(st, "dialog")' in APP


# ------------------------------------------- nội dung dùng lại được

@pytest.mark.parametrize("muc", ["1. Tải dữ liệu về", "2. Nạp dữ liệu từ file",
                                 "Lưu ý"])
def test_huong_dan_co_du_cac_muc(muc):
    assert muc in APP


def test_noi_dung_tach_rieng_de_dung_lai():
    """Một thân hàm, ba chỗ gọi: thẻ lần đầu, hộp thoại, bản dự phòng."""
    assert APP.count("def data_help_body()") == 1
    assert APP.count("data_help_body()") == 4  # 1 định nghĩa + 3 lần gọi
