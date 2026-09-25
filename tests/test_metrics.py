"""Kiểm thử các chỉ số chi phí.

Mỗi test kiểm tra một điều, và các con số kỳ vọng đều tính được bằng tay
để nếu test sai thì biết ngay là sai ở đâu.
"""

import math
import pytest

from src import metrics
from src.models import Finances, Goal, Purchase, Sale


@pytest.fixture
def headphones():
    """Món đồ mẫu: tai nghe 4,5 triệu, dùng 20 lần/tháng trong 24 tháng."""
    return Purchase(name="Tai nghe", price=4_500_000,
                    uses_per_month=20, months=24, category="tech")


@pytest.fixture
def student():
    """Tài chính mẫu: thu 8 triệu, chi cố định 5 triệu, có 12 triệu."""
    return Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)


def test_total_uses(headphones):
    assert metrics.total_uses(headphones) == 480      # 20 x 24


def test_cost_per_use(headphones):
    # 4.500.000 / 480 = 9.375
    assert metrics.cost_per_use(headphones) == pytest.approx(9375)


def test_cost_per_use_khi_chua_biet_so_lan_dung(headphones):
    """Chưa cho biết số lần dùng thì trả vô cực, không phải 0."""
    headphones.uses_per_month = 0
    assert math.isinf(metrics.cost_per_use(headphones))


def test_cost_per_use_giam_khi_dung_nhieu_hon(headphones):
    """Cùng một món, dùng nhiều hơn thì giá mỗi lần dùng phải giảm."""
    it = metrics.cost_per_use(headphones)
    headphones.uses_per_month = 40
    assert metrics.cost_per_use(headphones) < it


def test_work_hours(headphones, student):
    # 8.000.000 / 176 giờ = 45.454,5 mỗi giờ; 4.500.000 / 45.454,5 = 99 giờ
    assert metrics.work_hours_to_afford(headphones, student) == pytest.approx(99, abs=0.5)


def test_share_of_discretionary(headphones, student):
    # tiền dư = 8tr - 5tr = 3tr; 4,5tr / 3tr = 1,5 tức 150%
    assert metrics.share_of_discretionary(headphones, student) == pytest.approx(1.5)


def test_share_khi_khong_con_tien_du(headphones):
    """Chi phí cố định vượt thu nhập thì không tính được tỷ lệ."""
    broke = Finances(income=5_000_000, fixed_costs=6_000_000, savings=0)
    assert broke.discretionary == 0
    assert math.isinf(metrics.share_of_discretionary(headphones, broke))


def test_savings_coverage(headphones, student):
    # 12tr / 4,5tr = 2,67 lần
    assert metrics.savings_coverage(headphones, student) == pytest.approx(2.667, abs=0.01)


def test_opportunity_cost():
    """1 triệu để 5 năm với lãi 6%/năm thành khoảng 1,338 triệu."""
    assert metrics.opportunity_cost(1_000_000) == pytest.approx(1_338_225, abs=1)


def test_opportunity_cost_khong_lai_thi_giu_nguyen():
    assert metrics.opportunity_cost(1_000_000, rate=0) == 1_000_000


# ----------------------------------------------------------- giảm giá

def test_discount_tinh_dung():
    p = Purchase("x", 4_500_000, 20, 24,
                 sale=Sale(on=True, list_price=5_490_000))
    amount, pct, _, fake = metrics.discount_info(p)
    assert amount == 990_000
    assert pct == pytest.approx(0.18, abs=0.005)
    assert fake is False


def test_khong_co_sale_thi_khong_co_giam():
    p = Purchase("x", 4_500_000, 20, 24, sale=Sale(on=False, list_price=5_490_000))
    amount, pct, _, _ = metrics.discount_info(p)
    assert amount == 0 and pct == 0


def test_phat_hien_giam_gia_ao():
    """Giá sale không rẻ hơn đáy 30 ngày thì là giảm giá ảo."""
    p = Purchase("x", 4_500_000, 20, 24,
                 sale=Sale(on=True, list_price=5_490_000, low_30d=4_200_000))
    *_, fake = metrics.discount_info(p)
    assert fake is True


def test_giam_gia_that_khi_re_hon_day_30_ngay():
    p = Purchase("x", 4_000_000, 20, 24,
                 sale=Sale(on=True, list_price=5_490_000, low_30d=4_500_000))
    _, _, vs_low, fake = metrics.discount_info(p)
    assert fake is False
    assert vs_low == pytest.approx(0.111, abs=0.01)   # rẻ hơn đáy 11%


def test_gia_bang_dung_day_30_ngay_van_tinh_la_ao():
    """Trường hợp biên: bằng đúng đáy thì không rẻ hơn, nên vẫn là ảo."""
    p = Purchase("x", 4_500_000, 20, 24,
                 sale=Sale(on=True, list_price=5_000_000, low_30d=4_500_000))
    *_, fake = metrics.discount_info(p)
    assert fake is True


# ----------------------------------------------------------- quy đổi

def test_quy_doi_don_vi():
    units = dict(metrics.in_reference_units(500_000))
    assert units["bát phở"] == 10          # 500.000 / 50.000
    assert units["ly cà phê"] == 14        # làm tròn từ 14,3


def test_gia_qua_nho_thi_khong_quy_doi():
    assert metrics.in_reference_units(1_000) == []


def test_so_sanh_voi_muc_tieu():
    goals = [Goal("Quỹ dự phòng", 15_000_000), Goal("Khoá học", 3_000_000)]
    result = dict(metrics.compare_to_goals(4_500_000, goals))
    assert result["Quỹ dự phòng"] == pytest.approx(0.3)    # bằng 30% mục tiêu
    assert result["Khoá học"] == pytest.approx(1.5)        # bằng 1,5 lần


def test_muc_tieu_khong_co_so_tien_bi_bo_qua():
    assert metrics.compare_to_goals(1_000_000, [Goal("Chưa rõ", 0)]) == []
