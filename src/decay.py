"""Đo độ nguội của ham muốn.

Ý tưởng: khi kết quả là "chờ đã", món đồ được lưu lại kèm mức thèm muốn
lúc đó. Đến hạn, người dùng chấm lại mà không thấy điểm cũ. Từ các cặp
điểm trước - sau, ước tính "thời gian bán rã": số ngày để mức muốn một
món giảm đi một nửa.

Mô hình giả định ham muốn giảm theo hàm mũ:

    v(t) = v0 * 0.5 ** (t / T)

với T là thời gian bán rã. Giải ra T từ một cặp quan sát:

    T = t * ln(2) / -ln(v1 / v0)

Đây là một giả định đơn giản hoá. Với dữ liệu thật, hoàn toàn có thể
kiểm tra xem hàm mũ có khớp hơn một đường thẳng hay không — đó là một
hướng phân tích đáng làm và nên nói rõ trong báo cáo.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import math


@dataclass
class Rating:
    """Một lần chấm mức thèm muốn."""

    rated_at: datetime
    desire: int


@dataclass
class HalfLife:
    """Thời gian bán rã của ham muốn."""

    days: float
    from_data: bool      # True: tính từ dữ liệu người dùng; False: giá trị mặc định
    sample_size: int = 0


def half_life_from_pair(first: Rating, last: Rating) -> Optional[float]:
    """Tính thời gian bán rã từ một cặp lần chấm.

    Trả về None khi không tính được: ham muốn tăng lên, không đổi, rơi
    về 0, hoặc hai lần chấm cùng thời điểm.
    """
    if first.desire <= 0 or last.desire <= 0:
        return None

    ratio = last.desire / first.desire
    if not 0 < ratio < 1:
        return None   # không giảm thì không có bán rã

    days = (last.rated_at - first.rated_at).total_seconds() / 86400
    if days <= 0:
        return None

    return days * math.log(2) / -math.log(ratio)


def estimate_half_life(rating_series: List[List[Rating]],
                       default_days: float = 10.0) -> HalfLife:
    """Ước tính thời gian bán rã trung bình từ nhiều món đồ.

    `rating_series` là danh sách các chuỗi chấm điểm, mỗi món một chuỗi.
    Chỉ những món được chấm lại ít nhất hai lần mới góp vào kết quả.
    """
    values = []
    for ratings in rating_series:
        if len(ratings) < 2:
            continue
        hl = half_life_from_pair(ratings[0], ratings[-1])
        if hl is not None:
            values.append(hl)

    if values:
        return HalfLife(days=sum(values) / len(values),
                        from_data=True, sample_size=len(values))
    return HalfLife(days=default_days, from_data=False, sample_size=0)


def desire_after(desire_now: int, days: float, half_life_days: float) -> float:
    """Dự đoán mức thèm muốn sau một số ngày, trả về thang 0-1.

    Dùng để ước tính khả năng người dùng vẫn còn muốn món đồ sau khi chờ.
    """
    if half_life_days <= 0:
        return 0.0
    return max(0.0, min(1.0, desire_now * 0.5 ** (days / half_life_days) / 10))
