"""Kiểm thử xuất và nhập dữ liệu.

Điểm quan trọng nhất: xuất ra rồi nhập lại phải được đúng dữ liệu ban đầu
(round-trip). Nếu mất mát ở giữa thì nút "tải về" thành vô dụng.
"""

from datetime import datetime, timedelta
import json
import pytest

from src import db
from src.models import Finances, Goal, Offer, Purchase, Sale

MOC = datetime(2026, 9, 25, 10, 0)


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.init_db(p)
    return p


@pytest.fixture
def money():
    return Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)


def seed(path, money, profile="Đức", name="Tai nghe"):
    """Tạo một món đầy đủ: có chấm lại, có lịch sử giá, mục tiêu, nơi bán."""
    p = Purchase(name=name, price=4_500_000, uses_per_month=20, months=24,
                 category="tech", desire=8, used_price=2_800_000,
                 sale=Sale(on=True, list_price=5_490_000, hours_left=48))
    item_id = db.add_item(
        p, money, review_hours=168, target=2_088_495,
        goals=[Goal("Quỹ dự phòng", 15_000_000)],
        offers=[Offer("Shopee", "https://shopee.vn/x", 4_500_000)],
        profile=profile, path=path, now=MOC,
    )
    db.add_rating(item_id, 3, path=path, now=MOC + timedelta(days=7))
    db.add_price(item_id, 4_100_000, path=path, now=MOC + timedelta(days=3))
    db.set_setting(profile, "email", "duc@example.com", path=path)
    return item_id


# ------------------------------------------------- xuất

def test_xuat_du_lieu_co_cau_truc_dung(path, money):
    seed(path, money)
    data = db.export_profile("Đức", path=path)

    assert data["version"] == db.EXPORT_VERSION
    assert data["profile"] == "Đức"
    assert "exported_at" in data
    assert len(data["items"]) == 1
    assert data["settings"]["email"] == "duc@example.com"


def test_xuat_kem_day_du_du_lieu_con(path, money):
    seed(path, money)
    item = db.export_profile("Đức", path=path)["items"][0]

    assert item["name"] == "Tai nghe"
    assert item["price"] == 4_500_000
    assert len(item["ratings"]) == 2          # lần đầu + lần chấm lại
    assert len(item["price_log"]) == 2        # giá lúc ghi + giá mới
    assert len(item["goals"]) == 1
    assert len(item["offers"]) == 1


def test_xuat_khong_kem_id_va_ten_ho_so(path, money):
    """Bỏ id để lúc nhập lại không đụng khoá chính; bỏ profile vì đã ở gốc."""
    seed(path, money)
    item = db.export_profile("Đức", path=path)["items"][0]
    assert "id" not in item
    assert "profile" not in item


def test_chi_xuat_ho_so_duoc_chon(path, money):
    """Không được xuất lẫn dữ liệu của hồ sơ khác."""
    seed(path, money, profile="Đức", name="Tai nghe")
    seed(path, money, profile="Hà", name="Bàn phím")

    data = db.export_profile("Đức", path=path)
    assert [i["name"] for i in data["items"]] == ["Tai nghe"]


def test_xuat_ho_so_trong(path):
    data = db.export_profile("Chưa có ai", path=path)
    assert data["items"] == [] and data["settings"] == {}


def test_xuat_ra_json_duoc(path, money):
    """Phải chuyển thành JSON được, nếu không thì không tải về được."""
    seed(path, money)
    text = json.dumps(db.export_profile("Đức", path=path), ensure_ascii=False)
    assert json.loads(text)["profile"] == "Đức"


# ------------------------------------------------- nhập

def test_xuat_roi_nhap_lai_duoc_nguyen_du_lieu(path, money, tmp_path):
    """Round-trip: xuất từ database này, nhập vào database khác, phải khớp."""
    seed(path, money)
    data = db.export_profile("Đức", path=path)

    other = tmp_path / "khac.db"
    db.init_db(other)
    n = db.import_profile(data, path=other)

    assert n == 1
    rows = db.list_items(profile="Đức", path=other)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Tai nghe"
    assert row["price"] == 4_500_000
    assert row["target_price"] == 2_088_495
    assert row["income"] == 8_000_000          # hoàn cảnh tài chính giữ nguyên

    item_id = row["id"]
    assert [r.desire for r in db.get_ratings(item_id, path=other)] == [8, 3]
    assert len(db.get_price_log(item_id, path=other)) == 2
    assert db.get_goals(item_id, path=other)[0].name == "Quỹ dự phòng"
    assert db.get_offers(item_id, path=other)[0].store == "Shopee"
    assert db.get_setting("Đức", "email", path=other) == "duc@example.com"


def test_nhap_vao_ho_so_khac_ten(path, money, tmp_path):
    seed(path, money)
    data = db.export_profile("Đức", path=path)

    other = tmp_path / "khac.db"
    db.init_db(other)
    db.import_profile(data, profile="Khách", path=other)

    assert len(db.list_items(profile="Khách", path=other)) == 1
    assert db.list_items(profile="Đức", path=other) == []


def test_nhap_mac_dinh_la_them_vao(path, money):
    seed(path, money)
    data = db.export_profile("Đức", path=path)
    db.import_profile(data, path=path)
    assert len(db.list_items(profile="Đức", path=path)) == 2


def test_nhap_voi_replace_thi_xoa_du_lieu_cu(path, money):
    seed(path, money)
    data = db.export_profile("Đức", path=path)
    db.import_profile(data, replace=True, path=path)
    assert len(db.list_items(profile="Đức", path=path)) == 1


def test_nhap_khong_anh_huong_ho_so_khac(path, money):
    seed(path, money, profile="Đức")
    seed(path, money, profile="Hà", name="Bàn phím")
    data = db.export_profile("Đức", path=path)

    db.import_profile(data, replace=True, path=path)
    assert len(db.list_items(profile="Hà", path=path)) == 1


# ------------------------------------------------- file lỗi

def test_bao_loi_khi_khong_phai_dict(path):
    with pytest.raises(db.ImportError_):
        db.import_profile(["không phải dict"], path=path)


def test_bao_loi_khi_sai_phien_ban(path):
    with pytest.raises(db.ImportError_, match="phiên bản"):
        db.import_profile({"version": 99, "items": []}, path=path)


def test_bao_loi_khi_thieu_danh_sach_items(path):
    with pytest.raises(db.ImportError_, match="items"):
        db.import_profile({"version": db.EXPORT_VERSION}, path=path)


def test_bao_loi_khi_khong_biet_nhap_vao_ho_so_nao(path):
    with pytest.raises(db.ImportError_, match="hồ sơ"):
        db.import_profile({"version": db.EXPORT_VERSION, "items": []}, path=path)


def test_bo_qua_dong_rac_thay_vi_sap(path):
    """Món không có tên thì bỏ qua, không làm sập cả lần nhập."""
    data = {
        "version": db.EXPORT_VERSION, "profile": "Đức",
        "items": [
            {"name": "Món tốt", "price": 1_000_000},
            {"price": 999},          # thiếu tên
            "không phải dict",
            {"name": "Món tốt 2", "price": 2_000_000},
        ],
    }
    assert db.import_profile(data, path=path) == 2


def test_khong_nhan_cot_la(path):
    """File lạ chèn cột không có trong lược đồ thì bị lọc, không gây lỗi SQL."""
    data = {
        "version": db.EXPORT_VERSION, "profile": "Đức",
        "items": [{"name": "Món", "price": 1_000_000,
                   "cot_la": "xoá hết đi", "id": 999, "profile": "Người khác"}],
    }
    assert db.import_profile(data, path=path) == 1
    row = db.list_items(profile="Đức", path=path)[0]
    assert row["name"] == "Món"
    assert row["profile"] == "Đức"      # không bị file ghi đè


def test_mon_thieu_ngay_thi_dien_ngay_hien_tai(path):
    data = {"version": db.EXPORT_VERSION, "profile": "Đức",
            "items": [{"name": "Món", "price": 1_000_000}]}
    db.import_profile(data, path=path)
    row = db.list_items(profile="Đức", path=path)[0]
    assert row["created_at"] and row["review_at"]
