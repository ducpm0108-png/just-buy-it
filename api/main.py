"""API HTTP cho Just Buy It? — lớp vỏ quanh src/, chạy trên Vercel.

Nguyên tắc duy nhất của file này: **không có một công thức nào ở đây.**
Mọi con số đều do `src/` tính. Việc của file này là đổi JSON thành dataclass,
gọi hàm trong `src/`, rồi đổi kết quả về JSON.

Vì sao có file này: giao diện là trang HTML ở `public/index.html`, còn toàn
bộ phần tính toán phải là Python. Trước đây trang HTML tự tính bằng
JavaScript, nghĩa là mỗi công thức tồn tại hai bản — một trong
`src/scoring.py`, một trong trang. Hai nguồn sự thật thì sớm muộn cũng lệch.
Giờ trang không tính gì cả, chỉ hỏi và vẽ.

Không có cơ sở dữ liệu. Dữ liệu người dùng nằm trong trình duyệt của họ; các
endpoint cần lịch sử thì nhận lịch sử kèm trong request. API không giữ
trạng thái nào giữa hai lần gọi, nên không có gì để rò rỉ và không cần đăng
nhập.
"""

from __future__ import annotations

import math
import pathlib
import sys
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# Đưa gốc dự án vào sys.path trước khi import src/.
#
# Cần thiết vì entrypoint là api/main.py: khi Python nạp nó, thư mục nằm
# đầu sys.path là api/, không phải gốc dự án, nên `from src...` sẽ không
# thấy gì. Dòng này đúng cả khi chạy cục bộ bằng uvicorn và khi Vercel nạp.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from fastapi import FastAPI                                    # noqa: E402
from fastapi.middleware.cors import CORSMiddleware             # noqa: E402
from pydantic import BaseModel, Field                          # noqa: E402

from src import calendar_vn, decay, metrics, personalize, sale, scoring  # noqa: E402
from src.models import CATEGORIES, Finances, Goal, Purchase, SOURCES, Sale  # noqa: E402
from src.scoring import FACTORS, PRESETS, VERDICTS, Weights     # noqa: E402

app = FastAPI(
    title="Just Buy It? API",
    version="1.0",
    description=(
        "Phần tính toán của Just Buy It?. Giao diện chỉ gửi số liệu và vẽ "
        "lại kết quả; mọi công thức nằm trong src/ của dự án."
    ),
)

# Cho phép gọi từ mọi nguồn. Lý do an toàn: API không giữ trạng thái, không
# có đăng nhập, không có dữ liệu nằm sẵn trên server — mỗi request tự mang
# đủ số liệu của nó. Nên "ai gọi cũng được" ở đây không mở ra điều gì mà
# người gọi chưa tự có. Nhờ vậy cùng một trang HTML chạy được cả trên Vercel,
# cả khi mở bằng file, cả trong trình xem artifact.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ------------------------------------------------------------ JSON an toàn

def fin(x: Optional[float]) -> Optional[float]:
    """Đổi số không hữu hạn thành None.

    JSON không có `Infinity` hay `NaN`. `json.dumps` của Python vẫn in ra
    chữ `Infinity`, nhưng `JSON.parse` của trình duyệt coi đó là lỗi cú
    pháp và ném ngay — cả phản hồi thành rác. Mà `inf` xuất hiện thật:
    `cost_per_use` là inf khi người dùng để số lần dùng bằng 0, `work_hours`
    là inf khi thu nhập bằng 0.

    Nên biên giới giữa Python và JSON là chỗ duy nhất xử lý việc này: ra
    ngoài là None, và trang hiển thị None thành "∞" hoặc "—".
    """
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def iso(d: Optional[date | datetime]) -> Optional[str]:
    return d.isoformat() if d is not None else None


# ------------------------------------------------------------- đầu vào

class SaleIn(BaseModel):
    on: bool = False
    list_price: Optional[float] = Field(default=None, ge=0)
    # None nghĩa là không có hạn. Không dùng số rất lớn làm "vô hạn": như
    # thế thì mọi phép so sánh vẫn chạy nhưng cho kết quả sai một cách im
    # lặng, còn None thì buộc phải xử lý.
    hours_left: Optional[float] = Field(default=None, ge=0)
    low_30d: Optional[float] = Field(default=None, ge=0)

    def to_model(self) -> Sale:
        return Sale(
            on=self.on,
            list_price=self.list_price,
            hours_left=math.inf if self.hours_left is None else self.hours_left,
            low_30d=self.low_30d,
        )


class ItemIn(BaseModel):
    name: str = Field(default="Món chưa đặt tên", max_length=120)
    price: float = Field(default=0, ge=0)
    uses_per_month: float = Field(default=0, ge=0)
    months: float = Field(default=1, ge=0)
    category: str = "other"
    wanted_days: float = Field(default=0, ge=0)
    source: str = "need"
    owns_similar: bool = False
    desire: int = Field(default=5, ge=1, le=10)
    used_price: Optional[float] = Field(default=None, ge=0)

    def to_model(self, sale_in: SaleIn) -> Purchase:
        return Purchase(
            name=self.name.strip() or "Món chưa đặt tên",
            price=self.price,
            uses_per_month=self.uses_per_month,
            months=self.months,
            category=self.category if self.category in CATEGORIES else "other",
            wanted_days=self.wanted_days,
            source=self.source if self.source in SOURCES else "need",
            owns_similar=self.owns_similar,
            desire=self.desire,
            used_price=self.used_price,
            sale=sale_in.to_model(),
        )


class FinancesIn(BaseModel):
    income: float = Field(default=0, ge=0)
    fixed_costs: float = Field(default=0, ge=0)
    savings: float = Field(default=0, ge=0)

    def to_model(self) -> Finances:
        return Finances(income=self.income, fixed_costs=self.fixed_costs,
                        savings=self.savings)


class WeightsIn(BaseModel):
    strain: Dict[str, float] = Field(default_factory=dict)
    impulse: Dict[str, float] = Field(default_factory=dict)
    threshold: Optional[float] = Field(default=None, ge=0, le=100)
    ref_cost_per_use: Optional[float] = Field(default=None, gt=0)
    default_half_life: Optional[float] = Field(default=None, gt=0)

    def to_model(self) -> Weights:
        """Trộn lên bộ mặc định, chỉ nhận đúng các khoá đã biết.

        Không dùng thẳng dict của client: một khoá lạ sẽ lặng lẽ nằm trong
        trọng số và làm tổng bị lệch, mà không ai thấy.
        """
        w = Weights()
        for group, incoming in (("strain", self.strain), ("impulse", self.impulse)):
            known = getattr(w, group)
            for k, v in incoming.items():
                if k in known and isinstance(v, (int, float)) and math.isfinite(v):
                    known[k] = max(0.0, float(v))
        if self.threshold is not None:
            w.threshold = self.threshold
        if self.ref_cost_per_use is not None:
            w.ref_cost_per_use = self.ref_cost_per_use
        if self.default_half_life is not None:
            w.default_half_life = self.default_half_life
        return w


class GoalIn(BaseModel):
    name: str = Field(default="", max_length=80)
    amount: float = Field(default=0, ge=0)


class RatingIn(BaseModel):
    """Một lần chấm ham muốn. Tên trường theo đúng những gì trang đang lưu."""

    t: str                                  # thời điểm, ISO
    v: int = Field(ge=0, le=10)

    def to_model(self) -> Optional[decay.Rating]:
        try:
            when = datetime.fromisoformat(self.t.replace("Z", "+00:00"))
        except ValueError:
            return None                     # bỏ mốc thời gian không đọc được
        return decay.Rating(rated_at=when.replace(tzinfo=None), desire=self.v)


class AlternativesIn(BaseModel):
    """Các cách khác để có món đồ. None nghĩa là không cân nhắc cách đó."""

    used: Optional[float] = Field(default=None, ge=0)     # mua cũ, trả một lần
    rent: Optional[float] = Field(default=None, ge=0)     # thuê, tính theo lần
    borrow: Optional[float] = Field(default=None, ge=0)   # mượn, chi phí nếu có


class EvaluateIn(BaseModel):
    item: ItemIn = Field(default_factory=ItemIn)
    alternatives: AlternativesIn = Field(default_factory=AlternativesIn)
    sale: SaleIn = Field(default_factory=SaleIn)
    finances: FinancesIn = Field(default_factory=FinancesIn)
    weights: WeightsIn = Field(default_factory=WeightsIn)
    goals: List[GoalIn] = Field(default_factory=list)
    # Các chuỗi chấm điểm đã có, để ước tính bán rã từ dữ liệu của chính
    # người dùng thay vì dùng giá trị mặc định.
    rating_series: List[List[RatingIn]] = Field(default_factory=list)
    # Cho phép truyền thời điểm, để test tái lập được: yếu tố "giờ khuya"
    # và số ngày tới đợt sale đều phụ thuộc lúc gọi.
    now: Optional[datetime] = None


class ItemRow(BaseModel):
    """Một món đã lưu, đúng hình dạng trang đang giữ trong trình duyệt."""

    id: str = ""
    name: str = ""
    price: float = Field(default=0, ge=0)
    status: str = "waiting"
    created: Optional[str] = None
    ratings: List[RatingIn] = Field(default_factory=list)


class ProfileIn(BaseModel):
    items: List[ItemRow] = Field(default_factory=list)
    weights: WeightsIn = Field(default_factory=WeightsIn)


# ------------------------------------------------------------- đầu ra

def weights_out(w: Weights) -> Dict[str, Any]:
    return asdict(w)


def half_life_of(series: List[List[RatingIn]], w: Weights) -> decay.HalfLife:
    """Bán rã ước tính từ các chuỗi chấm điểm client gửi lên."""
    clean: List[List[decay.Rating]] = []
    for one in series:
        got = [r.to_model() for r in one]
        got = [r for r in got if r is not None]
        if len(got) >= 2:
            clean.append(got)
    return decay.estimate_half_life(clean, default_days=w.default_half_life)


def alternatives_out(p: Purchase, alt: AlternativesIn) -> List[Dict[str, Any]]:
    """Giá mỗi lần dùng của từng cách có được món đồ.

    Cùng một hàm `metrics.cost_per_use` với cách mua mới, nên bốn dòng trong
    bảng chắc chắn so sánh được với nhau. Trước đây bảng này tự tính bằng
    JavaScript — tức là một bản sao thứ hai của công thức.

    "Thuê" nhập sẵn theo lần nên không phải chia; hai cách còn lại trả một
    lần nên chia cho tổng số lần dùng.

    "Mượn" bị loại khỏi việc chọn rẻ nhất: nó thường bằng 0 nên sẽ luôn
    thắng, mà mượn được thì đã không còn là quyết định mua nữa.
    """
    rows: List[Dict[str, Any]] = [
        {"kind": "new", "cost_per_use": fin(metrics.cost_per_use(p))},
    ]
    if alt.used is not None:
        rows.append({"kind": "used",
                     "cost_per_use": fin(metrics.cost_per_use(
                         p.replace_price(alt.used)))})
    if alt.rent is not None:
        rows.append({"kind": "rent", "cost_per_use": fin(alt.rent)})
    if alt.borrow is not None:
        rows.append({"kind": "borrow",
                     "cost_per_use": fin(metrics.cost_per_use(
                         p.replace_price(alt.borrow)))})

    dua_tranh = [r for r in rows
                 if r["kind"] != "borrow" and r["cost_per_use"] is not None]
    re_nhat = min(dua_tranh, key=lambda r: r["cost_per_use"], default=None)
    for r in rows:
        r["best"] = re_nhat is not None and r is re_nhat
    return rows


def score_out(s: scoring.Score) -> Dict[str, Any]:
    return {
        "value": s.value,
        # top_parts trả về các bộ ba (khoá, nhãn ngắn, điểm) — dùng cho dòng
        # chữ nhỏ dưới mỗi thanh trên hoá đơn.
        "parts": [{"key": key, "short": short, "points": fin(pts)}
                  for key, short, pts in s.top_parts()],
    }


@app.get("/api/meta")
def meta() -> Dict[str, Any]:
    """Từ vựng của giao diện: danh mục, nguồn, các yếu tố, bộ có sẵn.

    Trang nạp thứ này một lần lúc mở để dựng các ô chọn và thanh trượt.
    Nhờ vậy nhãn và công thức chỉ được viết một lần, trong `src/scoring.py`
    — trước đây chúng có bản thứ hai nằm trong JavaScript của trang.

    Gọi lúc mở trang còn một tác dụng phụ có ích: nó đánh thức hàm trên
    Vercel, nên lần bấm đầu tiên của người dùng không phải chờ khởi động.
    """
    return {
        "categories": [{"key": k, "label": v} for k, v in CATEGORIES.items()],
        "sources": [{"key": k, "label": label, "value": val}
                    for k, (label, val) in SOURCES.items()],
        "factors": {
            group: [{"key": k, "label": label, "short": short, "how": how}
                    for k, label, short, how in rows]
            for group, rows in FACTORS.items()
        },
        "presets": {name: weights_out(w) for name, w in PRESETS.items()},
        "defaults": weights_out(Weights()),
        "verdicts": {k: asdict(v) for k, v in VERDICTS.items()},
        "reference_units": [{"name": n, "price": p}
                            for n, p in metrics.REFERENCE_UNITS],
    }


@app.post("/api/evaluate")
def evaluate(body: EvaluateIn) -> Dict[str, Any]:
    """Toàn bộ nội dung tờ hoá đơn, trong một lần gọi.

    Một endpoint thay vì nhiều endpoint nhỏ là có chủ ý: hoá đơn cập nhật
    theo từng lần gõ, nên mỗi lần chỉ nên có đúng một vòng đi về.
    """
    p = body.item.to_model(body.sale)
    f = body.finances.to_model()
    w = body.weights.to_model()
    now = body.now

    m = metrics.compute(p, f)
    st = scoring.strain_score(p, f, w, m)
    im = scoring.impulse_score(p, w, now=now)
    v = scoring.verdict_for(st.value, im.value, w)
    tp = scoring.target_price(p, f, w)

    hl = half_life_of(body.rating_series, w)
    adv = sale.advise(p, m, hl)

    today = (now or datetime.now()).date()
    window, timing = calendar_vn.timing_advice(
        p.category, tp.cut if tp.needed else None, today=today)

    goals = [Goal(name=g.name, amount=g.amount)
             for g in body.goals if g.name and g.amount > 0]

    return {
        "metrics": {
            "total_uses": fin(m.total_uses),
            "cost_per_use": fin(m.cost_per_use),
            "work_hours": fin(m.work_hours),
            "discretionary": fin(m.discretionary),
            "share_discretionary": fin(m.share_discretionary),
            "coverage": fin(m.coverage),
            "months_to_rebuild": fin(m.months_to_rebuild),
            "opportunity_5y": fin(m.opportunity_5y),
            "discount": fin(m.discount),
            "discount_pct": fin(m.discount_pct),
            "vs_low_30d": fin(m.vs_low_30d),
            "fake_discount": m.fake_discount,
        },
        "strain": score_out(st),
        "impulse": score_out(im),
        "threshold": fin(w.threshold),
        "verdict": asdict(v),
        "target": {
            "needed": tp.needed,
            "current_score": tp.current_score,
            "impossible": tp.impossible,
            "price": fin(tp.price),
            "cut": fin(tp.cut),
        },
        "timing": {
            "advice": timing,
            "window": ({"name": window.name, "when": iso(window.when),
                        "days_away": window.days_away} if window else None),
        },
        "sale_advice": ({
            "hours_left": fin(adv.hours_left),
            "ends_within_cooling": adv.ends_within_cooling,
            "p_still_want": fin(adv.p_still_want),
            "resale_value": fin(adv.resale_value),
            "wait_loss": fin(adv.wait_loss),
            "buy_loss": fin(adv.buy_loss),
            "better_to_wait": adv.better_to_wait,
            "recommendation": adv.recommendation,
        } if adv else None),
        "half_life": {"days": fin(hl.days), "from_data": hl.from_data,
                      "sample_size": hl.sample_size},
        "cooling_hours": fin(personalize.cooling_hours(hl)),
        "cooling_explanation": personalize.cooling_explanation(hl),
        "review_deadline_hours": fin(
            sale.review_deadline_hours(p, personalize.cooling_hours(hl))),
        "alternatives": alternatives_out(p, body.alternatives),
        "units": [{"name": n, "quantity": q}
                  for n, q in metrics.in_reference_units(p.price)],
        "goals": [{"name": n, "ratio": fin(r)}
                  for n, r in metrics.compare_to_goals(p.price, goals)],
    }


@app.post("/api/profile")
def profile(body: ProfileIn) -> Dict[str, Any]:
    """Hồ sơ mua sắm, tính từ các món client gửi lên.

    Phần bán rã dùng `src/decay.py` — cùng một hàm mà tab Đánh giá dùng,
    nên hai tab không thể cho ra hai con số khác nhau.

    Chưa có phần hiệu chỉnh trọng số (`personalize.calibrate`) vì nó cần
    biết thu nhập và chi phí cố định *lúc quyết định* từng món, mà trang
    hiện không lưu các số đó cùng món. Thêm được, nhưng đó là đổi nội dung
    file xuất ra nên để thành một bước riêng.
    """
    w = body.weights.to_model()
    items = body.items

    series = [it.ratings for it in items]
    hl = half_life_of(series, w)

    rated = [it for it in items if len(it.ratings) > 1]
    bought = [it for it in items if it.status == "bought"]
    skipped = [it for it in items if it.status == "skipped"]

    first_mean = last_mean = None
    if rated:
        first_mean = sum(it.ratings[0].v for it in rated) / len(rated)
        last_mean = sum(it.ratings[-1].v for it in rated) / len(rated)

    # "Mua rồi hết muốn": đúng ngưỡng mà personalize.label_outcome dùng cho
    # nhãn "mua hớ", nên hai nơi không thể lệch định nghĩa.
    regret = [it for it in bought
              if it.ratings and personalize.label_outcome(
                  "bought", it.ratings[-1].v) == "mua_ho"]

    return {
        "count": len(items),
        "total_considered": fin(sum(it.price for it in items)),
        "bought": len(bought),
        "skipped": len(skipped),
        "saved": fin(sum(it.price for it in skipped)),
        "rated": len(rated),
        "desire_first_mean": fin(first_mean),
        "desire_last_mean": fin(last_mean),
        "half_life": {"days": fin(hl.days), "from_data": hl.from_data,
                      "sample_size": hl.sample_size},
        "regret": {
            "count": len(regret),
            "total": fin(sum(it.price for it in regret)),
            "names": [it.name for it in regret][:10],
        },
    }


@app.get("/api/health")
def health() -> Dict[str, str]:
    """Để kiểm tra deploy đã sống chưa mà không cần gửi số liệu nào."""
    return {"status": "ok"}


# ------------------------------------------------------------ trang tĩnh
#
# Chính app này phục vụ luôn `public/index.html`, thay vì để Vercel phục vụ
# riêng phần tĩnh. Hai lý do:
#
# 1. Vercel định tuyến MỌI request vào hàm Python khi dự án dùng preset
#    framework, nên nếu app không tự trả trang thì `/` ra 404.
# 2. Chạy cục bộ bằng `uvicorn api.main:app` giống hệt lúc deploy — cùng
#    một gốc cho cả trang lẫn API, không có bước định tuyến nào chỉ tồn tại
#    ở một trong hai nơi rồi hỏng ở nơi kia.
#
# Phải khai sau các route /api/*: mount ở "/" khớp mọi đường dẫn, đặt trước
# thì nó nuốt luôn cả API.
PUBLIC = pathlib.Path(__file__).resolve().parents[1] / "public"
if PUBLIC.is_dir():
    from fastapi.staticfiles import StaticFiles      # noqa: E402

    app.mount("/", StaticFiles(directory=str(PUBLIC), html=True), name="public")
