"""Lớp lưu trữ dữ liệu bằng sqlite3.

Dùng `sqlite3` của thư viện chuẩn: không cần cài thêm gì, không cần tài
khoản, không cần server. Cả cơ sở dữ liệu là một file nằm cạnh code.

Mọi hàm ở đây nhận và trả về kiểu dữ liệu Python thuần, không biết gì về
Streamlit, nên script nhắc email cũng dùng lại được y nguyên.

Lưu ý bảo mật: file .db chứa thu nhập và tiền tiết kiệm của người dùng.
Đã thêm `data/*.db` vào .gitignore, đừng commit nó lên repo công khai.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from .decay import Rating
from .models import Finances, Goal, Offer, Purchase, Sale

DEFAULT_PATH = Path("data/justbuyit.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Tên hồ sơ, để phân tách dữ liệu giữa nhiều người dùng chung một máy.
    -- Đây là DANH TÍNH, không phải XÁC THỰC: đủ để cá nhân hoá, nhưng
    -- không chứng minh được ai là ai. Xem phần giới hạn trong README.
    profile         TEXT    NOT NULL DEFAULT 'Tôi',
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT 'other',
    price           REAL    NOT NULL,
    uses_per_month  REAL    NOT NULL,
    months          INTEGER NOT NULL,
    wanted_days     REAL    NOT NULL DEFAULT 10,
    source          TEXT    NOT NULL DEFAULT 'need',
    owns_similar    INTEGER NOT NULL DEFAULT 0,
    used_price      REAL,
    -- Hoàn cảnh tài chính lúc ra quyết định, lưu kèm để sau này xem lại
    -- còn hiểu được vì sao lúc đó kết luận như vậy.
    income          REAL    NOT NULL DEFAULT 0,
    fixed_costs     REAL    NOT NULL DEFAULT 0,
    savings         REAL    NOT NULL DEFAULT 0,
    list_price      REAL,
    sale_end        TEXT,
    target_price    REAL,
    created_at      TEXT    NOT NULL,
    review_at       TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'waiting'
);

CREATE TABLE IF NOT EXISTS ratings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id   INTEGER NOT NULL,
    rated_at  TEXT    NOT NULL,
    desire    INTEGER NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS price_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER NOT NULL,
    checked_at  TEXT    NOT NULL,
    price       REAL    NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS goals (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id  INTEGER NOT NULL,
    name     TEXT    NOT NULL,
    amount   REAL    NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS offers (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id  INTEGER NOT NULL,
    store    TEXT    NOT NULL DEFAULT '',
    url      TEXT    NOT NULL DEFAULT '',
    price    REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
);

-- Cài đặt riêng của từng hồ sơ: trọng số đã hiệu chỉnh, email nhận nhắc…
-- Lưu dạng khoá–giá trị để thêm cài đặt mới không phải đổi lược đồ.
CREATE TABLE IF NOT EXISTS settings (
    profile  TEXT NOT NULL,
    key      TEXT NOT NULL,
    value    TEXT NOT NULL,
    PRIMARY KEY (profile, key)
);

CREATE INDEX IF NOT EXISTS idx_ratings_item   ON ratings(item_id);
CREATE INDEX IF NOT EXISTS idx_price_item     ON price_log(item_id);
CREATE INDEX IF NOT EXISTS idx_items_status   ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_profile  ON items(profile);
"""

DEFAULT_PROFILE = "Tôi"


@contextmanager
def connect(path: Path = DEFAULT_PATH) -> Iterator[sqlite3.Connection]:
    """Mở kết nối, tự đóng khi xong, tự commit nếu không có lỗi.

    Dùng `with connect() as conn:` giống như `with open(...)` ở Buổi 3.
    """
    path = Path(path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row          # cho phép truy cập theo tên cột
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path = DEFAULT_PATH) -> None:
    """Tạo các bảng nếu chưa có. Gọi được nhiều lần không sao."""
    with connect(path) as conn:
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------- ghi dữ liệu

def add_item(p: Purchase, f: Finances, review_hours: float,
             target: Optional[float] = None,
             goals: Optional[List[Goal]] = None,
             offers: Optional[List[Offer]] = None,
             profile: str = DEFAULT_PROFILE,
             path: Path = DEFAULT_PATH,
             now: Optional[datetime] = None) -> int:
    """Lưu một món đồ vào danh sách chờ. Trả về id của món vừa lưu.

    Mức thèm muốn hiện tại được ghi luôn thành lần chấm đầu tiên, và giá
    hiện tại thành dòng đầu của lịch sử giá.
    """
    now = now or datetime.now()
    review_at = now + timedelta(hours=review_hours)
    sale_end = (now + timedelta(hours=p.sale.hours_left)
                if p.sale.on and p.sale.hours_left != float("inf") else None)

    with connect(path) as conn:
        cur = conn.execute(
            """INSERT INTO items
               (profile, name, category, price, uses_per_month, months, wanted_days,
                source, owns_similar, used_price, income, fixed_costs, savings,
                list_price, sale_end, target_price, created_at, review_at, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'waiting')""",
            (profile, p.name, p.category, p.price, p.uses_per_month, p.months,
             p.wanted_days, p.source, int(p.owns_similar), p.used_price,
             f.income, f.fixed_costs, f.savings,
             p.sale.list_price if p.sale.on else None,
             sale_end.isoformat() if sale_end else None,
             target, now.isoformat(), review_at.isoformat()),
        )
        item_id = cur.lastrowid

        conn.execute(
            "INSERT INTO ratings (item_id, rated_at, desire) VALUES (?,?,?)",
            (item_id, now.isoformat(), p.desire),
        )
        conn.execute(
            "INSERT INTO price_log (item_id, checked_at, price) VALUES (?,?,?)",
            (item_id, now.isoformat(), p.price),
        )
        for g in (goals or []):
            if g.name and g.amount > 0:
                conn.execute(
                    "INSERT INTO goals (item_id, name, amount) VALUES (?,?,?)",
                    (item_id, g.name, g.amount),
                )
        for o in (offers or []):
            if o.store or o.url:
                conn.execute(
                    "INSERT INTO offers (item_id, store, url, price) VALUES (?,?,?,?)",
                    (item_id, o.store, o.url, o.price),
                )

    return item_id


def add_rating(item_id: int, desire: int, path: Path = DEFAULT_PATH,
               now: Optional[datetime] = None) -> None:
    """Ghi một lần chấm lại mức thèm muốn."""
    now = now or datetime.now()
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO ratings (item_id, rated_at, desire) VALUES (?,?,?)",
            (item_id, now.isoformat(), desire),
        )


def add_price(item_id: int, price: float, path: Path = DEFAULT_PATH,
              now: Optional[datetime] = None) -> None:
    """Ghi lại giá thấy được hôm nay."""
    now = now or datetime.now()
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO price_log (item_id, checked_at, price) VALUES (?,?,?)",
            (item_id, now.isoformat(), price),
        )


def set_status(item_id: int, status: str, path: Path = DEFAULT_PATH) -> None:
    """Đổi trạng thái món đồ: waiting, bought hoặc skipped."""
    if status not in ("waiting", "bought", "skipped"):
        raise ValueError(f"Trạng thái không hợp lệ: {status}")
    with connect(path) as conn:
        conn.execute("UPDATE items SET status = ? WHERE id = ?", (status, item_id))


# ---------------------------------------------------------------- đọc dữ liệu

def _where(status: Optional[str], profile: Optional[str]) -> tuple:
    """Dựng mệnh đề WHERE cho các bộ lọc tuỳ chọn.

    `profile=None` nghĩa là không lọc theo hồ sơ — dùng khi muốn xem toàn bộ
    dữ liệu, ví dụ để thống kê chéo nhiều người dùng.
    """
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if profile:
        clauses.append("profile = ?")
        params.append(profile)
    sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return sql, tuple(params)


def list_profiles(path: Path = DEFAULT_PATH) -> List[str]:
    """Các tên hồ sơ đã có dữ liệu, để hiện trong ô chọn."""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT profile FROM items ORDER BY profile"
        ).fetchall()
    return [r["profile"] for r in rows]


def list_items(status: Optional[str] = None,
               profile: Optional[str] = None,
               path: Path = DEFAULT_PATH) -> List[sqlite3.Row]:
    """Danh sách món đồ, mới nhất trước. Lọc theo trạng thái và hồ sơ nếu cần."""
    where, params = _where(status, profile)
    with connect(path) as conn:
        return conn.execute(
            f"SELECT * FROM items{where} ORDER BY created_at DESC", params
        ).fetchall()


def get_item(item_id: int, path: Path = DEFAULT_PATH) -> Optional[sqlite3.Row]:
    """Một món đồ theo id."""
    with connect(path) as conn:
        return conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()


def get_ratings(item_id: int, path: Path = DEFAULT_PATH) -> List[Rating]:
    """Các lần chấm của một món, theo thứ tự thời gian."""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT rated_at, desire FROM ratings WHERE item_id = ? ORDER BY rated_at",
            (item_id,),
        ).fetchall()
    return [Rating(datetime.fromisoformat(r["rated_at"]), r["desire"]) for r in rows]


def get_price_log(item_id: int, path: Path = DEFAULT_PATH) -> List[tuple]:
    """Lịch sử giá của một món: [(thời điểm, giá), ...]."""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT checked_at, price FROM price_log WHERE item_id = ? ORDER BY checked_at",
            (item_id,),
        ).fetchall()
    return [(datetime.fromisoformat(r["checked_at"]), r["price"]) for r in rows]


def get_goals(item_id: int, path: Path = DEFAULT_PATH) -> List[Goal]:
    """Các mục tiêu thay thế đã lưu kèm món đồ."""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT name, amount FROM goals WHERE item_id = ?", (item_id,)
        ).fetchall()
    return [Goal(r["name"], r["amount"]) for r in rows]


def get_offers(item_id: int, path: Path = DEFAULT_PATH) -> List[Offer]:
    """Các nơi bán đã lưu, rẻ nhất trước."""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT store, url, price FROM offers WHERE item_id = ? ORDER BY price",
            (item_id,),
        ).fetchall()
    return [Offer(r["store"], r["url"], r["price"]) for r in rows]


def items_due_for_review(profile: Optional[str] = None,
                         path: Path = DEFAULT_PATH,
                         now: Optional[datetime] = None) -> List[sqlite3.Row]:
    """Các món đang chờ đã đến hạn chấm lại.

    Đây là hàm mà script gửi email nhắc gọi tới, với profile=None để quét
    toàn bộ hồ sơ.
    """
    now = now or datetime.now()
    extra, params = ("", ())
    if profile:
        extra, params = (" AND profile = ?", (profile,))
    with connect(path) as conn:
        return conn.execute(
            f"""SELECT * FROM items
                WHERE status = 'waiting' AND review_at <= ?{extra}
                ORDER BY review_at""",
            (now.isoformat(),) + params,
        ).fetchall()


def items_at_target_price(path: Path = DEFAULT_PATH) -> List[sqlite3.Row]:
    """Các món đang chờ mà giá ghi gần nhất đã về mức mục tiêu.

    Dùng hàm cửa sổ của SQLite để lấy dòng giá mới nhất của từng món,
    thay vì đọc hết về Python rồi lọc.
    """
    with connect(path) as conn:
        return conn.execute(
            """WITH latest AS (
                   SELECT item_id, price,
                          ROW_NUMBER() OVER (
                              PARTITION BY item_id ORDER BY checked_at DESC
                          ) AS rn
                   FROM price_log
               )
               SELECT i.*, latest.price AS current_price
               FROM items i
               JOIN latest ON latest.item_id = i.id AND latest.rn = 1
               WHERE i.status = 'waiting'
                 AND i.target_price IS NOT NULL
                 AND i.target_price > 0
                 AND latest.price <= i.target_price"""
        ).fetchall()


# ------------------------------------------------------- chuyển đổi kiểu dữ liệu

def row_to_purchase(row: sqlite3.Row, desire: int = 5) -> Purchase:
    """Dựng lại đối tượng Purchase từ một dòng trong bảng items.

    `desire` truyền vào vì mức thèm muốn nằm ở bảng `ratings`, không nằm
    trong bảng `items`. Muốn dựng đúng bối cảnh lúc ra quyết định thì
    truyền lần chấm ĐẦU TIÊN — xem `decision_context`.

    Thời hạn sale cũng được tính lại: bảng lưu thời điểm sale kết thúc,
    còn mô hình cần số giờ còn lại *tại lúc ra quyết định*.
    """
    hours_left = float("inf")
    if row["sale_end"]:
        delta = (datetime.fromisoformat(row["sale_end"])
                 - datetime.fromisoformat(row["created_at"]))
        hours_left = max(0.0, delta.total_seconds() / 3600)

    return Purchase(
        name=row["name"],
        price=row["price"],
        uses_per_month=row["uses_per_month"],
        months=row["months"],
        category=row["category"],
        wanted_days=row["wanted_days"],
        source=row["source"],
        owns_similar=bool(row["owns_similar"]),
        desire=desire,
        used_price=row["used_price"],
        sale=Sale(on=row["sale_end"] is not None or row["list_price"] is not None,
                  list_price=row["list_price"], hours_left=hours_left),
    )


def decision_context(row: sqlite3.Row,
                     path: Path = DEFAULT_PATH) -> Tuple[Purchase, Finances, datetime, List[Rating]]:
    """Dựng lại đầy đủ bối cảnh của một quyết định đã qua.

    Trả về (món đồ, tài chính, thời điểm quyết định, các lần chấm) — đủ để
    chạy lại mô hình y như lúc người dùng bấm lưu. Dùng cho báo cáo hiệu
    chỉnh: "bộ trọng số hiện tại có bắt được món tôi đã mua hớ không?"
    """
    ratings = get_ratings(row["id"], path=path)
    first_desire = ratings[0].desire if ratings else 5
    return (
        row_to_purchase(row, desire=first_desire),
        row_to_finances(row),
        datetime.fromisoformat(row["created_at"]),
        ratings,
    )


def row_to_finances(row: sqlite3.Row) -> Finances:
    """Dựng lại hoàn cảnh tài chính lúc ra quyết định."""
    return Finances(
        income=row["income"],
        fixed_costs=row["fixed_costs"],
        savings=row["savings"],
    )


# ------------------------------------------------------------------- thống kê

def profile_stats(profile: Optional[str] = None,
                  path: Path = DEFAULT_PATH) -> dict:
    """Số liệu tổng hợp cho tab Hồ sơ.

    Tính bằng SQL thay vì vòng lặp Python: gọn hơn và đúng việc của
    cơ sở dữ liệu.
    """
    where, params = _where(None, profile)
    extra = " AND i.profile = ?" if profile else ""
    regret_params = (profile,) if profile else ()

    with connect(path) as conn:
        totals = conn.execute(
            f"""SELECT COUNT(*)                                       AS n_items,
                      COALESCE(SUM(price), 0)                         AS total_value,
                      SUM(CASE WHEN status = 'bought'  THEN 1 ELSE 0 END) AS n_bought,
                      SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS n_skipped,
                      COALESCE(SUM(CASE WHEN status = 'skipped'
                                        THEN price ELSE 0 END), 0)    AS saved
               FROM items{where}""", params
        ).fetchone()

        # Những món đã mua mà lần chấm gần nhất chỉ còn 4/10 trở xuống.
        regret = conn.execute(
            f"""WITH last_rating AS (
                   SELECT item_id, desire,
                          ROW_NUMBER() OVER (
                              PARTITION BY item_id ORDER BY rated_at DESC
                          ) AS rn
                   FROM ratings
               )
               SELECT COUNT(*) AS n, COALESCE(SUM(i.price), 0) AS value
               FROM items i
               JOIN last_rating r ON r.item_id = i.id AND r.rn = 1
               WHERE i.status = 'bought' AND r.desire <= 4{extra}""",
            regret_params
        ).fetchone()

    return {
        "n_items": totals["n_items"],
        "total_value": totals["total_value"],
        "n_bought": totals["n_bought"] or 0,
        "n_skipped": totals["n_skipped"] or 0,
        "saved": totals["saved"],
        "n_regret": regret["n"],
        "regret_value": regret["value"],
    }


# ------------------------------------------------------- cài đặt của hồ sơ

def set_setting(profile: str, key: str, value: str,
                path: Path = DEFAULT_PATH) -> None:
    """Lưu một cài đặt của hồ sơ, ghi đè nếu đã có."""
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO settings (profile, key, value) VALUES (?,?,?)
               ON CONFLICT(profile, key) DO UPDATE SET value = excluded.value""",
            (profile, key, value),
        )


def get_setting(profile: str, key: str, default: Optional[str] = None,
                path: Path = DEFAULT_PATH) -> Optional[str]:
    """Đọc một cài đặt của hồ sơ, trả về `default` nếu chưa có."""
    with connect(path) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE profile = ? AND key = ?",
            (profile, key),
        ).fetchone()
    return row["value"] if row else default


def save_weights(profile: str, weights: dict,
                 path: Path = DEFAULT_PATH) -> None:
    """Lưu bộ trọng số đã hiệu chỉnh của hồ sơ.

    Nhận vào dict phẳng (dùng `dataclasses.asdict` trên Weights), lưu dạng
    JSON. Nhờ vậy trọng số không mất khi đóng app — nếu mất thì công sức
    hiệu chỉnh của người dùng thành vô nghĩa.
    """
    set_setting(profile, "weights", json.dumps(weights, ensure_ascii=False),
                path=path)


def load_weights(profile: str, path: Path = DEFAULT_PATH) -> Optional[dict]:
    """Đọc lại bộ trọng số đã lưu. Trả về None nếu hồ sơ chưa hiệu chỉnh gì."""
    raw = get_setting(profile, "weights", path=path)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None    # dữ liệu hỏng thì coi như chưa có, dùng mặc định


# ------------------------------------------------------- xuất / nhập dữ liệu

EXPORT_VERSION = 1


def export_profile(profile: str, path: Path = DEFAULT_PATH) -> dict:
    """Xuất toàn bộ dữ liệu của một hồ sơ thành dict để ghi ra JSON.

    Có `version` để nếu sau này lược đồ đổi thì vẫn biết cách đọc file cũ.

    Chỉ xuất đúng một hồ sơ, không xuất cả database: người dùng tải về dữ
    liệu của mình, không kèm của người khác.
    """
    items: List[dict] = []

    with connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE profile = ? ORDER BY id", (profile,)
        ).fetchall()

        for row in rows:
            item = {k: row[k] for k in row.keys() if k not in ("id", "profile")}
            item["ratings"] = [
                dict(r) for r in conn.execute(
                    "SELECT rated_at, desire FROM ratings WHERE item_id = ? "
                    "ORDER BY rated_at", (row["id"],)
                ).fetchall()
            ]
            item["price_log"] = [
                dict(r) for r in conn.execute(
                    "SELECT checked_at, price FROM price_log WHERE item_id = ? "
                    "ORDER BY checked_at", (row["id"],)
                ).fetchall()
            ]
            item["goals"] = [
                dict(r) for r in conn.execute(
                    "SELECT name, amount FROM goals WHERE item_id = ?",
                    (row["id"],)
                ).fetchall()
            ]
            item["offers"] = [
                dict(r) for r in conn.execute(
                    "SELECT store, url, price FROM offers WHERE item_id = ?",
                    (row["id"],)
                ).fetchall()
            ]
            items.append(item)

        settings = {
            r["key"]: r["value"] for r in conn.execute(
                "SELECT key, value FROM settings WHERE profile = ?", (profile,)
            ).fetchall()
        }

    return {
        "version": EXPORT_VERSION,
        "profile": profile,
        "exported_at": datetime.now().isoformat(),
        "settings": settings,
        "items": items,
    }


class ImportError_(ValueError):
    """File nhập vào không đúng định dạng."""


def import_profile(data: dict, profile: Optional[str] = None,
                   replace: bool = False,
                   path: Path = DEFAULT_PATH) -> int:
    """Nhập dữ liệu từ dict đã đọc từ JSON. Trả về số món đã nhập.

    `profile=None` thì dùng tên hồ sơ ghi trong file; truyền tên khác thì
    nhập vào hồ sơ đó (dùng khi muốn xem dữ liệu của người khác mà không
    trộn vào hồ sơ mình).

    `replace=True` thì xoá dữ liệu cũ của hồ sơ trước khi nhập; mặc định là
    nhập thêm vào.

    File do người dùng tự chọn nên phải kiểm tra định dạng trước: thiếu
    khoá hay sai kiểu thì báo lỗi rõ ràng thay vì để sập giữa đường.
    """
    if not isinstance(data, dict):
        raise ImportError_("File không phải một đối tượng JSON.")
    if data.get("version") != EXPORT_VERSION:
        raise ImportError_(
            f"File thuộc phiên bản {data.get('version')!r}, "
            f"công cụ đang dùng phiên bản {EXPORT_VERSION}."
        )
    items = data.get("items")
    if not isinstance(items, list):
        raise ImportError_("Không tìm thấy danh sách 'items' trong file.")

    target = profile or data.get("profile")
    if not target:
        raise ImportError_("File không ghi tên hồ sơ, và bạn cũng chưa chọn.")

    # Các cột của bảng items, trừ id và profile — chỉ nhận đúng những cột này
    # để file lạ không chèn được cột không mong muốn.
    allowed = {
        "name", "category", "price", "uses_per_month", "months", "wanted_days",
        "source", "owns_similar", "used_price", "income", "fixed_costs",
        "savings", "list_price", "sale_end", "target_price", "created_at",
        "review_at", "status",
    }

    count = 0
    with connect(path) as conn:
        if replace:
            conn.execute("DELETE FROM items WHERE profile = ?", (target,))
            conn.execute("DELETE FROM settings WHERE profile = ?", (target,))

        for raw in items:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue                      # bỏ qua dòng rác, không làm sập
            cols = {k: v for k, v in raw.items() if k in allowed}
            # Điền các cột NOT NULL mà lược đồ không có giá trị mặc định.
            # Thiếu chúng thì sqlite báo IntegrityError và cả lần nhập sập —
            # lỗi này do test phát hiện.
            cols.setdefault("price", 0)
            cols.setdefault("uses_per_month", 1)
            cols.setdefault("months", 12)
            cols.setdefault("created_at", datetime.now().isoformat())
            cols.setdefault("review_at", cols["created_at"])
            cols["profile"] = target

            names = ", ".join(cols)
            marks = ", ".join("?" for _ in cols)
            cur = conn.execute(
                f"INSERT INTO items ({names}) VALUES ({marks})",
                tuple(cols.values()),
            )
            item_id = cur.lastrowid
            count += 1

            for r in raw.get("ratings") or []:
                if isinstance(r, dict) and r.get("rated_at"):
                    conn.execute(
                        "INSERT INTO ratings (item_id, rated_at, desire) "
                        "VALUES (?,?,?)",
                        (item_id, r["rated_at"], int(r.get("desire", 5))),
                    )
            for p in raw.get("price_log") or []:
                if isinstance(p, dict) and p.get("checked_at"):
                    conn.execute(
                        "INSERT INTO price_log (item_id, checked_at, price) "
                        "VALUES (?,?,?)",
                        (item_id, p["checked_at"], float(p.get("price", 0))),
                    )
            for g in raw.get("goals") or []:
                if isinstance(g, dict) and g.get("name"):
                    conn.execute(
                        "INSERT INTO goals (item_id, name, amount) VALUES (?,?,?)",
                        (item_id, g["name"], float(g.get("amount", 0))),
                    )
            for o in raw.get("offers") or []:
                if isinstance(o, dict) and (o.get("store") or o.get("url")):
                    conn.execute(
                        "INSERT INTO offers (item_id, store, url, price) "
                        "VALUES (?,?,?,?)",
                        (item_id, o.get("store", ""), o.get("url", ""),
                         float(o.get("price", 0))),
                    )

        for key, value in (data.get("settings") or {}).items():
            if isinstance(key, str) and isinstance(value, str):
                conn.execute(
                    """INSERT INTO settings (profile, key, value) VALUES (?,?,?)
                       ON CONFLICT(profile, key) DO UPDATE
                       SET value = excluded.value""",
                    (target, key, value),
                )

    return count


def all_rating_series(profile: Optional[str] = None,
                      path: Path = DEFAULT_PATH) -> List[List[Rating]]:
    """Chuỗi chấm điểm của tất cả các món, để ước tính thời gian bán rã."""
    extra, params = ("", ())
    if profile:
        extra, params = (" WHERE i.profile = ?", (profile,))
    with connect(path) as conn:
        rows = conn.execute(
            f"""SELECT r.item_id, r.rated_at, r.desire
                FROM ratings r
                JOIN items i ON i.id = r.item_id{extra}
                ORDER BY r.item_id, r.rated_at""", params
        ).fetchall()

    series: dict = {}
    for r in rows:
        series.setdefault(r["item_id"], []).append(
            Rating(datetime.fromisoformat(r["rated_at"]), r["desire"])
        )
    return list(series.values())
