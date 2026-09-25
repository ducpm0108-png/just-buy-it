"""Cá nhân hoá: làm cho công cụ khớp với chính người đang dùng nó.

Cá nhân hoá ở đây KHÔNG phải đổi màu giao diện hay gọi tên người dùng.
Nó là ba việc cụ thể, cả ba đều tính từ dữ liệu người dùng tự tạo ra:

1. **Thời gian chờ riêng.** Bảy ngày là con số tuỳ tiện. Người có ham muốn
   nguội sau 3 ngày thì chờ 7 ngày là thừa; người nguội sau 30 ngày thì
   chờ 7 ngày chẳng nói lên điều gì. Thời gian chờ nên suy ra từ thời gian
   bán rã đo được của chính họ.

2. **Trọng số riêng, lưu lại được.** Trọng số hiệu chỉnh xong phải còn đó
   lần sau, nếu không thì công sức hiệu chỉnh thành vô nghĩa.

3. **Báo cáo hiệu chỉnh.** Chạy lại mô hình trên những quyết định đã qua
   của chính người dùng, đối chiếu với kết quả thật (mua rồi thấy đáng hay
   hớ), rồi chỉ ra nên tăng yếu tố nào. Đây là phần phân tích dữ liệu thật
   sự của dự án: không đoán trọng số, mà đo.

Không có bước nào cần đăng nhập. Tất cả chỉ cần biết dòng dữ liệu nào là
của ai — một cột `profile` là đủ.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .decay import HalfLife
from .metrics import compute
from .models import Finances, Purchase
from .scoring import FACTORS, Weights, impulse_factors, strain_factors, \
    strain_score, impulse_score, verdict_for

# Giới hạn thời gian chờ. Dưới 2 ngày thì không kịp nguội; quá 3 tuần thì
# người dùng bỏ luôn công cụ, mà một lời khuyên không ai theo là vô dụng.
MIN_COOLING_DAYS = 2
MAX_COOLING_DAYS = 21
DEFAULT_COOLING_DAYS = 7

# Ngưỡng phân loại kết quả từ lần chấm gần nhất.
STILL_WANT = 6      # từ 6/10 trở lên: vẫn còn muốn
NO_LONGER = 4       # từ 4/10 trở xuống: đã hết muốn


def cooling_days(half_life: HalfLife) -> float:
    """Số ngày nên chờ, suy ra từ thời gian bán rã của chính người dùng.

    Chờ đúng một chu kỳ bán rã thì mức thèm muốn giảm còn một nửa — vừa đủ
    để phân biệt "muốn thật" với "muốn bốc đồng", mà không bắt người dùng
    chờ vô nghĩa.

    Chưa có dữ liệu thì dùng 7 ngày như quy ước chung.
    """
    if not half_life.from_data:
        return DEFAULT_COOLING_DAYS
    return max(MIN_COOLING_DAYS, min(MAX_COOLING_DAYS, half_life.days))


def cooling_hours(half_life: HalfLife) -> float:
    """Thời gian chờ quy ra giờ, để truyền cho `sale.review_deadline_hours`."""
    return cooling_days(half_life) * 24


def cooling_explanation(half_life: HalfLife) -> str:
    """Một câu giải thích vì sao thời gian chờ là con số đó."""
    days = cooling_days(half_life)
    if not half_life.from_data:
        return (f"Chờ {DEFAULT_COOLING_DAYS} ngày theo quy ước chung. "
                f"Sau vài món được chấm lại, con số này sẽ đổi theo chính bạn.")

    reason = f"đo từ {half_life.sample_size} món bạn đã chấm lại"
    if half_life.days < MIN_COOLING_DAYS:
        measured = f"{half_life.days:.1f}".replace(".", ",")
        return (f"Ham muốn của bạn nguội rất nhanh (bán rã {measured} ngày, "
                f"{reason}), nhưng vẫn nên chờ tối thiểu "
                f"{MIN_COOLING_DAYS} ngày.")
    if half_life.days > MAX_COOLING_DAYS:
        return (f"Ham muốn của bạn rất bền (bán rã {round(half_life.days)} "
                f"ngày, {reason}). Chờ tối đa {MAX_COOLING_DAYS} ngày là đủ — "
                f"chờ lâu hơn thì bạn sẽ bỏ luôn công cụ này.")
    return (f"Chờ {round(days)} ngày, bằng đúng thời gian bán rã ham muốn "
            f"của bạn ({reason}): sau chừng đó, mức muốn còn một nửa.")


# --------------------------------------------------------------- kết quả thật

@dataclass
class Outcome:
    """Kết quả thật của một quyết định đã qua."""

    item_id: int
    name: str
    price: float
    label: str           # xem LABELS bên dưới
    went_ahead: bool     # mô hình có khuyên tiến tới không
    was_right: bool      # mô hình có khuyên đúng không
    verdict: str         # con dấu lúc đó
    strain: int
    impulse: int
    first_desire: int
    last_desire: int


LABELS = {
    "mua_dung": "Mua và vẫn thấy đáng",
    "mua_ho": "Mua rồi hết muốn",
    "bo_dung": "Bỏ qua và không tiếc",
    "bo_lo": "Bỏ qua nhưng vẫn muốn",
}


def label_outcome(status: str, last_desire: int) -> Optional[str]:
    """Gán nhãn kết quả từ trạng thái và lần chấm gần nhất.

    Trả về None khi chưa kết luận được: món còn đang chờ, hoặc mức thèm
    muốn nằm ở giữa (5/10) nên không rõ là còn muốn hay hết muốn.
    """
    if status == "bought":
        if last_desire >= STILL_WANT:
            return "mua_dung"
        if last_desire <= NO_LONGER:
            return "mua_ho"
    elif status == "skipped":
        if last_desire <= NO_LONGER:
            return "bo_dung"
        if last_desire >= STILL_WANT:
            return "bo_lo"
    return None


def replay(rows: List, ratings_of, context_of,
           w: Weights) -> List[Outcome]:
    """Chạy lại mô hình trên các quyết định đã qua.

    `context_of(row)` trả về (purchase, finances, decided_at) — truyền vào
    thay vì gọi db trực tiếp, để module này không phụ thuộc lớp lưu trữ và
    kiểm thử được bằng dữ liệu dựng tay. Thứ tự tham số giống
    `factor_gaps` để hai hàm dùng lẫn được.

    Quan trọng: chạy lại với trọng số HIỆN TẠI, không phải trọng số lúc đó.
    Câu hỏi cần trả lời là "bộ cài đặt bây giờ của tôi có bắt được món tôi
    đã mua hớ không", chứ không phải "hồi đó tôi cài gì".
    """
    out = []
    for row in rows:
        ratings = ratings_of(row)
        if len(ratings) < 2:
            continue      # chưa chấm lại lần hai thì chưa biết kết quả

        label = label_outcome(row["status"], ratings[-1].desire)
        if label is None:
            continue

        purchase, money, decided_at = context_of(row)
        m = compute(purchase, money)
        st = strain_score(purchase, money, w, m)
        im = impulse_score(purchase, w, now=decided_at)
        v = verdict_for(st.value, im.value, w)

        # "Tiến tới" gồm MUA ĐI và LÊN KẾ HOẠCH.
        #
        # Đây là một lựa chọn có thể bàn, nên nói rõ: LÊN KẾ HOẠCH trên thực
        # tế vẫn ngăn người dùng mua ngay, nên có thể xếp nó vào nhóm "dừng".
        # Ở đây xếp vào nhóm "tiến tới" vì nội dung của nó là *khẳng định
        # món đồ đáng mua*, chỉ hoãn vì chưa đủ tiền. Nếu người dùng bỏ qua
        # món đó và không hề tiếc, thì lời khẳng định ấy đã sai.
        #
        # Đổi cách xếp sẽ đổi tỷ lệ đoán đúng, nên khi trình bày cần nêu
        # cách xếp đang dùng.
        went_ahead = v.key in ("buy", "plan")
        was_right = (went_ahead and label in ("mua_dung", "bo_lo")) or \
                    (not went_ahead and label in ("mua_ho", "bo_dung"))

        out.append(Outcome(
            item_id=row["id"], name=row["name"], price=row["price"],
            label=label, went_ahead=went_ahead, was_right=was_right,
            verdict=v.title, strain=st.value, impulse=im.value,
            first_desire=ratings[0].desire, last_desire=ratings[-1].desire,
        ))
    return out


# ------------------------------------------------------- báo cáo hiệu chỉnh

@dataclass
class Calibration:
    """Kết quả đối chiếu mô hình với kết quả thật của người dùng."""

    n: int                      # số quyết định đã có kết quả
    n_right: int
    accuracy: float
    # Ma trận nhầm lẫn 2x2
    correct_go: int             # khuyên mua, và đúng là đáng
    correct_hold: int           # khuyên dừng, và đúng là không đáng
    false_go: int               # khuyên mua, nhưng hoá ra hớ
    false_hold: int             # khuyên dừng, nhưng hoá ra vẫn muốn
    missed_value: float         # tổng tiền của các món bị bỏ lỡ oan
    wasted_value: float         # tổng tiền của các món mua hớ mà mô hình bỏ qua

    @property
    def enough_data(self) -> bool:
        """Dưới 5 quyết định thì mọi tỷ lệ đều là nhiễu."""
        return self.n >= 5


def calibrate(outcomes: List[Outcome]) -> Calibration:
    """Dựng ma trận nhầm lẫn từ các quyết định đã có kết quả.

    Hai loại lỗi có hậu quả khác nhau, nên không gộp:

    - **Khuyên mua nhưng hoá ra hớ** (false_go): công cụ đã không chặn được
      một khoản tiêu vô ích. Đây là lỗi nặng hơn — đúng việc mà công cụ này
      sinh ra để làm.
    - **Khuyên dừng nhưng vẫn muốn** (false_hold): công cụ đã cản một món
      thật sự đáng. Gây khó chịu, nhưng không mất tiền.
    """
    correct_go = sum(1 for o in outcomes if o.went_ahead and o.was_right)
    correct_hold = sum(1 for o in outcomes if not o.went_ahead and o.was_right)
    false_go = sum(1 for o in outcomes if o.went_ahead and not o.was_right)
    false_hold = sum(1 for o in outcomes if not o.went_ahead and not o.was_right)

    n = len(outcomes)
    n_right = correct_go + correct_hold

    return Calibration(
        n=n, n_right=n_right,
        accuracy=n_right / n if n else 0.0,
        correct_go=correct_go, correct_hold=correct_hold,
        false_go=false_go, false_hold=false_hold,
        missed_value=sum(o.price for o in outcomes
                         if not o.went_ahead and not o.was_right),
        wasted_value=sum(o.price for o in outcomes
                         if o.went_ahead and not o.was_right),
    )


@dataclass
class FactorGap:
    """Một yếu tố và khả năng phân biệt mua đúng với mua hớ của nó."""

    key: str
    label: str
    group: str
    mean_regret: float      # giá trị trung bình ở các món mua hớ
    mean_good: float        # giá trị trung bình ở các món mua đúng
    gap: float              # chênh lệch; càng lớn càng phân biệt tốt


def factor_gaps(rows: List, ratings_of, context_of,
                w: Weights) -> List[FactorGap]:
    """Đo yếu tố nào phân biệt tốt nhất giữa món mua đúng và món mua hớ.

    Cách đo là hiệu số trung bình: với mỗi yếu tố, tính giá trị trung bình
    trên nhóm mua hớ và trên nhóm mua đúng, rồi lấy chênh lệch. Yếu tố có
    chênh lệch lớn là yếu tố mang thông tin — nên tăng trọng số cho nó.
    Yếu tố chênh lệch gần 0 thì với người này nó không nói lên gì.

    Đây là cách đo đơn giản nhất có ý nghĩa, không cần thư viện ngoài. Với
    nhiều dữ liệu hơn thì bước tiếp theo là hồi quy logistic, nhưng vài
    chục quyết định thì hiệu số trung bình đã đủ để biết nên chỉnh thanh nào.
    """
    regret: Dict[str, List[float]] = {}
    good: Dict[str, List[float]] = {}

    for row in rows:
        ratings = ratings_of(row)
        if len(ratings) < 2:
            continue
        label = label_outcome(row["status"], ratings[-1].desire)
        if label not in ("mua_ho", "mua_dung"):
            continue

        purchase, money, decided_at = context_of(row)
        m = compute(purchase, money)
        values = {}
        values.update(strain_factors(purchase, money, w, m))
        values.update(impulse_factors(purchase, now=decided_at))

        bucket = regret if label == "mua_ho" else good
        for k, v in values.items():
            bucket.setdefault(k, []).append(v)

    def mean(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    gaps = []
    for group, factors in FACTORS.items():
        for key, label, _short, _how in factors:
            if key not in regret or key not in good:
                continue
            mr, mg = mean(regret[key]), mean(good[key])
            gaps.append(FactorGap(key=key, label=label, group=group,
                                  mean_regret=mr, mean_good=mg,
                                  gap=mr - mg))

    gaps.sort(key=lambda g: -g.gap)
    return gaps


def suggestions(cal: Calibration, gaps: List[FactorGap]) -> List[str]:
    """Gợi ý chỉnh trọng số, viết thành câu người dùng đọc được.

    Cố tình thận trọng: dữ liệu ít thì nói là ít, và không bao giờ tự động
    đổi trọng số — chỉ nói nên chỉnh gì. Quyết định vẫn là của người dùng.
    """
    out = []

    if not cal.enough_data:
        out.append(
            f"Mới có {cal.n} quyết định đã biết kết quả. Cần ít nhất 5 món "
            "mới nói được gì có ý nghĩa — cứ dùng tiếp rồi quay lại."
        )
        return out

    out.append(
        f"Bộ trọng số hiện tại đoán đúng {cal.n_right}/{cal.n} quyết định "
        f"({round(cal.accuracy * 100)}%)."
    )

    if cal.false_go:
        wasted = f"{round(cal.wasted_value):,}".replace(",", ".")
        out.append(
            f"Có {cal.false_go} món công cụ khuyên mua mà bạn đã hối "
            f"(tổng {wasted} đồng). Đây là loại lỗi đáng sửa trước: công cụ "
            "đang quá dễ dãi. Hạ ngưỡng xuống 5 điểm, hoặc tăng yếu tố ở "
            "dòng dưới."
        )
    if cal.false_hold:
        out.append(
            f"Có {cal.false_hold} món công cụ khuyên dừng mà bạn vẫn muốn. "
            "Nếu số này lớn hơn số ở trên thì công cụ đang quá khắt khe — "
            "nâng ngưỡng lên."
        )
    if not cal.false_go and not cal.false_hold:
        out.append("Chưa có quyết định nào sai. Giữ nguyên bộ trọng số.")

    strong = [g for g in gaps if g.gap > 0.15]
    if strong:
        g = strong[0]
        regret = f"{g.mean_regret:.2f}".replace(".", ",")
        good = f"{g.mean_good:.2f}".replace(".", ",")
        out.append(
            f"Yếu tố phân biệt tốt nhất là **{g.label}**: ở những món bạn "
            f"mua hớ, giá trị trung bình là {regret} so với {good} ở những "
            f"món mua đúng. Tăng trọng số cho yếu tố này."
        )

    weak = [g for g in gaps if abs(g.gap) < 0.03]
    if weak and len(gaps) > 3:
        names = ", ".join(g.label.lower() for g in weak[:2])
        out.append(
            f"Ngược lại, {names} gần như không phân biệt được gì trong dữ "
            "liệu của bạn. Cân nhắc hạ trọng số các yếu tố này."
        )

    return out
