"""Các chỉ số chi phí thật của một món đồ.

Mỗi hàm nhận dữ liệu đã có và trả về một con số, không in ra gì và không
phụ thuộc giao diện. Nhờ vậy có thể kiểm thử từng hàm riêng lẻ.

Chỉ số quan trọng nhất là `cost_per_use`: cùng một món đồ, dùng 20 lần
mỗi tháng và dùng 2 lần mỗi tháng là hai quyết định hoàn toàn khác nhau.
"""

from dataclasses import dataclass
from typing import Optional
import math

from .models import Finances, Purchase

# Lãi suất giả định khi tính chi phí cơ hội: 6% một năm.
ANNUAL_RETURN = 0.06
OPPORTUNITY_YEARS = 5


@dataclass
class Metrics:
    """Kết quả tính toán cho một món đồ."""

    total_uses: float
    cost_per_use: float
    work_hours: float
    discretionary: float
    share_discretionary: float
    coverage: float
    months_to_rebuild: float
    opportunity_5y: float
    discount: float = 0.0
    discount_pct: float = 0.0
    vs_low_30d: Optional[float] = None
    fake_discount: bool = False


def total_uses(p: Purchase) -> float:
    """Tổng số lần dùng dự kiến trong suốt thời gian sở hữu."""
    return p.uses_per_month * p.months


def cost_per_use(p: Purchase) -> float:
    """Giá phải trả cho mỗi lần thật sự dùng món đồ.

    Chưa cho biết số lần dùng thì trả về vô cực: chưa trả lời được,
    và đó là thông tin đúng hơn là trả về 0.
    """
    uses = total_uses(p)
    return p.price / uses if uses > 0 else math.inf


def work_hours_to_afford(p: Purchase, f: Finances) -> float:
    """Số giờ phải đi làm để mua được món đồ."""
    rate = f.hourly_rate
    return p.price / rate if rate > 0 else math.inf


def share_of_discretionary(p: Purchase, f: Finances) -> float:
    """Giá món đồ chiếm bao nhiêu phần tiền dư một tháng.

    Trả về vô cực khi không còn tiền dư, tức chi phí cố định đã bằng
    hoặc vượt thu nhập.
    """
    disc = f.discretionary
    return p.price / disc if disc > 0 else math.inf


def savings_coverage(p: Purchase, f: Finances) -> float:
    """Tiền đang có mua được món đồ bao nhiêu lần."""
    return f.savings / p.price if p.price > 0 else math.inf


def months_to_rebuild(p: Purchase, f: Finances) -> float:
    """Số tháng để dành lại đủ số tiền vừa tiêu."""
    disc = f.discretionary
    return p.price / disc if disc > 0 else math.inf


def opportunity_cost(price: float, years: int = OPPORTUNITY_YEARS,
                     rate: float = ANNUAL_RETURN) -> float:
    """Số tiền này sẽ thành bao nhiêu nếu để dành và sinh lãi kép."""
    return price * (1 + rate) ** years


def discount_info(p: Purchase) -> tuple:
    """Phân tích đợt giảm giá.

    Trả về (số tiền giảm, tỷ lệ giảm, so với đáy 30 ngày, có phải giảm ảo).

    "Giảm ảo" là khi giá sale không hề thấp hơn mức thấp nhất của 30 ngày
    qua — dấu hiệu của chiêu nâng giá gốc lên rồi giảm lại.
    """
    amount = 0.0
    pct = 0.0
    vs_low = None
    fake = False

    if p.sale.on and p.sale.list_price and p.sale.list_price > p.price:
        amount = p.sale.list_price - p.price
        pct = amount / p.sale.list_price

    if p.sale.on and p.sale.low_30d is not None and p.sale.low_30d > 0:
        vs_low = (p.sale.low_30d - p.price) / p.sale.low_30d
        fake = p.price >= p.sale.low_30d

    return amount, pct, vs_low, fake


def compute(p: Purchase, f: Finances) -> Metrics:
    """Tính tất cả chỉ số một lượt. Đây là hàm giao diện Streamlit gọi."""
    amount, pct, vs_low, fake = discount_info(p)
    return Metrics(
        total_uses=total_uses(p),
        cost_per_use=cost_per_use(p),
        work_hours=work_hours_to_afford(p, f),
        discretionary=f.discretionary,
        share_discretionary=share_of_discretionary(p, f),
        coverage=savings_coverage(p, f),
        months_to_rebuild=months_to_rebuild(p, f),
        opportunity_5y=opportunity_cost(p.price),
        discount=amount,
        discount_pct=pct,
        vs_low_30d=vs_low,
        fake_discount=fake,
    )


# Đơn vị quy đổi để con số dễ cảm nhận hơn.
REFERENCE_UNITS = [
    ("bát phở", 50_000),
    ("ly cà phê", 35_000),
    ("tháng Spotify", 59_000),
    ("lần đổ xăng", 80_000),
]


def in_reference_units(price: float) -> list:
    """Quy giá ra các đơn vị quen thuộc. Bỏ qua đơn vị nào chưa đủ 1."""
    out = []
    for name, unit_price in REFERENCE_UNITS:
        qty = round(price / unit_price)
        if qty >= 1:
            out.append((name, qty))
    return out


def compare_to_goals(price: float, goals: list) -> list:
    """So giá món đồ với những việc khác người dùng muốn dùng tiền cho.

    Trả về danh sách (tên mục tiêu, tỷ lệ). Tỷ lệ 0.3 nghĩa là món đồ
    bằng 30% mục tiêu đó; tỷ lệ 1.5 nghĩa là bằng 1,5 lần.
    """
    out = []
    for g in goals:
        if g.amount > 0:
            out.append((g.name, price / g.amount))
    return out
