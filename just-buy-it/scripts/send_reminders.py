"""Gửi email nhắc chấm lại mức thèm muốn, và báo khi giá về mức mục tiêu.

Vì sao cần script này: nhật ký hoãn mua là phần cốt lõi của công cụ, nhưng
nó âm thầm dựa vào việc người dùng tự nhớ quay lại sau một tuần. Không ai
tự mở một trang tính tiền cả. Một email "7 ngày rồi, bạn còn muốn cái tai
nghe đó không?" là thứ biến tính năng này từ sơ đồ thành thứ dùng được.

Chỉ dùng thư viện chuẩn: sqlite3, smtplib, email.message, argparse.

    # Xem trước, không gửi gì — dùng khi demo và khi test
    python -m scripts.send_reminders --dry-run

    # Gửi thật
    export JBI_SMTP_USER="ban@gmail.com"
    export JBI_SMTP_PASS="app password 16 ký tự"
    python -m scripts.send_reminders

Với Gmail phải dùng **app password**, không phải mật khẩu tài khoản: bật
xác thực hai bước rồi tạo app password riêng. Đừng viết mật khẩu vào file
này — đọc từ biến môi trường, và .env đã nằm trong .gitignore.

Muốn chạy tự động hằng ngày thì cần database nằm trên host để máy khác đọc
được — xem phần kế hoạch dài hạn trong README.
"""

import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db                      # noqa: E402
from src.decay import estimate_half_life   # noqa: E402
from src.personalize import cooling_days   # noqa: E402

SMTP_HOST = os.environ.get("JBI_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("JBI_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("JBI_SMTP_USER", "")
SMTP_PASS = os.environ.get("JBI_SMTP_PASS", "")


def vnd(n) -> str:
    """Định dạng tiền đồng: 4.500.000 ₫."""
    return f"{round(n):,}".replace(",", ".") + " ₫"


def compose(profile: str, due: List, at_target: List,
            path: Path) -> Optional[EmailMessage]:
    """Soạn email cho một hồ sơ. Trả về None nếu chẳng có gì để nhắc.

    Email cố tình KHÔNG nhắc lại điểm thèm muốn cũ. Cả cơ chế đo độ nguội
    dựa vào việc người dùng chấm lại mà không bị điểm cũ neo vào.
    """
    if not due and not at_target:
        return None

    hl = estimate_half_life(db.all_rating_series(profile=profile, path=path))
    lines = [f"Chào {profile},", ""]

    if due:
        days = round(cooling_days(hl))
        lines.append(f"Đã {days} ngày kể từ lúc bạn ghi những món này lại. "
                     "Giờ bạn còn muốn chúng bao nhiêu?")
        lines.append("")
        for row in due:
            lines.append(f"  · {row['name']} — {vnd(row['price'])}")
            offers = db.get_offers(row["id"], path=path)
            for o in offers[:1]:
                if o.url:
                    lines.append(f"    {o.store}: {o.url}")
        lines.append("")
        lines.append("Mở app, vào tab “Chờ đã” và chấm lại. "
                     "Đừng cố nhớ hồi đó bạn chấm mấy điểm — "
                     "chấm theo cảm giác bây giờ mới đúng.")
        lines.append("")

    if at_target:
        lines.append("Mấy món này đã về mức giá mục tiêu của bạn:")
        lines.append("")
        for row in at_target:
            lines.append(
                f"  · {row['name']} — còn {vnd(row['current_price'])}, "
                f"mục tiêu {vnd(row['target_price'])}"
            )
        lines.append("")
        lines.append("Nhưng nhớ là giá rẻ không có nghĩa là bạn cần nó. "
                     "Chấm lại mức thèm muốn trước khi bấm mua.")
        lines.append("")

    lines.append("—")
    lines.append("Just Buy It? · công cụ tự bạn dựng, tự bạn nhắc mình.")

    msg = EmailMessage()
    n = len(due) + len(at_target)
    if due and at_target:
        subject = f"{len(due)} món đến hạn chấm lại, {len(at_target)} món về giá mục tiêu"
    elif due:
        first = due[0]["name"]
        subject = (f"Còn muốn “{first}” không?" if len(due) == 1
                   else f"{n} món đến hạn chấm lại")
    else:
        subject = (f"“{at_target[0]['name']}” đã về giá mục tiêu"
                   if len(at_target) == 1
                   else f"{n} món đã về giá mục tiêu")

    msg["Subject"] = subject
    msg.set_content("\n".join(lines))
    return msg


def collect(path: Path) -> Dict[str, dict]:
    """Gom các món cần nhắc, nhóm theo hồ sơ."""
    buckets: Dict[str, dict] = {}

    for row in db.items_due_for_review(path=path):
        buckets.setdefault(row["profile"], {"due": [], "target": []})
        buckets[row["profile"]]["due"].append(row)

    for row in db.items_at_target_price(path=path):
        buckets.setdefault(row["profile"], {"due": [], "target": []})
        # Món vừa đến hạn vừa về giá thì chỉ nhắc một lần, ở phần đến hạn.
        already = any(d["id"] == row["id"]
                      for d in buckets[row["profile"]]["due"])
        if not already:
            buckets[row["profile"]]["target"].append(row)

    return buckets


def send(msg: EmailMessage, to: str) -> None:
    """Gửi một email qua SMTP."""
    if not SMTP_USER or not SMTP_PASS:
        raise RuntimeError(
            "Chưa có JBI_SMTP_USER và JBI_SMTP_PASS trong biến môi trường. "
            "Chạy với --dry-run để xem trước mà không cần cấu hình."
        )
    msg["From"] = SMTP_USER
    msg["To"] = to

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gửi email nhắc chấm lại mức thèm muốn."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="In email ra màn hình thay vì gửi.")
    parser.add_argument("--profile", default=None,
                        help="Chỉ nhắc một hồ sơ. Mặc định là tất cả.")
    parser.add_argument("--to", default=None,
                        help="Địa chỉ nhận. Mặc định lấy từ cài đặt của hồ sơ.")
    parser.add_argument("--db", default=str(db.DEFAULT_PATH),
                        help="Đường dẫn file database.")
    args = parser.parse_args()

    path = Path(args.db)
    if not path.exists():
        print(f"Không tìm thấy database tại {path}", file=sys.stderr)
        return 1

    buckets = collect(path)
    if args.profile:
        buckets = {k: v for k, v in buckets.items() if k == args.profile}

    if not buckets:
        print("Không có món nào đến hạn. Không gửi gì.")
        return 0

    sent = skipped = 0
    for profile, items in buckets.items():
        msg = compose(profile, items["due"], items["target"], path)
        if msg is None:
            continue

        to = args.to or db.get_setting(profile, "email", path=path)

        if args.dry_run:
            print("=" * 68)
            print(f"Hồ sơ:  {profile}")
            print(f"Gửi tới: {to or '(chưa có email, cần đặt trong app)'}")
            print(f"Tiêu đề: {msg['Subject']}")
            print("-" * 68)
            print(msg.get_content())
            sent += 1
            continue

        if not to:
            print(f"Bỏ qua hồ sơ “{profile}”: chưa đặt email.", file=sys.stderr)
            skipped += 1
            continue

        try:
            send(msg, to)
            print(f"Đã gửi tới {to} cho hồ sơ “{profile}”.")
            sent += 1
        except Exception as exc:                     # noqa: BLE001
            print(f"Lỗi khi gửi cho “{profile}”: {exc}", file=sys.stderr)
            skipped += 1

    verb = "Đã soạn" if args.dry_run else "Đã gửi"
    print(f"\n{verb} {sent} email." + (f" Bỏ qua {skipped}." if skipped else ""))
    return 0 if not skipped else 2


if __name__ == "__main__":
    raise SystemExit(main())
