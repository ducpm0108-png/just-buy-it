"""Lời khuyên khi món đồ đang trong đợt giảm giá có thời hạn.

Tình huống thường gặp nhất ở Việt Nam: flash sale và các ngày đôi tạo
áp lực phải bấm mua ngay. Module này trả lời hai câu hỏi:

1. Có cần mua ngay không? Thường là không — chờ đến ngày cuối đợt sale
   vẫn giữ nguyên mức giảm mà có thêm thời gian để nguội.

2. Nếu đợt sale kết thúc trước khi hết 7 ngày chờ, chờ hay mua?
   So sánh thiệt hại kỳ vọng của hai lựa chọn.
"""

from dataclasses import dataclass
from typing import Optional
import math

from .decay import HalfLife, desire_after
from .metrics import Metrics
from .models import Purchase

# Số giờ trong 7 ngày chờ nguội.
COOLING_HOURS = 168

# Giờ trước lúc hết sale mà vẫn kịp quyết định, dùng để dời hạn chấm lại.
BUFFER_HOURS = 6


@dataclass
class SaleAdvice:
    """Kết quả phân tích một đợt giảm giá có thời hạn."""

    hours_left: float
    ends_within_cooling: bool     # sale hết trước khi đủ 7 ngày chờ
    p_still_want: float           # khả năng sau 7 ngày vẫn còn muốn, thang 0-1
    half_life: HalfLife
    resale_value: float           # bán lại được bao nhiêu nếu sau này tiếc
    wait_loss: float              # thiệt hại kỳ vọng nếu chờ và mất đợt giảm
    buy_loss: float               # thiệt hại kỳ vọng nếu mua rồi tiếc

    @property
    def better_to_wait(self) -> bool:
        """Chờ có lợi hơn mua ngay hay không."""
        return self.wait_loss <= self.buy_loss

    @property
    def recommendation(self) -> str:
        if self.better_to_wait:
            return "Chờ vẫn lợi hơn, kể cả khi lỡ mất đợt sale."
        return "Mức giảm đủ lớn để mua trong đợt này — nhưng vào ngày cuối."


def advise(p: Purchase, m: Metrics, hl: HalfLife) -> Optional[SaleAdvice]:
    """Phân tích đánh đổi giữa chờ nguội và mua trong đợt sale.

    Trả về None khi không có gì để phân tích: không có sale, sale không
    có hạn, hoặc thực tế không giảm giá.

    Cách tính thiệt hại kỳ vọng:

    - Chờ: mất mức giảm, nhưng chỉ "mất" thật nếu sau 7 ngày vẫn còn muốn
      mua. Vậy thiệt hại kỳ vọng = mức giảm x khả năng vẫn còn muốn.

    - Mua: tiêu tiền ngay, nhưng chỉ "tiếc" nếu sau 7 ngày không còn muốn.
      Số tiền mất là giá trừ phần bán lại được.
      Thiệt hại kỳ vọng = (giá - giá bán lại) x khả năng không còn muốn.
    """
    if not p.sale.on or not math.isfinite(p.sale.hours_left) or m.discount <= 0:
        return None

    p7 = desire_after(p.desire, days=7, half_life_days=hl.days)
    resale = min(p.used_price, p.price) if p.used_price is not None else 0.0

    return SaleAdvice(
        hours_left=p.sale.hours_left,
        ends_within_cooling=p.sale.hours_left < COOLING_HOURS,
        p_still_want=p7,
        half_life=hl,
        resale_value=resale,
        wait_loss=m.discount * p7,
        buy_loss=(p.price - resale) * (1 - p7),
    )


def review_deadline_hours(p: Purchase, cooling_hours: float = COOLING_HOURS) -> float:
    """Số giờ đến hạn chấm lại mức thèm muốn.

    Bình thường là 7 ngày. Nếu đợt sale kết thúc trước đó thì dời hạn lên
    sớm hơn, để người dùng còn kịp quyết định trước khi mất mức giảm.
    """
    if p.sale.on and math.isfinite(p.sale.hours_left) and p.sale.hours_left > 0:
        if p.sale.hours_left < cooling_hours:
            return max(0.0, p.sale.hours_left - BUFFER_HOURS)
    return cooling_hours
