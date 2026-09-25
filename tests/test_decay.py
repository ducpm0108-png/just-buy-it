"""Kiểm thử phần đo độ nguội của ham muốn."""

from datetime import datetime, timedelta
import pytest

from src import decay
from src.decay import Rating

MOC = datetime(2026, 9, 1, 10, 0)


def cap(days: float, v0: int, v1: int):
    """Tạo một cặp lần chấm cách nhau `days` ngày."""
    return [Rating(MOC, v0), Rating(MOC + timedelta(days=days), v1)]


def test_giam_dung_mot_nua_thi_ban_ra_bang_khoang_cach():
    """8 xuống 4 trong 7 ngày thì thời gian bán rã đúng bằng 7 ngày."""
    first, last = cap(7, 8, 4)
    assert decay.half_life_from_pair(first, last) == pytest.approx(7)


def test_giam_mot_phan_tu_thi_ban_ra_bang_nua_khoang_cach():
    """8 xuống 2 là giảm hai lần liên tiếp, nên bán rã bằng nửa thời gian."""
    first, last = cap(14, 8, 2)
    assert decay.half_life_from_pair(first, last) == pytest.approx(7)


def test_giam_cham_thi_ban_ra_dai_hon():
    cham = decay.half_life_from_pair(*cap(7, 8, 7))
    nhanh = decay.half_life_from_pair(*cap(7, 8, 2))
    assert cham > nhanh


def test_ham_muon_tang_thi_khong_tinh_duoc():
    assert decay.half_life_from_pair(*cap(7, 5, 8)) is None


def test_ham_muon_khong_doi_thi_khong_tinh_duoc():
    assert decay.half_life_from_pair(*cap(7, 6, 6)) is None


def test_diem_bang_0_thi_khong_tinh_duoc():
    assert decay.half_life_from_pair(*cap(7, 8, 0)) is None


def test_cung_thoi_diem_thi_khong_tinh_duoc():
    assert decay.half_life_from_pair(*cap(0, 8, 4)) is None


# ------------------------------------------------- ước lượng trung bình

def test_uoc_luong_tu_nhieu_mon():
    series = [cap(7, 8, 4), cap(7, 8, 4), cap(14, 8, 4)]
    hl = decay.estimate_half_life(series)
    assert hl.from_data is True
    assert hl.sample_size == 3
    # trung bình của 7, 7, 14
    assert hl.days == pytest.approx((7 + 7 + 14) / 3)


def test_chua_co_du_lieu_thi_dung_mac_dinh():
    hl = decay.estimate_half_life([], default_days=10)
    assert hl.from_data is False
    assert hl.days == 10
    assert hl.sample_size == 0


def test_mon_chi_cham_mot_lan_khong_duoc_tinh():
    hl = decay.estimate_half_life([[Rating(MOC, 8)]], default_days=10)
    assert hl.from_data is False


def test_mon_khong_tinh_duoc_bi_loai_khoi_trung_binh():
    """Món có ham muốn tăng bị loại, chỉ còn món giảm góp vào."""
    hl = decay.estimate_half_life([cap(7, 8, 4), cap(7, 4, 9)])
    assert hl.sample_size == 1
    assert hl.days == pytest.approx(7)


# ------------------------------------------------- dự đoán về sau

def test_du_doan_sau_dung_mot_ban_ra():
    """Thèm muốn 8/10, sau đúng một chu kỳ bán rã còn khoảng một nửa."""
    assert decay.desire_after(8, days=10, half_life_days=10) == pytest.approx(0.4)


def test_du_doan_ngay_luc_nay_bang_diem_hien_tai():
    assert decay.desire_after(8, days=0, half_life_days=10) == pytest.approx(0.8)


def test_cho_cang_lau_kha_nang_con_muon_cang_thap():
    a = decay.desire_after(8, days=7, half_life_days=10)
    b = decay.desire_after(8, days=30, half_life_days=10)
    assert b < a


def test_ket_qua_luon_trong_khoang_0_1():
    for desire in range(1, 11):
        for days in (0, 1, 7, 100):
            v = decay.desire_after(desire, days, half_life_days=10)
            assert 0 <= v <= 1
