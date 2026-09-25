"""Nạp dữ liệu mẫu để xem trước tab Hồ sơ khi chưa dùng đủ lâu.

Tính năng thời gian bán rã cần vài tuần dữ liệu thật mới ra số, nên lúc
thuyết trình cần có dữ liệu sẵn. Dữ liệu này là GIẢ, được ghi lùi ngày,
và phải nói rõ là dữ liệu mẫu khi trình bày.

Chạy độc lập: python -m scripts.seed_demo
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db                                              # noqa: E402
from src.models import Finances, Goal, Offer, Purchase, Sale    # noqa: E402

# (tên, danh mục, giá, trạng thái, ngày ghi, điểm đầu, ngày chấm lại,
#  điểm sau, shop, giá mục tiêu)
DEMO = [
    ("Bàn phím cơ", "tech", 2_400_000, "bought", 41, 9, 34, 6, "Shopee", 1_800_000),
    ("Máy pha cà phê", "home", 3_900_000, "skipped", 36, 8, 29, 3, "Tiki", 2_500_000),
    ("Áo khoác da", "fashion", 1_800_000, "bought", 30, 9, 23, 2, "Lazada", 0),
    ("Khoá học dựng phim", "edu", 1_200_000, "bought", 25, 7, 18, 7, "Unica", 0),
    ("Tay cầm chơi game", "tech", 1_500_000, "skipped", 21, 8, 14, 4, "Shopee", 0),
    ("Giày chạy bộ", "sport", 2_200_000, "waiting", 9, 7, 2, 5, "Tiki", 1_700_000),
]

# Lịch sử giá của riêng đôi giày, để biểu đồ trong tab Chờ đã có gì mà vẽ.
DEMO_PRICES = {"Giày chạy bộ": [(9, 2_200_000), (5, 2_050_000), (1, 1_890_000)]}

MONEY = Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)
GOALS = [Goal("Quỹ dự phòng 3 tháng", 15_000_000)]


def seed(profile: str = db.DEFAULT_PROFILE,
         path: Path = db.DEFAULT_PATH) -> int:
    """Xoá dữ liệu cũ của hồ sơ rồi nạp lại bộ mẫu. Trả về số món đã nạp."""
    db.init_db(path)
    now = datetime.now()

    with db.connect(path) as conn:
        conn.execute("DELETE FROM items WHERE profile = ?", (profile,))

    for (name, cat, price, status, d0, v0, d1, v1, shop, target) in DEMO:
        created = now - timedelta(days=d0)
        purchase = Purchase(
            name=name, price=price, uses_per_month=10, months=24,
            category=cat, desire=v0, sale=Sale(on=False),
        )
        item_id = db.add_item(
            purchase, MONEY, review_hours=168, target=target,
            goals=GOALS, offers=[Offer(shop, "", price)],
            profile=profile, path=path, now=created,
        )
        db.add_rating(item_id, v1, path=path, now=now - timedelta(days=d1))
        db.set_status(item_id, status, path=path)

        for days_ago, p in DEMO_PRICES.get(name, []):
            db.add_price(item_id, p, path=path, now=now - timedelta(days=days_ago))

    return len(DEMO)


if __name__ == "__main__":
    n = seed()
    print(f"Đã nạp {n} món dữ liệu mẫu vào {db.DEFAULT_PATH}")
    print("Lưu ý: đây là dữ liệu giả, nói rõ khi trình bày.")
