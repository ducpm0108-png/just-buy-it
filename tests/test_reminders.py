"""Kiểm thử script gửi email nhắc.

Không gửi email thật: chỉ kiểm tra phần gom dữ liệu và soạn nội dung, là
hai chỗ có thể sai. Phần smtplib chỉ là vài dòng gọi thư viện chuẩn.
"""

from datetime import datetime, timedelta
import pytest

from scripts import send_reminders as sr
from src import db
from src.models import Finances, Offer, Purchase, Sale

MOC = datetime(2026, 9, 1, 10, 0)


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_db(p)
    return p


@pytest.fixture
def money():
    return Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)


def add(path, money, name="Tai nghe", price=4_500_000, profile="Đức",
        days_ago=10, target=0, offers=None):
    """Thêm một món đã ghi `days_ago` ngày trước, hạn chấm lại sau 7 ngày."""
    p = Purchase(name=name, price=price, uses_per_month=20, months=24,
                 desire=8, sale=Sale(on=False))
    return db.add_item(p, money, review_hours=168, target=target,
                       offers=offers or [], profile=profile, path=path,
                       now=datetime.now() - timedelta(days=days_ago))


# ------------------------------------------------- gom dữ liệu

def test_gom_mon_den_han(path, money):
    add(path, money, days_ago=10)          # đến hạn (10 > 7 ngày)
    add(path, money, name="Chuột", days_ago=2)   # chưa đến hạn

    buckets = sr.collect(path)
    assert list(buckets) == ["Đức"]
    assert [r["name"] for r in buckets["Đức"]["due"]] == ["Tai nghe"]


def test_gom_theo_tung_ho_so(path, money):
    add(path, money, profile="Đức", days_ago=10)
    add(path, money, profile="Hà", name="Bàn phím", days_ago=10)

    buckets = sr.collect(path)
    assert set(buckets) == {"Đức", "Hà"}
    assert len(buckets["Đức"]["due"]) == 1
    assert len(buckets["Hà"]["due"]) == 1


def test_mon_ve_gia_muc_tieu_nhung_chua_den_han(path, money):
    """Giá về mục tiêu thì báo ngay, không cần chờ đến hạn chấm lại."""
    item_id = add(path, money, days_ago=1, target=4_000_000)
    db.add_price(item_id, 3_800_000, path=path)

    buckets = sr.collect(path)
    assert buckets["Đức"]["due"] == []
    assert [r["name"] for r in buckets["Đức"]["target"]] == ["Tai nghe"]


def test_mon_vua_den_han_vua_ve_gia_chi_nhac_mot_lan(path, money):
    """Tránh nhắc trùng: món xuất hiện ở cả hai nhóm thì chỉ tính nhóm đến hạn."""
    item_id = add(path, money, days_ago=10, target=4_000_000)
    db.add_price(item_id, 3_800_000, path=path)

    buckets = sr.collect(path)
    assert len(buckets["Đức"]["due"]) == 1
    assert buckets["Đức"]["target"] == []


def test_mon_da_mua_khong_con_bi_nhac(path, money):
    item_id = add(path, money, days_ago=10)
    db.set_status(item_id, "bought", path=path)
    assert sr.collect(path) == {}


def test_database_trong_thi_khong_gom_duoc_gi(path):
    assert sr.collect(path) == {}


# ------------------------------------------------- soạn nội dung

def test_khong_co_gi_thi_khong_soan_email(path):
    assert sr.compose("Đức", [], [], path) is None


def test_email_mot_mon_dat_tieu_de_theo_ten_mon(path, money):
    add(path, money, days_ago=10)
    due = sr.collect(path)["Đức"]["due"]
    msg = sr.compose("Đức", due, [], path)

    assert "Tai nghe" in msg["Subject"]
    assert "Còn muốn" in msg["Subject"]


def test_email_nhieu_mon_dat_tieu_de_theo_so_luong(path, money):
    add(path, money, days_ago=10)
    add(path, money, name="Chuột", days_ago=10)
    due = sr.collect(path)["Đức"]["due"]
    msg = sr.compose("Đức", due, [], path)

    assert "2 món" in msg["Subject"]


def test_email_khong_nhac_lai_diem_cu(path, money):
    """Điểm thèm muốn cũ KHÔNG được xuất hiện trong email.

    Cả cơ chế đo độ nguội dựa vào việc người dùng chấm lại mà không bị
    điểm cũ neo vào. Nhắc lại "hồi đó bạn chấm 8/10" là phá chính nó.
    """
    add(path, money, days_ago=10)
    due = sr.collect(path)["Đức"]["due"]
    body = sr.compose("Đức", due, [], path).get_content()

    assert "8/10" not in body
    assert "Đừng cố nhớ" in body


def test_email_co_ten_mon_va_gia(path, money):
    add(path, money, days_ago=10)
    due = sr.collect(path)["Đức"]["due"]
    body = sr.compose("Đức", due, [], path).get_content()

    assert "Tai nghe" in body
    assert "4.500.000" in body


def test_email_kem_link_noi_ban(path, money):
    add(path, money, days_ago=10,
        offers=[Offer("Shopee", "https://shopee.vn/x", 4_500_000)])
    due = sr.collect(path)["Đức"]["due"]
    body = sr.compose("Đức", due, [], path).get_content()

    assert "https://shopee.vn/x" in body


def test_email_bao_gia_ve_muc_tieu_co_canh_bao(path, money):
    """Báo giá rẻ phải kèm nhắc rằng rẻ không có nghĩa là cần."""
    item_id = add(path, money, days_ago=1, target=4_000_000)
    db.add_price(item_id, 3_800_000, path=path)
    target = sr.collect(path)["Đức"]["target"]
    body = sr.compose("Đức", [], target, path).get_content()

    assert "3.800.000" in body
    assert "không có nghĩa là bạn cần nó" in body


def test_email_gop_ca_hai_loai_thi_tieu_de_noi_ca_hai(path, money):
    add(path, money, name="Tai nghe", days_ago=10)
    other = add(path, money, name="Bàn phím", days_ago=1, target=2_000_000)
    db.add_price(other, 1_900_000, path=path)

    b = sr.collect(path)["Đức"]
    msg = sr.compose("Đức", b["due"], b["target"], path)
    assert "đến hạn chấm lại" in msg["Subject"]
    assert "giá mục tiêu" in msg["Subject"]


def test_so_ngay_trong_email_lay_tu_thoi_gian_ban_ra_cua_nguoi_dung(path, money):
    """Email nói số ngày chờ đã cá nhân hoá, không phải 7 ngày cố định."""
    from src.decay import Rating

    # Dựng một món có ham muốn nguội nhanh: 8 xuống 2 trong 14 ngày
    # tương ứng thời gian bán rã 7 ngày. Thêm một món nguội rất nhanh
    # để trung bình lệch khỏi 7.
    a = add(path, money, name="Món A", days_ago=30)
    db.add_rating(a, 1, path=path, now=datetime.now() - timedelta(days=27))

    b = add(path, money, name="Món B", days_ago=10)
    body = sr.compose("Đức", sr.collect(path)["Đức"]["due"], [], path).get_content()

    # Có dữ liệu nên số ngày phải khác 7 (bán rã đo được rất ngắn,
    # bị chặn ở mức tối thiểu 2 ngày).
    assert "Đã 2 ngày" in body
