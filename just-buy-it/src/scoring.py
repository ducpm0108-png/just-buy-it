"""Mô hình tính điểm: áp lực tài chính và mức độ bốc đồng.

Hai trục tách biệt, vì đó là hai vấn đề khác nhau cần hai lời khuyên khác
nhau: "không đủ tiền" và "đang mua quá vội". Gộp thành một điểm tổng sẽ
làm mất sự phân biệt đó.

Mỗi yếu tố được quy về thang 0–1 bằng một công thức ghi rõ trong FACTORS,
rồi nhân với trọng số. Điểm cuối là trung bình có trọng số, nhân 100.
Trọng số không cần cộng lại bằng 100 — chỉ tỷ lệ giữa chúng là quan trọng.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import math

from .metrics import Metrics, compute
from .models import Finances, Purchase, SOURCES


def clamp(x: float, low: float = 0.0, high: float = 1.0) -> float:
    """Ép một số về trong khoảng [low, high]."""
    return max(low, min(high, x))


@dataclass
class Weights:
    """Bộ trọng số và các mốc so sánh của mô hình.

    Người dùng xem và chỉnh được toàn bộ những con số này trong giao diện.
    Giá trị mặc định ở đây là điểm xuất phát, không phải chân lý — cách
    hiệu chỉnh xem trong README.
    """

    strain: Dict[str, float] = field(default_factory=lambda: {
        "share": 35, "cpu": 25, "cover": 25, "hours": 15,
    })
    impulse: Dict[str, float] = field(default_factory=lambda: {
        "recency": 30, "source": 20, "owns": 15,
        "desire": 15, "urgency": 15, "night": 5,
    })
    threshold: float = 40          # điểm từ mức này trở lên được coi là cao
    ref_cost_per_use: float = 35_000   # mốc giá mỗi lần dùng: một ly cà phê
    default_half_life: float = 10      # ngày, dùng khi chưa có dữ liệu người dùng


# Ba bộ trọng số dựng sẵn theo nhóm người dùng.
PRESETS = {
    "student": Weights(
        strain={"share": 30, "cpu": 15, "cover": 40, "hours": 15},
        impulse={"recency": 30, "source": 20, "owns": 15,
                 "desire": 15, "urgency": 15, "night": 5},
        threshold=35,
    ),
    "saver": Weights(
        strain={"share": 40, "cpu": 15, "cover": 20, "hours": 25},
        impulse={"recency": 25, "source": 20, "owns": 20,
                 "desire": 15, "urgency": 15, "night": 5},
        threshold=30,
    ),
    "stable": Weights(
        strain={"share": 30, "cpu": 35, "cover": 15, "hours": 20},
        impulse={"recency": 35, "source": 25, "owns": 20,
                 "desire": 10, "urgency": 10, "night": 0},
        threshold=45,
    ),
}

# Mô tả từng yếu tố: nhãn hiện cho người dùng, tên ngắn cho hoá đơn,
# và công thức quy về thang 0-1 viết bằng lời.
FACTORS = {
    "strain": [
        ("share", "Phần tiền dư mỗi tháng", "tiền dư",
         "Giá chia tiền dư hàng tháng, tối đa ở 100%."),
        ("cpu", "Giá mỗi lần dùng", "mỗi lần dùng",
         "c chia (c + mốc). Bằng mốc thì 0,5; đắt gấp ba mốc thì 0,75."),
        ("cover", "Tiền đang có", "tiền đang có",
         "Có ít hơn giá món: 1. Có gấp đôi: 0,5. Gấp bốn: 0,25."),
        ("hours", "Số giờ đi làm", "giờ làm",
         "h chia (h + 40). Đúng một tuần làm việc thì 0,5."),
    ],
    "impulse": [
        ("recency", "Mới muốn gần đây", "mới muốn",
         "0,5 mũ (số ngày chia 7). Sau một tuần còn 0,5."),
        ("source", "Nguồn biết đến", "nguồn",
         "Sale 1, quảng cáo 0,8, bạn bè 0,4, tự có nhu cầu 0."),
        ("owns", "Đã có món thay thế", "đã có món khác",
         "Có thì 1, không thì 0."),
        ("desire", "Thèm muốn quá mức", "thèm muốn",
         "(điểm trừ 5) chia 5. Từ 5/10 trở xuống là 0."),
        ("urgency", "Áp lực hết hạn giảm giá", "sắp hết sale",
         "Sale hết trong 7 ngày: 1 trừ (giờ còn lại chia 168)."),
        ("night", "Đang cân nhắc lúc khuya", "giờ khuya",
         "Từ 22 giờ đến 5 giờ sáng thì 1."),
    ],
}


@dataclass
class Score:
    """Điểm của một trục, kèm phần đóng góp của từng yếu tố."""

    value: int
    parts: List[tuple]   # [(khoá, tên ngắn, số điểm đóng góp), ...]

    def top_parts(self, n: int = 3, minimum: float = 1.0) -> List[tuple]:
        """Các yếu tố đang kéo điểm lên nhiều nhất, để hiện trên hoá đơn."""
        return [p for p in self.parts if p[2] >= minimum][:n]


def strain_factors(p: Purchase, f: Finances, w: Weights,
                   m: Optional[Metrics] = None) -> Dict[str, float]:
    """Quy bốn yếu tố áp lực tài chính về thang 0-1."""
    m = m or compute(p, f)
    c, h = m.cost_per_use, m.work_hours

    return {
        "share": clamp(m.share_discretionary) if math.isfinite(m.share_discretionary) else 1.0,
        "cpu": c / (c + w.ref_cost_per_use) if math.isfinite(c) else 1.0,
        "cover": 1.0 if m.coverage <= 1 else (1.0 / m.coverage if math.isfinite(m.coverage) else 0.0),
        "hours": h / (h + 40) if math.isfinite(h) else 1.0,
    }


def impulse_factors(p: Purchase, now: Optional[datetime] = None) -> Dict[str, float]:
    """Quy sáu yếu tố bốc đồng về thang 0-1.

    `now` nhận vào thay vì gọi datetime.now() bên trong, để yếu tố
    "giờ khuya" kiểm thử được mà không phụ thuộc lúc chạy test.
    """
    now = now or datetime.now()
    hours_left = p.sale.hours_left

    urgency = 0.0
    if p.sale.on and math.isfinite(hours_left) and hours_left < 168:
        urgency = clamp(1 - hours_left / 168)

    return {
        "recency": 0.5 ** (p.wanted_days / 7),
        "source": SOURCES.get(p.source, ("", 0.0))[1],
        "owns": 1.0 if p.owns_similar else 0.0,
        "desire": clamp((p.desire - 5) / 5),
        "urgency": urgency,
        "night": 1.0 if (now.hour >= 22 or now.hour < 5) else 0.0,
    }


def score_of(group: str, factors: Dict[str, float], w: Weights) -> Score:
    """Gộp các yếu tố đã quy về 0-1 thành một điểm 0-100."""
    weights = getattr(w, group)
    total_weight = sum(max(0.0, weights.get(k, 0.0)) for k, _, _, _ in FACTORS[group])

    parts = []
    running = 0.0
    for key, _label, short, _how in FACTORS[group]:
        wi = max(0.0, weights.get(key, 0.0))
        pts = (wi * factors[key] / total_weight * 100) if total_weight > 0 else 0.0
        running += pts
        parts.append((key, short, pts))

    parts.sort(key=lambda t: -t[2])
    return Score(value=round(clamp(running, 0, 100)), parts=parts)


def strain_score(p: Purchase, f: Finances, w: Weights,
                 m: Optional[Metrics] = None) -> Score:
    """Điểm áp lực tài chính."""
    return score_of("strain", strain_factors(p, f, w, m), w)


def impulse_score(p: Purchase, w: Weights,
                  now: Optional[datetime] = None) -> Score:
    """Điểm bốc đồng."""
    return score_of("impulse", impulse_factors(p, now), w)


@dataclass
class Verdict:
    """Một trong bốn kết luận."""

    key: str
    title: str
    subtitle: str
    note: str


VERDICTS = {
    "buy": Verdict("buy", "MUA ĐI", "đã cân nhắc kỹ",
                   "Vừa túi tiền, vừa không phải quyết định vội. "
                   "Không có lý do gì để chần chừ."),
    "wait": Verdict("wait", "CHỜ ĐÃ", "7 ngày",
                    "Tiền thì ổn, nhưng bạn đang muốn nó theo kiểu bốc đồng. "
                    "Ghi vào danh sách chờ rồi chấm lại sau."),
    "plan": Verdict("plan", "LÊN KẾ HOẠCH", "để dành trước",
                    "Món này đáng nhưng đang quá nặng so với tiền dư của bạn. "
                    "Để dành rồi mua, đừng bóp phần còn lại của tháng."),
    "no": Verdict("no", "ĐỪNG MUA", "chưa phải lúc",
                  "Vừa nặng tiền vừa quyết định vội. "
                  "Đây đúng là kiểu mua mà tuần sau sẽ tiếc."),
}


def verdict_for(strain: int, impulse: int, w: Weights) -> Verdict:
    """Xếp hai điểm vào ma trận hai chiều để ra một trong bốn ô."""
    high_strain = strain >= w.threshold
    high_impulse = impulse >= w.threshold

    if high_strain and high_impulse:
        return VERDICTS["no"]
    if high_strain:
        return VERDICTS["plan"]
    if high_impulse:
        return VERDICTS["wait"]
    return VERDICTS["buy"]


@dataclass
class TargetPrice:
    """Kết quả bài toán tìm giá mục tiêu."""

    needed: bool            # có cần giảm giá không
    current_score: int      # điểm áp lực ở giá hiện tại
    price: Optional[float] = None   # mức giá cần xuống dưới
    cut: Optional[float] = None     # tỷ lệ cần giảm thêm
    impossible: bool = False        # kể cả miễn phí vẫn vượt ngưỡng


# Mức giá nhỏ nhất còn có ý nghĩa để hiển thị. Giá mục tiêu tìm ra mà
# thấp hơn mức này thì thực chất là "không có giá nào đủ rẻ".
MIN_MEANINGFUL_PRICE = 1_000


def target_price(p: Purchase, f: Finances, w: Weights,
                 iterations: int = 40) -> TargetPrice:
    """Tìm mức giá cao nhất mà điểm áp lực tài chính vẫn dưới ngưỡng.

    Cả bốn yếu tố áp lực đều tăng theo giá, nên điểm áp lực là hàm đơn
    điệu không giảm theo giá. Nhờ tính đơn điệu đó, có thể tìm ngưỡng
    bằng chia đôi khoảng (binary search) thay vì thử từng giá một.

    Mỗi vòng lặp thu hẹp khoảng tìm kiếm một nửa, nên 40 vòng là quá đủ
    độ chính xác cho tiền đồng.

    Lưu ý một trường hợp biên: khi người dùng không có đồng tiết kiệm nào,
    yếu tố "tiền đang có" nhảy bậc ngay khi giá vượt 0, nên có thể không
    tồn tại mức giá dương nào đạt ngưỡng. Lúc đó hàm báo `impossible`
    thay vì trả về giá mục tiêu bằng 0 — vì "giá cần xuống dưới 0 đồng"
    không phải một lời khuyên dùng được.
    """
    here = strain_score(p, f, w).value
    if here < w.threshold:
        return TargetPrice(needed=False, current_score=here)

    def score_at(price: float) -> int:
        return strain_score(p.replace_price(price), f, w).value

    # Nếu miễn phí mà vẫn vượt ngưỡng thì vấn đề không nằm ở giá món đồ.
    if score_at(0) >= w.threshold:
        return TargetPrice(needed=True, current_score=here, impossible=True)

    low, high = 0.0, p.price
    for _ in range(iterations):
        mid = (low + high) / 2
        if score_at(mid) < w.threshold:
            low = mid
        else:
            high = mid

    # Không có mức giá dương nào đủ rẻ: ngân sách mới là vấn đề, không phải giá.
    if low < MIN_MEANINGFUL_PRICE:
        return TargetPrice(needed=True, current_score=here, impossible=True)

    cut = (p.price - low) / p.price if p.price > 0 else 0.0
    return TargetPrice(needed=True, current_score=here, price=low, cut=cut)
