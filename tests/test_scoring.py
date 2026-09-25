"""Kiểm thử mô hình tính điểm.

Ngoài các test kiểm tra giá trị cụ thể, ở đây có mấy test kiểm tra
TÍNH CHẤT của mô hình — những điều phải luôn đúng với mọi đầu vào.
Loại test này bắt được lỗi mà test giá trị cụ thể bỏ sót.
"""

from datetime import datetime
import pytest

from src import scoring
from src.models import Finances, Purchase, Sale
from src.scoring import Weights


@pytest.fixture
def item():
    return Purchase(name="Tai nghe", price=4_500_000, uses_per_month=20,
                    months=24, category="tech", wanted_days=10, source="ad",
                    desire=8, used_price=2_800_000,
                    sale=Sale(on=True, list_price=5_490_000, hours_left=48))


@pytest.fixture
def money():
    return Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)


@pytest.fixture
def w():
    return Weights()


BAN_NGAY = datetime(2026, 9, 25, 14, 0)    # 14 giờ, không phải giờ khuya
BAN_DEM = datetime(2026, 9, 25, 23, 30)    # 23h30, giờ khuya


# ------------------------------------------------- giá trị cụ thể

def test_diem_khop_voi_ban_mau(item, money, w):
    """Số phải khớp với bản HTML đã dựng thử, để không bị lệch khi chuyển code."""
    assert scoring.strain_score(item, money, w).value == 60
    assert scoring.impulse_score(item, w, now=BAN_NGAY).value == 47


def test_bon_o_ket_luan(w):
    """Ma trận hai chiều phải cho ra đúng bốn ô."""
    assert scoring.verdict_for(20, 20, w).key == "buy"
    assert scoring.verdict_for(20, 70, w).key == "wait"
    assert scoring.verdict_for(70, 20, w).key == "plan"
    assert scoring.verdict_for(70, 70, w).key == "no"


def test_diem_bang_dung_nguong_tinh_la_cao(w):
    """Trường hợp biên: bằng đúng ngưỡng thì tính là cao."""
    assert w.threshold == 40
    assert scoring.verdict_for(40, 20, w).key == "plan"
    assert scoring.verdict_for(39, 20, w).key == "buy"


# ------------------------------------------------- tính chất của mô hình

def test_diem_khong_doi_khi_nhan_doi_moi_trong_so(item, money):
    """Chỉ TỶ LỆ giữa các trọng số là quan trọng.

    Nhân đôi tất cả trọng số thì điểm phải giữ nguyên. Đây là điều đã
    nói với người dùng trong phần hướng dẫn, nên phải có test bảo đảm.
    """
    w1 = Weights()
    w2 = Weights(strain={k: v * 2 for k, v in w1.strain.items()},
                 impulse={k: v * 2 for k, v in w1.impulse.items()})

    assert (scoring.strain_score(item, money, w1).value
            == scoring.strain_score(item, money, w2).value)
    assert (scoring.impulse_score(item, w1, now=BAN_NGAY).value
            == scoring.impulse_score(item, w2, now=BAN_NGAY).value)


def test_ap_luc_tang_don_dieu_theo_gia(money, w):
    """Giá càng cao thì áp lực tài chính không bao giờ được giảm.

    Đây là tính chất mà thuật toán tìm giá mục tiêu dựa vào. Nếu test này
    hỏng thì chia đôi khoảng không còn đúng nữa.
    """
    diem = []
    for price in range(100_000, 20_000_001, 250_000):
        p = Purchase("x", price, 20, 24)
        diem.append(scoring.strain_score(p, money, w).value)

    assert diem == sorted(diem), "điểm áp lực phải không giảm khi giá tăng"


def test_diem_luon_trong_khoang_0_100(money, w):
    """Không đầu vào nào được làm điểm ra ngoài thang 0-100."""
    cases = [
        Purchase("rẻ", 1_000, 100, 60),
        Purchase("đắt", 500_000_000, 1, 1),
        Purchase("không dùng", 1_000_000, 0, 1),
        Purchase("miễn phí", 0, 10, 10),
    ]
    for p in cases:
        for s in (scoring.strain_score(p, money, w),
                  scoring.impulse_score(p, w, now=BAN_NGAY)):
            assert 0 <= s.value <= 100, f"{p.name} cho điểm {s.value}"


def test_tat_yeu_to_thi_yeu_to_do_khong_con_anh_huong(item, money):
    """Kéo trọng số về 0 phải tắt hẳn yếu tố đó."""
    w = Weights(strain={"share": 0, "cpu": 100, "cover": 0, "hours": 0})
    factors = scoring.strain_factors(item, money, w)
    expected = round(factors["cpu"] * 100)
    assert scoring.strain_score(item, money, w).value == expected


def test_tong_cac_phan_dong_gop_bang_diem(item, money, w):
    """Điểm phải đúng bằng tổng phần đóng góp của từng yếu tố."""
    s = scoring.strain_score(item, money, w)
    assert round(sum(pts for _, _, pts in s.parts)) == s.value


# ------------------------------------------------- từng yếu tố

def test_gio_khuya_lam_tang_boc_dong(item, w):
    """Cân nhắc lúc 23h30 phải bốc đồng hơn lúc 14h."""
    assert (scoring.impulse_score(item, w, now=BAN_DEM).value
            > scoring.impulse_score(item, w, now=BAN_NGAY).value)


def test_muon_lau_roi_thi_it_boc_dong_hon(w):
    """Muốn nhiều tháng phải ít bốc đồng hơn mới muốn hôm nay."""
    moi = Purchase("x", 1_000_000, 10, 12, wanted_days=0)
    lau = Purchase("x", 1_000_000, 10, 12, wanted_days=180)
    assert (scoring.impulse_score(lau, w, now=BAN_NGAY).value
            < scoring.impulse_score(moi, w, now=BAN_NGAY).value)


def test_yeu_to_them_muon_duoi_5_diem_la_khong():
    """Thèm muốn từ 5/10 trở xuống không tính là quá mức."""
    for d in (1, 3, 5):
        p = Purchase("x", 1_000_000, 10, 12, desire=d)
        assert scoring.impulse_factors(p, now=BAN_NGAY)["desire"] == 0
    p = Purchase("x", 1_000_000, 10, 12, desire=10)
    assert scoring.impulse_factors(p, now=BAN_NGAY)["desire"] == 1


def test_sale_con_dai_thi_khong_tao_ap_luc():
    """Sale còn hơn 7 ngày thì chưa gây áp lực phải mua ngay."""
    p = Purchase("x", 1_000_000, 10, 12, sale=Sale(on=True, hours_left=200))
    assert scoring.impulse_factors(p, now=BAN_NGAY)["urgency"] == 0


def test_sale_sap_het_thi_ap_luc_gan_toi_da():
    p = Purchase("x", 1_000_000, 10, 12, sale=Sale(on=True, hours_left=2))
    assert scoring.impulse_factors(p, now=BAN_NGAY)["urgency"] > 0.95


def test_khong_bat_sale_thi_khong_co_ap_luc_hen_gio():
    """Sale.on = False phải xoá hạn chót, tránh tính oan."""
    p = Purchase("x", 1_000_000, 10, 12, sale=Sale(on=False, hours_left=2))
    assert scoring.impulse_factors(p, now=BAN_NGAY)["urgency"] == 0


# ------------------------------------------------- giá mục tiêu

def test_gia_muc_tieu_dat_dung_nguong(item, money, w):
    """Ở giá mục tiêu điểm phải dưới ngưỡng, nhưng nhích lên là vượt."""
    tp = scoring.target_price(item, money, w)
    assert tp.needed is True

    duoi = scoring.strain_score(item.replace_price(tp.price), money, w).value
    tren = scoring.strain_score(item.replace_price(tp.price * 1.05), money, w).value
    assert duoi < w.threshold <= tren


def test_khong_can_giam_gia_khi_da_trong_tam(money, w):
    """Món rẻ so với thu nhập thì không cần giá mục tiêu."""
    p = Purchase("bút", 30_000, 20, 12)
    tp = scoring.target_price(p, money, w)
    assert tp.needed is False
    assert tp.price is None


def test_bao_khong_kha_thi_khi_ngan_sach_qua_mong(w):
    """Không còn tiền dư thì kể cả miễn phí vẫn vượt ngưỡng."""
    ngheo = Finances(income=3_000_000, fixed_costs=3_000_000, savings=0)
    p = Purchase("x", 2_000_000, 10, 12)
    tp = scoring.target_price(p, ngheo, w)
    assert tp.impossible is True
    assert tp.price is None


def test_ty_le_can_giam_nam_trong_khoang_hop_le(item, money, w):
    tp = scoring.target_price(item, money, w)
    assert 0 < tp.cut < 1
    assert tp.price < item.price


def test_nguong_thap_hon_thi_gia_muc_tieu_thap_hon(item, money):
    """Ngưỡng khắt khe hơn phải đòi giá thấp hơn."""
    de = scoring.target_price(item, money, Weights(threshold=45))
    khat_khe = scoring.target_price(item, money, Weights(threshold=30))
    assert khat_khe.price < de.price


# ------------------------------------------------- bộ trọng số dựng sẵn

@pytest.mark.parametrize("name", ["student", "saver", "stable"])
def test_cac_bo_dung_san_chay_duoc(name, item, money):
    w = scoring.PRESETS[name]
    assert 0 <= scoring.strain_score(item, money, w).value <= 100
    assert 0 <= scoring.impulse_score(item, w, now=BAN_NGAY).value <= 100


def test_bo_de_danh_khat_khe_hon_bo_thu_nhap_on_dinh(item, money):
    """Bộ 'đang để dành' phải khắt khe hơn bộ 'thu nhập ổn định'."""
    saver = scoring.PRESETS["saver"]
    stable = scoring.PRESETS["stable"]
    assert saver.threshold < stable.threshold


def test_khong_co_tiet_kiem_van_con_gia_muc_tieu_duong(w):
    """Hết tiền tiết kiệm một mình chưa làm bài toán vô nghiệm.

    Yếu tố "tiền đang có" bị tối đa hoá, nhưng nó chỉ chiếm 25 trong 100
    điểm, dưới ngưỡng 40. Ba yếu tố còn lại vẫn giảm theo giá, nên vẫn
    tồn tại mức giá dương đủ rẻ.
    """
    khong_tiet_kiem = Finances(income=8_000_000, fixed_costs=5_000_000, savings=0)
    p = Purchase("x", 2_000_000, 10, 12)
    tp = scoring.target_price(p, khong_tiet_kiem, w)

    assert tp.impossible is False
    assert tp.price > scoring.MIN_MEANINGFUL_PRICE
    assert scoring.strain_score(p.replace_price(tp.price),
                                khong_tiet_kiem, w).value < w.threshold


def test_vo_nghiem_khi_vua_het_tiet_kiem_vua_khong_con_tien_du(w):
    """Trường hợp biên phát hiện được nhờ test, đã sửa trong target_price.

    Vừa không có tiết kiệm vừa không còn tiền dư thì yếu tố "tiền dư" bị
    tối đa hoá luôn, cộng với "tiền đang có" là vượt ngưỡng ở mọi mức giá
    dương. Phép chia đôi khoảng hội tụ về 0, và hàm phải báo `impossible`
    chứ không trả về "giá cần xuống dưới 0 đồng".
    """
    kiet = Finances(income=3_000_000, fixed_costs=3_000_000, savings=0)
    p = Purchase("x", 2_000_000, 10, 12)
    tp = scoring.target_price(p, kiet, w)

    assert tp.impossible is True
    assert tp.price is None
