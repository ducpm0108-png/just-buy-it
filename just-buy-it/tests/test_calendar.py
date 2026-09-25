"""Kiểm thử lịch giảm giá theo danh mục."""

from datetime import date
import pytest

from src import calendar_vn as cal


# Black Friday thật của các năm, tra từ lịch.
BLACK_FRIDAYS = {
    2026: date(2026, 11, 27),
    2027: date(2027, 11, 26),
    2028: date(2028, 11, 24),
    2029: date(2029, 11, 23),
}


@pytest.mark.parametrize("year,expected", BLACK_FRIDAYS.items())
def test_black_friday_dung_ngay(year, expected):
    assert cal.black_friday(year) == expected


@pytest.mark.parametrize("year", range(2026, 2041))
def test_black_friday_luon_la_thu_sau_cuoi_thang_11(year):
    d = cal.black_friday(year)
    assert d.weekday() == 4          # 4 = thứ Sáu
    assert d.month == 11
    assert d.day >= 23               # không thể sớm hơn 23/11


def test_dot_sale_gan_nhat_luon_o_tuong_lai():
    """Với mọi ngày trong năm và mọi danh mục, đợt tìm được phải chưa qua."""
    for category in cal.CATEGORIES:
        for month in range(1, 13):
            today = date(2026, month, 15)
            w = cal.next_sale_window(category, today)
            assert w is not None
            assert w.days_away >= 0
            assert w.when >= today


def test_cac_danh_muc_cho_ket_qua_khac_nhau():
    """Lịch phải thật sự phụ thuộc danh mục, không phải trả về một mốc chung."""
    today = date(2027, 2, 10)
    ket_qua = {c: cal.next_sale_window(c, today).name for c in cal.CATEGORIES}
    assert len(set(ket_qua.values())) > 1

    # Đầu tháng 2: thời trang chờ đợt xả đồ đông, mỹ phẩm chờ 8/3.
    assert ket_qua["fashion"] == "Xả hàng cuối mùa đông"
    assert ket_qua["beauty"] == "Ưu đãi 8/3"


def test_cuoi_nam_tim_sang_dot_cua_nam_sau():
    """Ngày 15/12 đã qua hết các mốc trong năm, phải tìm sang năm sau."""
    w = cal.next_sale_window("tech", date(2026, 12, 15))
    assert w.when.year == 2027


def test_danh_muc_la_thi_dung_mac_dinh():
    w = cal.next_sale_window("khong-ton-tai", date(2026, 9, 25))
    assert w is not None


def test_ngay_dung_dot_sale_thi_con_0_ngay():
    w = cal.next_sale_window("tech", date(2026, 11, 11))
    assert w.days_away == 0
    assert w.name == "Ngày đôi 11/11"


# ------------------------------------------------- lời khuyên thời điểm

def test_muc_giam_nho_thi_khuyen_cho_sale():
    _, advice = cal.timing_advice("tech", needed_cut=0.15,
                                  today=date(2026, 10, 20))
    assert "trong tầm một đợt sale" in advice


def test_muc_giam_sau_thi_noi_thang_la_van_de_ngan_sach():
    _, advice = cal.timing_advice("tech", needed_cut=0.60,
                                  today=date(2026, 10, 20))
    assert "ngân sách" in advice


def test_dot_sale_con_xa_thi_khuyen_dung_tri_hoan():
    """Tháng 1, đợt gần nhất của đồ công nghệ còn hơn 60 ngày."""
    w, advice = cal.timing_advice("tech", needed_cut=0.10,
                                  today=date(2027, 1, 5))
    assert w.days_away > cal.WORTH_WAITING_DAYS
    assert "trì hoãn" in advice


def test_khong_can_giam_gia_thi_chi_tra_ve_ghi_chu_danh_muc():
    _, advice = cal.timing_advice("sport", needed_cut=None,
                                  today=date(2026, 9, 25))
    assert advice == cal.CATEGORIES["sport"].note
