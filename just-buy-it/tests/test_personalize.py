"""Kiểm thử phần cá nhân hoá."""

from datetime import datetime, timedelta
import pytest

from src import personalize as pz
from src.decay import HalfLife, Rating
from src.models import Finances, Purchase
from src.scoring import Weights

MOC = datetime(2026, 9, 1, 14, 0)


# ------------------------------------------------- thời gian chờ riêng

def test_chua_co_du_lieu_thi_cho_7_ngay():
    hl = HalfLife(days=10, from_data=False)
    assert pz.cooling_days(hl) == pz.DEFAULT_COOLING_DAYS


def test_co_du_lieu_thi_cho_bang_thoi_gian_ban_ra():
    hl = HalfLife(days=5, from_data=True, sample_size=6)
    assert pz.cooling_days(hl) == 5


def test_ham_muon_nguoi_rat_nhanh_van_cho_toi_thieu():
    """Bán rã nửa ngày thì vẫn phải chờ tối thiểu 2 ngày."""
    hl = HalfLife(days=0.5, from_data=True, sample_size=5)
    assert pz.cooling_days(hl) == pz.MIN_COOLING_DAYS


def test_ham_muon_rat_ben_thi_cho_toi_da():
    """Bán rã 60 ngày thì chặn ở 21 ngày, không bắt chờ hai tháng."""
    hl = HalfLife(days=60, from_data=True, sample_size=5)
    assert pz.cooling_days(hl) == pz.MAX_COOLING_DAYS


def test_quy_doi_sang_gio():
    hl = HalfLife(days=5, from_data=True, sample_size=6)
    assert pz.cooling_hours(hl) == 120


@pytest.mark.parametrize("days,from_data", [
    (10, False), (0.5, True), (5, True), (60, True),
])
def test_luon_co_cau_giai_thich(days, from_data):
    hl = HalfLife(days=days, from_data=from_data, sample_size=5)
    text = pz.cooling_explanation(hl)
    assert isinstance(text, str) and len(text) > 20


# ------------------------------------------------- gán nhãn kết quả

def test_gan_nhan_bon_truong_hop():
    assert pz.label_outcome("bought", 9) == "mua_dung"
    assert pz.label_outcome("bought", 2) == "mua_ho"
    assert pz.label_outcome("skipped", 2) == "bo_dung"
    assert pz.label_outcome("skipped", 9) == "bo_lo"


def test_mon_dang_cho_thi_chua_co_ket_qua():
    assert pz.label_outcome("waiting", 8) is None


def test_diem_o_giua_thi_khong_ket_luan():
    """5/10 không rõ là còn muốn hay hết muốn, nên bỏ qua."""
    assert pz.label_outcome("bought", 5) is None
    assert pz.label_outcome("skipped", 5) is None


def test_moi_nhan_deu_co_mo_ta_tieng_viet():
    for key in ("mua_dung", "mua_ho", "bo_dung", "bo_lo"):
        assert key in pz.LABELS


# ------------------------------------------------- chạy lại mô hình

class FakeRow(dict):
    """Giả lập sqlite3.Row bằng dict, để test không cần database."""

    def __getitem__(self, k):
        return super().__getitem__(k)


def make_case(item_id: int, status: str, first: int, last: int,
              price: float = 2_000_000, wanted_days: float = 1,
              source: str = "sale", owns: bool = False):
    """Dựng một quyết định đã qua kèm bối cảnh của nó."""
    row = FakeRow(id=item_id, name=f"Món {item_id}", price=price, status=status)
    ratings = [Rating(MOC, first), Rating(MOC + timedelta(days=7), last)]

    purchase = Purchase(name=row["name"], price=price, uses_per_month=10,
                        months=12, wanted_days=wanted_days, source=source,
                        owns_similar=owns, desire=first)
    money = Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)
    return row, ratings, (purchase, money, MOC)


def build_lookups(cases):
    """Dựng các hàm tra cứu mà replay và factor_gaps cần."""
    rows = [c[0] for c in cases]
    ratings_map = {c[0]["id"]: c[1] for c in cases}
    ctx_map = {c[0]["id"]: c[2] for c in cases}
    return rows, (lambda r: ratings_map[r["id"]]), (lambda r: ctx_map[r["id"]])


def test_replay_bo_qua_mon_chua_cham_lai():
    row, _, ctx = make_case(1, "bought", 9, 6)
    rows = [row]
    out = pz.replay(rows, lambda r: [Rating(MOC, 9)], lambda r: ctx,
                    Weights())
    assert out == []


def test_replay_bo_qua_mon_dang_cho():
    cases = [make_case(1, "waiting", 9, 5)]
    rows, ratings_of, ctx_of = build_lookups(cases)
    assert pz.replay(rows, ratings_of, ctx_of, Weights()) == []


def test_replay_tra_ve_du_thong_tin():
    cases = [make_case(1, "bought", 9, 2)]
    rows, ratings_of, ctx_of = build_lookups(cases)
    out = pz.replay(rows, ratings_of, ctx_of, Weights())

    assert len(out) == 1
    o = out[0]
    assert o.item_id == 1
    assert o.label == "mua_ho"
    assert o.first_desire == 9 and o.last_desire == 2
    assert 0 <= o.strain <= 100 and 0 <= o.impulse <= 100
    assert isinstance(o.went_ahead, bool) and isinstance(o.was_right, bool)


def test_khuyen_dung_mon_mua_ho_la_dung():
    """Món bốc đồng rõ ràng, mua rồi hết muốn — mô hình nên đã khuyên dừng."""
    cases = [make_case(1, "bought", 10, 1, price=6_000_000,
                       wanted_days=0.2, source="sale", owns=True)]
    rows, ratings_of, ctx_of = build_lookups(cases)
    o = pz.replay(rows, ratings_of, ctx_of, Weights())[0]

    assert o.went_ahead is False
    assert o.was_right is True


# ------------------------------------------------- ma trận nhầm lẫn

def outcome(went_ahead: bool, was_right: bool, price: float = 1_000_000):
    return pz.Outcome(item_id=1, name="x", price=price, label="mua_ho",
                      went_ahead=went_ahead, was_right=was_right,
                      verdict="X", strain=50, impulse=50,
                      first_desire=8, last_desire=3)


def test_ma_tran_nham_lan_dem_dung_bon_o():
    outs = [
        outcome(True, True), outcome(True, True),       # khuyên mua, đúng
        outcome(False, True),                            # khuyên dừng, đúng
        outcome(True, False, price=3_000_000),           # khuyên mua, hoá ra hớ
        outcome(False, False, price=2_000_000),          # khuyên dừng, vẫn muốn
    ]
    cal = pz.calibrate(outs)

    assert cal.n == 5
    assert cal.correct_go == 2
    assert cal.correct_hold == 1
    assert cal.false_go == 1
    assert cal.false_hold == 1
    assert cal.n_right == 3
    assert cal.accuracy == pytest.approx(0.6)
    assert cal.wasted_value == 3_000_000
    assert cal.missed_value == 2_000_000


def test_ma_tran_tren_danh_sach_rong():
    cal = pz.calibrate([])
    assert cal.n == 0 and cal.accuracy == 0 and cal.enough_data is False


def test_duoi_5_quyet_dinh_thi_chua_du_du_lieu():
    assert pz.calibrate([outcome(True, True)] * 4).enough_data is False
    assert pz.calibrate([outcome(True, True)] * 5).enough_data is True


# ------------------------------------------------- yếu tố phân biệt

def test_yeu_to_da_co_mon_thay_the_phan_biet_duoc():
    """Dựng dữ liệu mà các món mua hớ đều đã có món thay thế.

    Yếu tố "đã có món thay thế" phải nổi lên là yếu tố phân biệt tốt nhất,
    vì nó đúng bằng 1 ở nhóm hớ và bằng 0 ở nhóm đúng.
    """
    cases = [
        make_case(1, "bought", 9, 2, owns=True),
        make_case(2, "bought", 9, 1, owns=True),
        make_case(3, "bought", 8, 9, owns=False),
        make_case(4, "bought", 8, 8, owns=False),
    ]
    rows, ratings_of, ctx_of = build_lookups(cases)
    gaps = pz.factor_gaps(rows, ratings_of, ctx_of, Weights())

    top = gaps[0]
    assert top.key == "owns"
    assert top.mean_regret == 1.0
    assert top.mean_good == 0.0
    assert top.gap == pytest.approx(1.0)


def test_yeu_to_khong_phan_biet_thi_chenh_lech_bang_0():
    """Yếu tố giống nhau ở cả hai nhóm thì chênh lệch phải bằng 0."""
    cases = [
        make_case(1, "bought", 9, 2, price=2_000_000),
        make_case(2, "bought", 8, 9, price=2_000_000),
    ]
    rows, ratings_of, ctx_of = build_lookups(cases)
    gaps = pz.factor_gaps(rows, ratings_of, ctx_of, Weights())

    # Giá giống nhau nên các yếu tố tài chính không phân biệt được gì.
    by_key = {g.key: g for g in gaps}
    for key in ("share", "cpu", "cover", "hours"):
        assert by_key[key].gap == pytest.approx(0.0)


def test_khong_co_mon_nao_da_ket_luan_thi_tra_ve_rong():
    cases = [make_case(1, "waiting", 9, 5)]
    rows, ratings_of, ctx_of = build_lookups(cases)
    assert pz.factor_gaps(rows, ratings_of, ctx_of, Weights()) == []


def test_chi_xet_mon_da_mua_bo_qua_mon_da_bo():
    """Yếu tố phân biệt chỉ so mua đúng với mua hớ, không tính món đã bỏ."""
    cases = [
        make_case(1, "bought", 9, 2, owns=True),
        make_case(2, "bought", 8, 9, owns=False),
        make_case(3, "skipped", 9, 1, owns=True),    # không được tính
    ]
    rows, ratings_of, ctx_of = build_lookups(cases)
    gaps = pz.factor_gaps(rows, ratings_of, ctx_of, Weights())
    by_key = {g.key: g for g in gaps}
    assert by_key["owns"].mean_regret == 1.0     # chỉ từ món số 1


# ------------------------------------------------- gợi ý

def test_it_du_lieu_thi_noi_thang_la_it():
    msgs = pz.suggestions(pz.calibrate([outcome(True, True)] * 3), [])
    assert len(msgs) == 1
    assert "5 món" in msgs[0]


def test_bao_loi_khuyen_mua_ma_hoi():
    outs = [outcome(True, True)] * 4 + [outcome(True, False, price=3_000_000)]
    msgs = pz.suggestions(pz.calibrate(outs), [])
    joined = " ".join(msgs)
    assert "quá dễ dãi" in joined


def test_khong_co_loi_thi_khuyen_giu_nguyen():
    msgs = pz.suggestions(pz.calibrate([outcome(True, True)] * 6), [])
    assert any("Giữ nguyên" in m for m in msgs)


def test_goi_y_tang_yeu_to_phan_biet_tot_nhat():
    outs = [outcome(True, True)] * 5
    gaps = [pz.FactorGap("owns", "Đã có món thay thế", "impulse", 1.0, 0.0, 1.0)]
    msgs = pz.suggestions(pz.calibrate(outs), gaps)
    assert any("Đã có món thay thế" in m for m in msgs)


# ------------------------------------------------- định dạng câu chữ

@pytest.mark.parametrize("days,from_data", [
    (10, False), (0.5, True), (1.4, True), (5, True), (60, True),
])
def test_cau_giai_thich_ket_thuc_bang_dau_cham(days, from_data):
    """Bắt lỗi từng gặp: đổi dấu thập phân sang dấu phẩy bằng replace() trên
    cả câu làm dấu chấm cuối câu biến thành dấu phẩy."""
    hl = HalfLife(days=days, from_data=from_data, sample_size=5)
    text = pz.cooling_explanation(hl)
    assert text.rstrip().endswith("."), f"câu kết thúc sai: {text!r}"


def test_goi_y_khong_bi_hong_dau_cau():
    """Cùng lỗi replace(): số tiền có dấu phân cách không được làm hỏng câu."""
    outs = [outcome(True, True)] * 4 + [outcome(True, False, price=3_000_000)]
    gaps = [pz.FactorGap("owns", "Đã có món thay thế", "impulse", 0.8, 0.2, 0.6)]
    for msg in pz.suggestions(pz.calibrate(outs), gaps):
        assert msg.rstrip().endswith((".", "%", ")")), f"câu lỗi: {msg!r}"
        assert ". hoặc" not in msg
        assert "5 điểm." not in msg
