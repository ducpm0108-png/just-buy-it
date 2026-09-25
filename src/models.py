"""Các kiểu dữ liệu dùng chung cho toàn bộ dự án.

Tách riêng để mọi module khác cùng nói một "ngôn ngữ": module tính toán,
module lưu trữ và giao diện Streamlit đều nhận cùng các đối tượng này.
"""

from dataclasses import dataclass, field
from typing import Optional
import math

# Danh mục sản phẩm. Khoá dùng trong code, giá trị là nhãn hiện cho người dùng.
CATEGORIES = {
    "tech": "Công nghệ",
    "fashion": "Thời trang",
    "edu": "Giáo dục",
    "home": "Đồ gia dụng",
    "sport": "Thể thao",
    "beauty": "Mỹ phẩm",
    "food": "Ẩm thực",
    "other": "Khác",
}

# Nguồn biết đến món đồ, kèm điểm bốc đồng tương ứng (0 = lành nhất).
SOURCES = {
    "sale": ("Thấy đang sale", 1.0),
    "ad": ("Quảng cáo trên mạng", 0.8),
    "friend": ("Bạn bè dùng", 0.4),
    "need": ("Nhu cầu tự phát sinh", 0.0),
}


@dataclass
class Sale:
    """Thông tin về đợt giảm giá đang diễn ra, nếu có."""

    on: bool = False
    list_price: Optional[float] = None   # giá gốc trước khi giảm
    hours_left: float = math.inf         # số giờ còn lại của đợt giảm
    low_30d: Optional[float] = None      # giá thấp nhất 30 ngày qua

    def __post_init__(self) -> None:
        if not self.on:
            # Không có sale thì coi như không có hạn chót, tránh việc
            # yếu tố "sắp hết sale" bị tính oan.
            self.hours_left = math.inf


@dataclass
class Purchase:
    """Một món đồ đang được cân nhắc."""

    name: str
    price: float
    uses_per_month: float
    months: int
    category: str = "other"
    wanted_days: float = 10.0            # đã muốn món này bao nhiêu ngày
    source: str = "need"
    owns_similar: bool = False           # đã có món làm được việc tương tự
    desire: int = 5                      # mức thèm muốn 1-10
    used_price: Optional[float] = None   # giá mua cũ, cũng là giá bán lại
    sale: Sale = field(default_factory=Sale)

    def replace_price(self, new_price: float) -> "Purchase":
        """Trả về bản sao với giá khác. Dùng cho bài toán tìm giá mục tiêu."""
        from dataclasses import replace

        return replace(self, price=new_price)


@dataclass
class Finances:
    """Tình hình tài chính của người dùng tại thời điểm cân nhắc.

    Lưu kèm từng món đồ, vì một quyết định chỉ có thể đánh giá đúng
    trong hoàn cảnh tài chính lúc nó được đưa ra.
    """

    income: float          # thu nhập mỗi tháng
    fixed_costs: float     # chi phí cố định mỗi tháng
    savings: float         # tiền đang có

    # Số giờ làm việc quy ước trong một tháng: 22 ngày x 8 giờ.
    WORK_HOURS_PER_MONTH = 176

    @property
    def discretionary(self) -> float:
        """Tiền dư mỗi tháng, không bao giờ âm."""
        return max(self.income - self.fixed_costs, 0.0)

    @property
    def hourly_rate(self) -> float:
        """Thu nhập quy ra mỗi giờ làm việc."""
        return self.income / self.WORK_HOURS_PER_MONTH


@dataclass
class Goal:
    """Một việc khác người dùng đang muốn dùng tiền cho."""

    name: str
    amount: float


@dataclass
class Offer:
    """Một nơi bán món đồ."""

    store: str
    url: str = ""
    price: float = 0.0
