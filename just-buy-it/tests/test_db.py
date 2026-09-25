"""Kiểm thử lớp lưu trữ.

Mỗi test dùng một file database riêng trong thư mục tạm (tmp_path của
pytest), nên các test không ảnh hưởng lẫn nhau và không đụng vào dữ liệu
thật trong data/.
"""

from datetime import datetime, timedelta
import pytest

from src import db
from src.models import Finances, Goal, Offer, Purchase, Sale

MOC = datetime(2026, 9, 25, 10, 0)


@pytest.fixture
def path(tmp_path):
    """Đường dẫn tới một database trống, khởi tạo sẵn các bảng."""
    p = tmp_path / "test.db"
    db.init_db(p)
    return p


@pytest.fixture
def item():
    return Purchase(name="Tai nghe", price=4_500_000, uses_per_month=20,
                    months=24, category="tech", wanted_days=10, source="ad",
                    desire=8, used_price=2_800_000,
                    sale=Sale(on=True, list_price=5_490_000, hours_left=48))


@pytest.fixture
def money():
    return Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)


def test_init_db_goi_nhieu_lan_khong_loi(tmp_path):
    p = tmp_path / "a.db"
    db.init_db(p)
    db.init_db(p)          # không được báo lỗi
    assert p.exists()


def test_luu_va_doc_lai_mon_do(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, target=2_088_495,
                          path=path, now=MOC)
    row = db.get_item(item_id, path=path)

    assert row["name"] == "Tai nghe"
    assert row["price"] == 4_500_000
    assert row["category"] == "tech"
    assert row["status"] == "waiting"
    assert row["target_price"] == 2_088_495


def test_hoan_canh_tai_chinh_duoc_luu_kem(path, item, money):
    """Thu nhập lúc ra quyết định phải lưu theo món đồ."""
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    row = db.get_item(item_id, path=path)

    assert row["income"] == 8_000_000
    assert row["fixed_costs"] == 5_000_000
    f = db.row_to_finances(row)
    assert f.discretionary == 3_000_000


def test_muc_them_muon_thanh_lan_cham_dau_tien(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    ratings = db.get_ratings(item_id, path=path)

    assert len(ratings) == 1
    assert ratings[0].desire == 8


def test_gia_luc_luu_thanh_dong_dau_lich_su_gia(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    log = db.get_price_log(item_id, path=path)

    assert len(log) == 1
    assert log[0][1] == 4_500_000


def test_muc_tieu_va_noi_ban_duoc_luu_kem(path, item, money):
    item_id = db.add_item(
        item, money, review_hours=168, path=path, now=MOC,
        goals=[Goal("Quỹ dự phòng", 15_000_000), Goal("Bỏ trống", 0)],
        offers=[Offer("Shopee", "https://shopee.vn/x", 4_500_000),
                Offer("", "", 0)],
    )

    goals = db.get_goals(item_id, path=path)
    offers = db.get_offers(item_id, path=path)

    assert len(goals) == 1               # mục tiêu không có số tiền bị bỏ
    assert goals[0].name == "Quỹ dự phòng"
    assert len(offers) == 1              # nơi bán trống cũng bị bỏ
    assert offers[0].store == "Shopee"


def test_cham_lai_va_ghi_gia(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)

    db.add_rating(item_id, 4, path=path, now=MOC + timedelta(days=7))
    db.add_price(item_id, 4_100_000, path=path, now=MOC + timedelta(days=3))
    db.add_price(item_id, 3_900_000, path=path, now=MOC + timedelta(days=7))

    ratings = db.get_ratings(item_id, path=path)
    log = db.get_price_log(item_id, path=path)

    assert [r.desire for r in ratings] == [8, 4]
    assert [p for _, p in log] == [4_500_000, 4_100_000, 3_900_000]


def test_doi_trang_thai(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.set_status(item_id, "bought", path=path)
    assert db.get_item(item_id, path=path)["status"] == "bought"


def test_trang_thai_khong_hop_le_bi_tu_choi(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    with pytest.raises(ValueError):
        db.set_status(item_id, "xoa-luon", path=path)


def test_loc_theo_trang_thai(path, item, money):
    a = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.set_status(a, "bought", path=path)

    assert len(db.list_items(path=path)) == 2
    assert len(db.list_items(status="waiting", path=path)) == 1
    assert len(db.list_items(status="bought", path=path)) == 1


# ------------------------------------------------- nhắc chấm lại

def test_chua_den_han_thi_khong_hien_trong_danh_sach_nhac(path, item, money):
    db.add_item(item, money, review_hours=168, path=path, now=MOC)
    due = db.items_due_for_review(path=path, now=MOC + timedelta(days=3))
    assert due == []


def test_den_han_thi_hien_trong_danh_sach_nhac(path, item, money):
    db.add_item(item, money, review_hours=168, path=path, now=MOC)
    due = db.items_due_for_review(path=path, now=MOC + timedelta(days=8))
    assert len(due) == 1
    assert due[0]["name"] == "Tai nghe"


def test_mon_da_mua_khong_con_bi_nhac(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.set_status(item_id, "bought", path=path)
    assert db.items_due_for_review(path=path, now=MOC + timedelta(days=8)) == []


def test_han_cham_lai_duoc_doi_len_khi_sale_sap_het(path, item, money):
    """Sale còn 48 giờ thì hạn chấm lại phải sớm hơn 7 ngày."""
    db.add_item(item, money, review_hours=42, path=path, now=MOC)
    due = db.items_due_for_review(path=path, now=MOC + timedelta(hours=43))
    assert len(due) == 1


# ------------------------------------------------- báo giá về mục tiêu

def test_gia_ve_muc_tieu_thi_bao(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, target=4_000_000,
                          path=path, now=MOC)
    db.add_price(item_id, 3_800_000, path=path, now=MOC + timedelta(days=2))

    hit = db.items_at_target_price(path=path)
    assert len(hit) == 1
    assert hit[0]["current_price"] == 3_800_000


def test_gia_chua_ve_muc_tieu_thi_khong_bao(path, item, money):
    item_id = db.add_item(item, money, review_hours=168, target=3_000_000,
                          path=path, now=MOC)
    db.add_price(item_id, 4_200_000, path=path, now=MOC + timedelta(days=2))
    assert db.items_at_target_price(path=path) == []


def test_chi_xet_gia_ghi_gan_nhat(path, item, money):
    """Giá từng xuống thấp rồi tăng lại thì không còn tính là đạt ngưỡng."""
    item_id = db.add_item(item, money, review_hours=168, target=4_000_000,
                          path=path, now=MOC)
    db.add_price(item_id, 3_500_000, path=path, now=MOC + timedelta(days=1))
    db.add_price(item_id, 4_600_000, path=path, now=MOC + timedelta(days=2))
    assert db.items_at_target_price(path=path) == []


# ------------------------------------------------- thống kê

def test_thong_ke_ho_so(path, item, money):
    a = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    b = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.add_item(item, money, review_hours=168, path=path, now=MOC)

    db.set_status(a, "bought", path=path)
    db.set_status(b, "skipped", path=path)

    stats = db.profile_stats(path=path)
    assert stats["n_items"] == 3
    assert stats["n_bought"] == 1
    assert stats["n_skipped"] == 1
    assert stats["saved"] == 4_500_000
    assert stats["total_value"] == 13_500_000


def test_thong_ke_tren_database_trong(path):
    stats = db.profile_stats(path=path)
    assert stats["n_items"] == 0
    assert stats["total_value"] == 0
    assert stats["n_regret"] == 0


def test_dem_mon_da_mua_ma_gio_hoi_tiec(path, item, money):
    """Đã mua nhưng lần chấm gần nhất còn 4/10 trở xuống thì tính là tiếc."""
    a = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.set_status(a, "bought", path=path)
    db.add_rating(a, 2, path=path, now=MOC + timedelta(days=10))

    b = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.set_status(b, "bought", path=path)
    db.add_rating(b, 9, path=path, now=MOC + timedelta(days=10))

    stats = db.profile_stats(path=path)
    assert stats["n_regret"] == 1
    assert stats["regret_value"] == 4_500_000


def test_lay_chuoi_cham_diem_cua_moi_mon(path, item, money):
    a = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.add_rating(a, 4, path=path, now=MOC + timedelta(days=7))
    db.add_item(item, money, review_hours=168, path=path, now=MOC)

    series = db.all_rating_series(path=path)
    assert len(series) == 2
    assert sorted(len(s) for s in series) == [1, 2]


def test_xoa_mon_do_thi_xoa_luon_du_lieu_lien_quan(path, item, money):
    """Khoá ngoại phải xoá theo (ON DELETE CASCADE)."""
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC,
                          goals=[Goal("Quỹ", 1_000_000)])
    with db.connect(path) as conn:
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))

    assert db.get_ratings(item_id, path=path) == []
    assert db.get_price_log(item_id, path=path) == []
    assert db.get_goals(item_id, path=path) == []


# ------------------------------------------------- hồ sơ (cá nhân hoá)

def test_du_lieu_duoc_tach_theo_ho_so(path, item, money):
    """Mỗi hồ sơ chỉ thấy dữ liệu của mình.

    Đây là cơ chế cá nhân hoá: một cột `profile`, không cần đăng nhập.
    """
    db.add_item(item, money, review_hours=168, profile="Đức", path=path, now=MOC)
    db.add_item(item, money, review_hours=168, profile="Đức", path=path, now=MOC)
    db.add_item(item, money, review_hours=168, profile="Hà", path=path, now=MOC)

    assert len(db.list_items(profile="Đức", path=path)) == 2
    assert len(db.list_items(profile="Hà", path=path)) == 1
    assert len(db.list_items(path=path)) == 3        # None = tất cả hồ sơ


def test_liet_ke_cac_ho_so_da_co(path, item, money):
    db.add_item(item, money, review_hours=168, profile="Hà", path=path, now=MOC)
    db.add_item(item, money, review_hours=168, profile="Đức", path=path, now=MOC)
    assert db.list_profiles(path=path) == ["Hà", "Đức"] or \
           db.list_profiles(path=path) == ["Đức", "Hà"]
    assert len(db.list_profiles(path=path)) == 2


def test_ho_so_mac_dinh_khi_khong_chi_dinh(path, item, money):
    db.add_item(item, money, review_hours=168, path=path, now=MOC)
    assert db.get_item(1, path=path)["profile"] == db.DEFAULT_PROFILE


def test_thong_ke_loc_theo_ho_so(path, item, money):
    a = db.add_item(item, money, review_hours=168, profile="Đức", path=path, now=MOC)
    db.add_item(item, money, review_hours=168, profile="Hà", path=path, now=MOC)
    db.set_status(a, "skipped", path=path)

    duc = db.profile_stats(profile="Đức", path=path)
    ha = db.profile_stats(profile="Hà", path=path)

    assert duc["n_items"] == 1 and duc["saved"] == 4_500_000
    assert ha["n_items"] == 1 and ha["saved"] == 0
    assert db.profile_stats(path=path)["n_items"] == 2


def test_nhac_cham_lai_loc_theo_ho_so(path, item, money):
    db.add_item(item, money, review_hours=168, profile="Đức", path=path, now=MOC)
    db.add_item(item, money, review_hours=168, profile="Hà", path=path, now=MOC)
    sau = MOC + timedelta(days=8)

    assert len(db.items_due_for_review(profile="Đức", path=path, now=sau)) == 1
    assert len(db.items_due_for_review(path=path, now=sau)) == 2


def test_chuoi_cham_diem_loc_theo_ho_so(path, item, money):
    a = db.add_item(item, money, review_hours=168, profile="Đức", path=path, now=MOC)
    db.add_rating(a, 4, path=path, now=MOC + timedelta(days=7))
    db.add_item(item, money, review_hours=168, profile="Hà", path=path, now=MOC)

    assert len(db.all_rating_series(profile="Đức", path=path)) == 1
    assert len(db.all_rating_series(path=path)) == 2


# ------------------------------------------------- cài đặt & trọng số

def test_luu_va_doc_lai_cai_dat(path):
    db.set_setting("Đức", "email", "duc@example.com", path=path)
    assert db.get_setting("Đức", "email", path=path) == "duc@example.com"


def test_cai_dat_chua_co_thi_tra_ve_mac_dinh(path):
    assert db.get_setting("Đức", "email", path=path) is None
    assert db.get_setting("Đức", "email", "(trống)", path=path) == "(trống)"


def test_ghi_de_cai_dat_cu(path):
    db.set_setting("Đức", "email", "cu@example.com", path=path)
    db.set_setting("Đức", "email", "moi@example.com", path=path)
    assert db.get_setting("Đức", "email", path=path) == "moi@example.com"


def test_cai_dat_tach_theo_ho_so(path):
    db.set_setting("Đức", "email", "duc@example.com", path=path)
    db.set_setting("Hà", "email", "ha@example.com", path=path)
    assert db.get_setting("Đức", "email", path=path) == "duc@example.com"
    assert db.get_setting("Hà", "email", path=path) == "ha@example.com"


def test_trong_so_luu_rieng_tung_ho_so(path):
    """Mỗi hồ sơ giữ bộ trọng số riêng — nếu không thì hiệu chỉnh vô nghĩa."""
    db.save_weights("Đức", {"strain": {"share": 50}, "threshold": 30}, path=path)

    duc = db.load_weights("Đức", path=path)
    assert duc["strain"]["share"] == 50
    assert duc["threshold"] == 30
    assert db.load_weights("Hà", path=path) is None


def test_trong_so_hong_thi_coi_nhu_chua_co(path):
    """JSON hỏng không được làm app chết, chỉ cần quay về mặc định."""
    db.set_setting("Đức", "weights", "{không phải json", path=path)
    assert db.load_weights("Đức", path=path) is None


def test_dung_lai_boi_canh_quyet_dinh(path, item, money):
    """decision_context phải dựng lại mức thèm muốn LÚC ĐÓ, không phải hiện tại."""
    item_id = db.add_item(item, money, review_hours=168, path=path, now=MOC)
    db.add_rating(item_id, 2, path=path, now=MOC + timedelta(days=7))

    row = db.get_item(item_id, path=path)
    purchase, fin, decided_at, ratings = db.decision_context(row, path=path)

    assert purchase.desire == 8          # lần chấm đầu, không phải 2
    assert decided_at == MOC
    assert fin.income == 8_000_000
    assert [r.desire for r in ratings] == [8, 2]


def test_dung_lai_thoi_han_sale_luc_ra_quyet_dinh(path, item, money):
    """Bảng lưu thời điểm sale kết thúc; mô hình cần số giờ còn lại lúc đó."""
    item_id = db.add_item(item, money, review_hours=42, path=path, now=MOC)
    row = db.get_item(item_id, path=path)
    purchase, *_ = db.decision_context(row, path=path)

    assert purchase.sale.on is True
    assert purchase.sale.hours_left == pytest.approx(48, abs=0.1)
