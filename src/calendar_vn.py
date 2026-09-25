"""Lịch giảm giá theo danh mục trên các sàn thương mại điện tử Việt Nam.

Đây là DỮ LIỆU THAM KHẢO, gom từ các đợt sale định kỳ, không phải dự báo
giá. Mục đích là trả lời câu "có nên chờ không" bằng một mốc thời gian cụ
thể thay vì cảm giác.

Chưa tính các đợt sale quanh Tết, vì Tết theo lịch âm nên mỗi năm một
ngày khác nhau; muốn thêm thì cần một thư viện chuyển đổi âm lịch.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Các ngày đôi lớn, dùng lại cho nhiều danh mục.
DOUBLE_66 = (6, 6, "Ngày đôi 6/6")
DOUBLE_99 = (9, 9, "Ngày đôi 9/9")
DOUBLE_1111 = (11, 11, "Ngày đôi 11/11")
DOUBLE_1212 = (12, 12, "Ngày đôi 12/12")


@dataclass
class Category:
    """Đặc điểm giảm giá của một danh mục."""

    label: str
    windows: List[Tuple[int, int, str]]   # (tháng, ngày, tên đợt)
    black_friday: bool
    note: str


CATEGORIES: Dict[str, Category] = {
    "tech": Category(
        "Công nghệ", [DOUBLE_99, DOUBLE_1111, DOUBLE_1212], True,
        "Đời cũ giảm mạnh nhất ngay sau khi hãng ra mẫu mới, "
        "thường vào tháng 9–10.",
    ),
    "fashion": Category(
        "Thời trang",
        [(3, 1, "Xả hàng cuối mùa đông"), (9, 1, "Xả hàng cuối mùa hè"),
         DOUBLE_1111, DOUBLE_1212], True,
        "Rẻ nhất vào cuối mùa, khoảng tháng 3 và tháng 9, "
        "khi cửa hàng xả đồ tồn.",
    ),
    "edu": Category(
        "Giáo dục",
        [(8, 15, "Ưu đãi đầu năm học"), (1, 1, "Ưu đãi đầu năm mới"),
         DOUBLE_1111], False,
        "Khoá học hay giảm vào đầu năm học (tháng 8–9) và đầu năm mới.",
    ),
    "home": Category(
        "Đồ gia dụng", [DOUBLE_66, DOUBLE_1111, DOUBLE_1212], True,
        "Đồ gia dụng lớn giảm sâu vào các ngày đôi và dịp cuối năm.",
    ),
    "sport": Category(
        "Thể thao", [(8, 15, "Xả hàng cuối hè"), DOUBLE_1111], True,
        "Đồ tập hay tăng giá vào tháng 1 vì ai cũng quyết tâm đầu năm. "
        "Cuối hè rẻ hơn.",
    ),
    "beauty": Category(
        "Mỹ phẩm",
        [(3, 8, "Ưu đãi 8/3"), DOUBLE_1111, DOUBLE_1212], False,
        "Hay có mã giảm sâu vào 8/3 và các ngày đôi; "
        "để ý hạn sử dụng khi giá quá rẻ.",
    ),
    "food": Category(
        "Ẩm thực",
        [(12, 20, "Mùa lễ cuối năm"), DOUBLE_1111], False,
        "Đồ ăn ít giảm giá theo đợt; mua theo nhu cầu thay vì chờ sale.",
    ),
    "other": Category(
        "Khác", [DOUBLE_66, DOUBLE_1111, DOUBLE_1212], False,
        "Các ngày đôi là mốc giảm giá đáng chờ nhất trên sàn.",
    ),
}

# Mức giảm mà một đợt sale lớn có thể mang lại. Cần giảm sâu hơn mức này
# thì chờ sale không giải quyết được vấn đề.
PLAUSIBLE_SALE_CUT = 0.30

# Khoảng thời gian còn đáng chờ, tính theo ngày.
WORTH_WAITING_DAYS = 60


def black_friday(year: int) -> date:
    """Ngày Black Friday của một năm: thứ Sáu ngay sau thứ Năm thứ tư của tháng 11."""
    d = date(year, 11, 1)
    thursdays = 0
    while d.month == 11:
        if d.weekday() == 3:      # 3 = thứ Năm
            thursdays += 1
            if thursdays == 4:
                break
        d += timedelta(days=1)
    return d + timedelta(days=1)


@dataclass
class SaleWindow:
    """Một đợt giảm giá sắp tới."""

    name: str
    when: date
    days_away: int


def next_sale_window(category: str,
                     today: Optional[date] = None) -> Optional[SaleWindow]:
    """Đợt giảm giá lớn gần nhất của danh mục, tính từ hôm nay.

    Xét các mốc của cả năm nay và năm sau, để cuối tháng 12 vẫn tìm ra
    được đợt của năm kế tiếp.
    """
    today = today or date.today()
    if isinstance(today, datetime):
        today = today.date()

    cat = CATEGORIES.get(category, CATEGORIES["other"])
    candidates = []

    for year in (today.year, today.year + 1):
        for month, day, name in cat.windows:
            candidates.append((name, date(year, month, day)))
        if cat.black_friday:
            candidates.append(("Black Friday", black_friday(year)))

    upcoming = [(n, w, (w - today).days) for n, w in candidates if (w - today).days >= 0]
    if not upcoming:
        return None

    name, when, days = min(upcoming, key=lambda t: t[2])
    return SaleWindow(name=name, when=when, days_away=days)


def timing_advice(category: str, needed_cut: Optional[float],
                  today: Optional[date] = None) -> Tuple[Optional[SaleWindow], str]:
    """Kết hợp lịch sale với mức giảm giá đang cần.

    Trả về (đợt sale gần nhất, lời khuyên). Lời khuyên nói thẳng khi mức
    cần giảm sâu hơn những gì một đợt sale thường mang lại — lúc đó vấn
    đề là ngân sách, không phải giá.
    """
    window = next_sale_window(category, today)
    cat = CATEGORIES.get(category, CATEGORIES["other"])

    if window is None:
        return None, cat.note

    if needed_cut is None:
        return window, cat.note

    if window.days_away > WORTH_WAITING_DAYS:
        return window, ("Còn xa, đừng lấy đó làm lý do trì hoãn "
                        "nếu bạn thật sự cần món này.")

    if needed_cut <= PLAUSIBLE_SALE_CUT:
        return window, (
            f"Mức giảm {round(needed_cut * 100)}% bạn cần là trong tầm một "
            f"đợt sale lớn. Chờ {window.days_away} ngày tới đợt này có thể vừa đủ."
        )

    return window, (
        f"Cần giảm tới {round(needed_cut * 100)}%, sâu hơn mức một đợt sale "
        "thường có. Chờ sale không giải quyết được khoảng cách này — "
        "vấn đề là ngân sách, không phải giá."
    )
