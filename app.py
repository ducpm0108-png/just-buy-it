"""Just Buy It? — giao diện Streamlit.

File này CHỈ làm giao diện: đọc ô nhập, gọi hàm trong src/, vẽ kết quả.
Không có một công thức nào ở đây. Muốn kiểm tra cách tính thì đọc src/,
muốn đổi giao diện thì sửa file này mà không sợ làm sai con số.

Chạy: streamlit run app.py
"""

import json
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src import calendar_vn, db, decay, metrics, personalize, sale, scoring, style
from src.models import CATEGORIES, Finances, Goal, Offer, Purchase, Sale, SOURCES
from src.scoring import PRESETS, Weights

DB_PATH = Path("data/justbuyit.db")

# Hai màu cho biểu đồ lịch sử giá. Đã kiểm tra bằng bộ validate của
# hướng dẫn trực quan hoá: đạt cả năm tiêu chí ở chế độ sáng và tối,
# gồm khoảng cách màu cho người mù màu.
COLOR_ACTUAL = "#2a78d6"   # giá ghi được
COLOR_TARGET = "#eb6834"   # giá mục tiêu

st.set_page_config(page_title="Just Buy It?", page_icon="🧾", layout="wide")


# ----------------------------------------------------------------- tiện ích

def vnd(n) -> str:
    """Định dạng tiền đồng theo kiểu Việt Nam: 4.500.000 ₫."""
    try:
        if n != n or n in (float("inf"), float("-inf")):   # NaN hoặc vô cực
            return "—"
    except TypeError:
        return "—"
    return f"{round(n):,}".replace(",", ".") + " ₫"


def so(n, digits: int = 1) -> str:
    """Số thực với dấu phẩy thập phân kiểu Việt Nam."""
    return f"{n:.{digits}f}".replace(".", ",")


def receipt_line(label: str, value: str, muted: bool = False) -> str:
    """Một dòng trên hoá đơn: nhãn bên trái, giá trị bên phải."""
    color = "color:var(--text-color-secondary);" if muted else ""
    return (
        f'<div style="display:flex;justify-content:space-between;gap:12px;'
        f'font-family:monospace;font-size:13px;{color}">'
        f"<span>{label}</span><span><b>{value}</b></span></div>"
    )


def receipt_sub(text: str) -> str:
    """Dòng chú thích nhỏ dưới một chỉ số."""
    return (
        f'<div style="font-family:monospace;font-size:11px;opacity:.65;'
        f'margin:-2px 0 6px">{text}</div>'
    )


def receipt_rule() -> str:
    return '<hr style="border:0;border-top:1px dashed currentColor;opacity:.3;margin:9px 0">'


def receipt_section(title: str) -> str:
    return (
        f'<div style="font-family:monospace;font-size:10.5px;letter-spacing:.14em;'
        f'opacity:.6;margin:2px 0 4px">{title}</div>'
    )


def section(title: str) -> None:
    """Tiêu đề một nhóm trường, kiểu dòng legend của fieldset.

    Dùng thay cho việc in đậm một dòng chữ thường: chữ nhỏ, giãn cách, có
    đường kẻ dưới. Kiểu dáng nằm ở `src/style.py`.
    """
    st.html(f'<div class="jbi-legend">{title}</div>')


# Hai màu cho thanh điểm: dưới ngưỡng xanh, vượt ngưỡng đỏ. Đây là màu
# TRẠNG THÁI chứ không phải màu danh tính — hai thanh đã có nhãn riêng, màu
# chỉ để nói "mức này có đáng lo chưa". Cả hai đạt tương phản từ 3:1 trên cả
# nền giấy sáng và nền giấy tối, nên không cần đổi theo chế độ.
BAR_UNDER = "#3D8F69"
BAR_OVER = "#D2554A"


def meter(label: str, score: int, threshold: float, parts: list) -> None:
    """Vẽ một thanh điểm kèm vạch ngưỡng.

    Vạch ngưỡng là thứ làm con số có nghĩa: 47/100 tự nó không nói gì, nhưng
    "47 với vạch ngưỡng ở 40" thì thấy ngay là đã vượt.
    """
    over = score >= threshold
    fill = BAR_OVER if over else BAR_UNDER

    st.markdown(
        receipt_line(label, f"{score}/100")
        + f'<div style="height:9px;background:color-mix(in srgb, currentColor 14%, transparent);'
          f'position:relative;overflow:hidden;margin:3px 0 4px">'
          f'<span style="position:absolute;inset:0 auto 0 0;width:{score}%;'
          f'background:{fill}"></span>'
          f'<span style="position:absolute;top:0;bottom:0;left:{threshold}%;'
          f'width:2px;background:currentColor;opacity:.5"></span>'
          f"</div>",
        unsafe_allow_html=True,
    )

    top = " · ".join(f"{s} +{round(p)}" for _, s, p in parts)
    st.caption(
        (top if top else "không yếu tố nào đáng kể")
        + (f" — đã vượt ngưỡng {round(threshold)}" if over else "")
    )


def price_chart(price_log: list, target: float) -> alt.LayerChart:
    """Biểu đồ lịch sử giá đã ghi, kèm đường giá mục tiêu.

    Giá mục tiêu vẽ bằng đường gạch mảnh chứ không phải một chuỗi dữ liệu
    thứ hai: nó là MỐC SO SÁNH, không phải số liệu quan sát được. Nhờ vậy
    biểu đồ chỉ có một chuỗi dữ liệu và không cần chú giải màu.

    Trục giá không bắt đầu từ 0 — với biểu đồ đường thì điều đáng xem là
    khoảng cách giữa giá và mục tiêu, để 0 sẽ dồn cả hai vào một dải hẹp.
    """
    df = pd.DataFrame({
        "Ngày": [t for t, _ in price_log],
        "Giá": [p for _, p in price_log],
    })

    line = alt.Chart(df).mark_line(
        color=COLOR_ACTUAL, strokeWidth=2,
        point=alt.OverlayMarkDef(size=70, filled=True, color=COLOR_ACTUAL),
    ).encode(
        x=alt.X("Ngày:T", title=None,
                axis=alt.Axis(format="%d/%m", tickCount="day")),
        # Nhãn trục quy ra triệu đồng và đổi dấu thập phân sang dấu phẩy
        # cho đúng cách viết số của tiếng Việt.
        y=alt.Y("Giá:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(labelExpr=(
                    "replace(format(datum.value / 1e6, '.1f'), '.', ',') + ' tr'"
                ))),
        tooltip=[alt.Tooltip("Ngày:T", title="Ngày", format="%d/%m"),
                 alt.Tooltip("Giá:Q", title="Giá", format=",.0f")],
    )

    layers = [line]
    if target > 0:
        ref = pd.DataFrame({"Giá": [target]})
        layers.append(
            alt.Chart(ref).mark_rule(
                color=COLOR_TARGET, strokeWidth=2, strokeDash=[6, 4],
            ).encode(y="Giá:Q")
        )
        layers.append(
            alt.Chart(ref).mark_text(
                text="giá mục tiêu", align="left", baseline="bottom",
                dx=4, dy=-4, color=COLOR_TARGET, fontSize=11,
            ).encode(y="Giá:Q")
        )

    return alt.layer(*layers).properties(height=220)


# ----------------------------------------------------------------- khởi tạo

db.init_db(DB_PATH)


def theme_mode() -> str:
    """Chế độ sáng hay tối mà người dùng đang xem.

    Streamlit không phơi màu giao diện ra biến CSS, nên phải hỏi Python để
    biết mà truyền đúng màu giấy vào lớp trang trí.
    """
    try:
        return st.context.theme.type or "light"
    except Exception:       # noqa: BLE001
        return "light"


st.html(style.css(theme_mode()))

if "profile" not in st.session_state:
    st.session_state.profile = db.DEFAULT_PROFILE


def load_weights_for(profile: str) -> Weights:
    """Đọc trọng số đã hiệu chỉnh của hồ sơ, hoặc mặc định nếu chưa có."""
    saved = db.load_weights(profile, path=DB_PATH)
    if not saved:
        return Weights()
    base = Weights()
    return Weights(
        strain={**base.strain, **saved.get("strain", {})},
        impulse={**base.impulse, **saved.get("impulse", {})},
        threshold=saved.get("threshold", base.threshold),
        ref_cost_per_use=saved.get("ref_cost_per_use", base.ref_cost_per_use),
        default_half_life=saved.get("default_half_life", base.default_half_life),
    )


def persist_weights(profile: str, w: Weights) -> None:
    """Lưu trọng số của hồ sơ để lần sau mở lại vẫn còn."""
    db.save_weights(profile, {
        "strain": w.strain, "impulse": w.impulse,
        "threshold": w.threshold, "ref_cost_per_use": w.ref_cost_per_use,
        "default_half_life": w.default_half_life,
    }, path=DB_PATH)


def running_on_cloud() -> bool:
    """Đoán xem app đang chạy trên Streamlit Cloud hay trên máy người dùng.

    Streamlit Cloud mount repo tại /mount/src. Đây là cách đoán chứ không
    phải API chính thức, nên bọc try/except: đoán sai thì chỉ hiện sai một
    dòng lưu ý, không làm app chết.
    """
    try:
        return Path("/mount/src").exists()
    except Exception:       # noqa: BLE001
        return False


ON_CLOUD = running_on_cloud()


def intro_body() -> None:
    """Nội dung bảng giới thiệu. Tách riêng để dùng lại ở cả hai cách hiển thị."""
    st.markdown(
        "Công cụ giúp bạn trả lời **“có nên mua món này không?”** bằng con số "
        "thay vì cảm xúc. Bạn nhập giá, tình hình tiền bạc và lý do mình muốn "
        "nó; công cụ in ra một hoá đơn cho biết món đồ *thật sự* tốn bao nhiêu, "
        "rồi đóng dấu một trong bốn kết luận: **MUA ĐI**, **CHỜ ĐÃ**, "
        "**LÊN KẾ HOẠCH** hoặc **ĐỪNG MUA**."
    )

    st.markdown("##### Dùng thế nào")
    st.markdown(
        "1. **Đánh giá** — điền thông tin món đồ. Các ô đã có sẵn một ví dụ, "
        "cứ sửa đè lên. Hoá đơn bên phải cập nhật ngay khi bạn gõ.\n"
        "2. **Chờ đã** — còn phân vân thì bấm “Đưa vào danh sách chờ”. Đến hạn, "
        "quay lại chấm lại xem mình còn muốn nó không.\n"
        "3. **Hồ sơ** — sau vài món, công cụ cho biết ham muốn của bạn nguội "
        "nhanh cỡ nào, và tự đo xem bộ trọng số của bạn đoán đúng đến đâu.\n"
        "4. **Cách tính điểm** — tuỳ chỉnh độ khắt khe, có hướng dẫn kèm theo."
    )

    st.markdown("##### Vài lưu ý")
    notes = [
        "Con số chỉ tốt bằng dữ liệu bạn nhập. Hãy ước tính số lần dùng một "
        "cách thật lòng — đó là ô ảnh hưởng nhiều nhất.",
        "Công cụ không tự đọc giá từ các sàn. Giá là do bạn ghi vào, và lịch "
        "giảm giá theo danh mục chỉ là các mốc sale định kỳ, không phải dự báo.",
        "Tên hồ sơ chỉ để tách dữ liệu, **không có xác thực** — ai cũng chọn "
        "được hồ sơ của người khác. Đừng nhập số liệu thật vào bản online.",
        "Đây là công cụ để nhìn lại thói quen chi tiêu, **không phải lời "
        "khuyên tài chính**.",
    ]
    st.markdown("\n".join(f"- {n}" for n in notes))

    if ON_CLOUD:
        st.warning(
            "**Bản online không giữ được dữ liệu** — mỗi lần app khởi động lại "
            "là mất hết. Hai việc nên biết:\n\n"
            "- Muốn xem thử ngay: tab **Hồ sơ** → **Nạp dữ liệu mẫu**\n"
            "- Muốn giữ dữ liệu mình nhập: tab **Hồ sơ** → **Tải dữ liệu về**, "
            "lần sau quay lại thì nạp file đó lên",
            icon="⚠️",
        )
    else:
        st.info(
            f"Dữ liệu lưu tại `{DB_PATH}` trên máy này, không gửi đi đâu. "
            "Muốn sao lưu hoặc mang sang máy khác thì dùng **Tải dữ liệu về** "
            "ở tab Hồ sơ.",
            icon="💾",
        )


INTRO_TITLE = "Chào bạn, đây là Just Buy It?"

if hasattr(st, "dialog"):
    @st.dialog(INTRO_TITLE, width="large")
    def show_intro() -> None:
        intro_body()
        if st.button("Bắt đầu", type="primary"):
            st.session_state.show_intro = False
            st.rerun()
else:
    # Streamlit cũ không có st.dialog: hiện trong khối mở sẵn thay vì modal.
    def show_intro() -> None:
        with st.expander(INTRO_TITLE, expanded=True):
            intro_body()
            if st.button("Đã hiểu", type="primary"):
                st.session_state.show_intro = False
                st.rerun()


# Trọng số nạp theo hồ sơ. Đổi hồ sơ thì nạp lại bộ của hồ sơ đó — đây là
# phần cá nhân hoá quan trọng nhất: công sức hiệu chỉnh không được mất.
if ("weights" not in st.session_state
        or st.session_state.get("weights_profile") != st.session_state.profile):
    st.session_state.weights = load_weights_for(st.session_state.profile)
    st.session_state.weights_profile = st.session_state.profile

W: Weights = st.session_state.weights


# ----------------------------------------------------------------- thanh bên

with st.sidebar:
    st.title("Just Buy It?")
    st.caption("Món này tốn bao nhiêu cho mỗi lần bạn thật sự dùng nó.")

    st.subheader("Hồ sơ")
    existing = db.list_profiles(DB_PATH)
    options = existing + (["+ Hồ sơ mới"] if existing else [])

    if existing:
        current = st.session_state.profile
        index = options.index(current) if current in options else 0
        chosen = st.selectbox("Bạn là ai", options, index=index,
                              label_visibility="collapsed")
        if chosen == "+ Hồ sơ mới":
            new_name = st.text_input("Tên hồ sơ mới", placeholder="Ví dụ: Đức")
            if new_name.strip():
                st.session_state.profile = new_name.strip()
        else:
            st.session_state.profile = chosen
    else:
        st.session_state.profile = st.text_input(
            "Tên hồ sơ", value=db.DEFAULT_PROFILE,
            help="Chỉ để phân tách dữ liệu, không phải đăng nhập.",
        ).strip() or db.DEFAULT_PROFILE

    profile = st.session_state.profile

    with st.expander("Nhắc qua email"):
        saved_email = db.get_setting(profile, "email", "", path=DB_PATH)
        email = st.text_input("Địa chỉ nhận nhắc", value=saved_email,
                              placeholder="ban@example.com")
        if email != saved_email:
            db.set_setting(profile, "email", email.strip(), path=DB_PATH)
        st.caption("Đến hạn chấm lại, công cụ gửi nhắc về địa chỉ này.")

    st.divider()
    if st.button("Giới thiệu và lưu ý", use_container_width=True):
        st.session_state.show_intro = True
        st.rerun()


# ----------------------------------------------------------------- các tab

# Lần đầu mở trong một phiên thì hiện bảng giới thiệu. Đặt cờ ngay lúc hiện,
# không phải lúc bấm nút, để đóng bằng dấu X cũng không làm nó hiện lại.
if st.session_state.get("show_intro", True):
    st.session_state.show_intro = False
    show_intro()

tab_eval, tab_wait, tab_profile, tab_weights = st.tabs(
    ["Đánh giá", "Chờ đã", "Hồ sơ", "Cách tính điểm"]
)


# ============================================================ TAB: ĐÁNH GIÁ

with tab_eval:
    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        st.subheader("Món đồ bạn đang cân nhắc")
        st.caption("Hoá đơn bên cạnh cập nhật ngay khi bạn sửa bất kỳ ô nào.")

        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Tên món", value="Tai nghe chống ồn")
        with c2:
            category = st.selectbox(
                "Danh mục", list(CATEGORIES),
                format_func=lambda k: CATEGORIES[k],
            )

        c1, c2, c3 = st.columns(3)
        with c1:
            price = st.number_input("Giá bạn sẽ trả", min_value=0,
                                    value=4_500_000, step=50_000)
        with c2:
            uses = st.number_input("Dùng bao nhiêu lần mỗi tháng", min_value=0,
                                   value=20, step=1)
        with c3:
            months = st.number_input("Dùng được bao nhiêu tháng", min_value=1,
                                     value=24, step=1)

        section("Giảm giá có thời hạn")
        sale_on = st.checkbox("Món này đang trong đợt giảm giá", value=True)

        list_price = low_30d = None
        hours_left = float("inf")
        if sale_on:
            c1, c2, c3 = st.columns(3)
            with c1:
                list_price = st.number_input("Giá gốc trước khi giảm",
                                             min_value=0, value=5_490_000,
                                             step=50_000)
            with c2:
                left_n = st.number_input("Đợt giảm còn", min_value=0,
                                         value=2, step=1)
                unit = st.radio("Đơn vị", ["giờ", "ngày"], index=1,
                                horizontal=True, label_visibility="collapsed")
                hours_left = left_n * 24 if unit == "ngày" else left_n
            with c3:
                low_raw = st.number_input(
                    "Giá thấp nhất 30 ngày qua", min_value=0, value=0, step=50_000,
                    help="Để 0 nếu không biết. Xem lịch sử giá trên trang bán.",
                )
                low_30d = low_raw if low_raw > 0 else None

        section("Tình hình tài chính")
        c1, c2, c3 = st.columns(3)
        with c1:
            income = st.number_input("Thu nhập mỗi tháng", min_value=0,
                                     value=8_000_000, step=500_000)
        with c2:
            fixed = st.number_input("Chi phí cố định mỗi tháng", min_value=0,
                                    value=5_000_000, step=500_000,
                                    help="Thuê nhà, ăn uống, đi lại…")
        with c3:
            savings = st.number_input("Tiền đang có", min_value=0,
                                      value=12_000_000, step=500_000)

        section("Bạn muốn nó từ khi nào")
        c1, c2 = st.columns(2)
        with c1:
            wanted_label = st.selectbox(
                "Muốn món này bao lâu rồi",
                ["Vài giờ", "Vài ngày", "1–2 tuần", "Hơn một tháng", "Nhiều tháng"],
                index=2,
            )
            wanted_days = {"Vài giờ": 0.2, "Vài ngày": 3, "1–2 tuần": 10,
                           "Hơn một tháng": 45, "Nhiều tháng": 180}[wanted_label]
        with c2:
            source = st.selectbox("Biết đến nó từ đâu", list(SOURCES),
                                  index=1,
                                  format_func=lambda k: SOURCES[k][0])

        owns = st.checkbox("Đã có món làm được việc tương tự")
        desire = st.slider("Mức độ thèm muốn", 1, 10, 8)

        st.divider()
        section("Số tiền này còn làm được gì khác")
        st.caption("Những việc khác bạn đang muốn dùng tiền cho.")
        goals_df = st.data_editor(
            pd.DataFrame([
                {"Mục tiêu": "Quỹ dự phòng 3 tháng", "Số tiền cần": 15_000_000},
                {"Mục tiêu": "Một khoá học", "Số tiền cần": 3_000_000},
                {"Mục tiêu": "Chuyến đi Đà Lạt", "Số tiền cần": 5_000_000},
            ]),
            num_rows="dynamic", use_container_width=True, key="goals",
            column_config={
                "Số tiền cần": st.column_config.NumberColumn(format="%d", min_value=0),
            },
        )
        goals = [Goal(str(r["Mục tiêu"]), float(r["Số tiền cần"]))
                 for _, r in goals_df.iterrows()
                 if str(r["Mục tiêu"]).strip() and r["Số tiền cần"] > 0]

        section("Nơi bán")
        st.caption("Link đi theo món đồ vào danh sách chờ.")
        offers_df = st.data_editor(
            pd.DataFrame([
                {"Shop": "Shopee", "Link": "", "Giá": 4_500_000},
                {"Shop": "Tiki", "Link": "", "Giá": 4_690_000},
            ]),
            num_rows="dynamic", use_container_width=True, key="offers",
            column_config={
                "Giá": st.column_config.NumberColumn(format="%d", min_value=0),
                "Link": st.column_config.LinkColumn(),
            },
        )
        offers = [Offer(str(r["Shop"]), str(r["Link"] or ""), float(r["Giá"] or 0))
                  for _, r in offers_df.iterrows() if str(r["Shop"]).strip()]

        section("Các cách khác để có nó")
        c1, c2 = st.columns(2)
        with c1:
            used_raw = st.number_input("Giá mua cũ", min_value=0,
                                       value=2_800_000, step=100_000,
                                       help="Cũng dùng làm giá bán lại nếu sau này tiếc.")
        with c2:
            rent_raw = st.number_input("Giá thuê mỗi lần", min_value=0,
                                       value=0, step=10_000)

    # ------------------------------------------------------ tính toán

    purchase = Purchase(
        name=name.strip() or "Món chưa đặt tên",
        price=price, uses_per_month=uses, months=months, category=category,
        wanted_days=wanted_days, source=source, owns_similar=owns,
        desire=desire, used_price=used_raw if used_raw > 0 else None,
        sale=Sale(on=sale_on, list_price=list_price or None,
                  hours_left=hours_left, low_30d=low_30d),
    )
    money = Finances(income=income, fixed_costs=fixed, savings=savings)

    m = metrics.compute(purchase, money)
    st_score = scoring.strain_score(purchase, money, W, m)
    im_score = scoring.impulse_score(purchase, W)
    verdict = scoring.verdict_for(st_score.value, im_score.value, W)
    target = scoring.target_price(purchase, money, W)
    half_life = decay.estimate_half_life(
        db.all_rating_series(profile=profile, path=DB_PATH), W.default_half_life
    )
    advice = sale.advise(purchase, m, half_life)
    window, timing = calendar_vn.timing_advice(category, target.cut)

    # ------------------------------------------------------ hoá đơn

    with right:
        with st.container(border=True, key="receipt"):
            st.markdown(
                f'<div style="text-align:center;font-family:monospace">'
                f'<b style="letter-spacing:.22em">JUST BUY IT?</b><br>'
                f'<span style="font-size:11px;opacity:.6">hoá đơn chi phí thật</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(receipt_rule(), unsafe_allow_html=True)

            st.markdown(f"**{purchase.name}**")
            st.markdown(f"### {vnd(price)}")

            # Giảm giá
            if sale_on and m.discount:
                st.markdown(
                    receipt_line("Giá gốc", vnd(list_price))
                    + receipt_line(
                        "Giảm",
                        f"−{vnd(m.discount)} ({round(m.discount_pct * 100)}%)")
                    + (receipt_line("Sale hết sau",
                                    f"{round(hours_left)} giờ"
                                    if hours_left < 48 else f"{round(hours_left / 24)} ngày")
                       if hours_left != float("inf") else ""),
                    unsafe_allow_html=True,
                )
            if m.fake_discount:
                st.warning(
                    "Giá này không rẻ hơn mức thấp nhất 30 ngày qua. "
                    "Đợt giảm có thể chỉ là nâng giá gốc lên rồi giảm lại.",
                    icon="⚠️",
                )
            elif m.vs_low_30d is not None:
                st.markdown(
                    receipt_line("So với đáy 30 ngày",
                                 f"rẻ hơn {round(m.vs_low_30d * 100)}%"),
                    unsafe_allow_html=True,
                )

            # Chỉ số chính
            st.markdown(receipt_rule(), unsafe_allow_html=True)
            st.metric("Cho mỗi lần dùng", vnd(m.cost_per_use))
            if m.total_uses > 0:
                st.caption(
                    f"{uses:,}".replace(",", ".") + f" lần/tháng × {months} tháng = "
                    + f"{round(m.total_uses):,}".replace(",", ".") + " lần"
                )

            st.markdown(receipt_rule(), unsafe_allow_html=True)
            rows = receipt_line("Số giờ phải đi làm",
                                f"{round(m.work_hours)} giờ"
                                if m.work_hours != float("inf") else "—")
            if m.work_hours != float("inf"):
                rows += receipt_sub(f"≈ {so(m.work_hours / 8)} ngày công")

            if m.share_discretionary != float("inf"):
                rows += receipt_line("Phần tiền dư mỗi tháng",
                                     f"{round(m.share_discretionary * 100)}%")
                rows += receipt_sub(
                    f"tiền dư {vnd(m.discretionary)}/tháng · "
                    f"{so(m.months_to_rebuild)} tháng để bù lại"
                )
            else:
                rows += receipt_line("Phần tiền dư mỗi tháng", "không còn dư")
                rows += receipt_sub("chi phí cố định đã bằng hoặc vượt thu nhập")

            rows += receipt_line("Tiền đang có đủ mua",
                                 f"{so(m.coverage)} lần"
                                 if m.coverage != float("inf") else "—")
            rows += receipt_line("Nếu để đó 5 năm", vnd(m.opportunity_5y))
            rows += receipt_sub("lãi kép 6% một năm")
            st.markdown(rows, unsafe_allow_html=True)

            # Đánh đổi
            st.markdown(receipt_rule() + receipt_section("ĐÁNH ĐỔI"),
                        unsafe_allow_html=True)
            units = "".join(
                receipt_line(n, f"{q:,}".replace(",", "."))
                for n, q in metrics.in_reference_units(price)
            )
            st.markdown(units or receipt_sub("giá quá nhỏ để quy đổi"),
                        unsafe_allow_html=True)

            if goals:
                comp = metrics.compare_to_goals(price, goals)
                st.markdown(receipt_sub("so với việc khác bạn muốn làm"),
                            unsafe_allow_html=True)
                st.markdown("".join(
                    receipt_line(n, f"{so(r)} lần" if r >= 1 else f"{round(r * 100)}%")
                    for n, r in comp
                ), unsafe_allow_html=True)

            # Giá mục tiêu
            st.markdown(receipt_rule() + receipt_section("GIÁ MỤC TIÊU"),
                        unsafe_allow_html=True)
            if not target.needed:
                st.success(
                    f"Giá hiện tại đã trong tầm — áp lực tài chính "
                    f"{target.current_score}, dưới ngưỡng {round(W.threshold)}.",
                    icon="✅",
                )
            elif target.impossible:
                st.info(
                    "Kể cả miễn phí thì món này vẫn vượt ngưỡng áp lực. "
                    "Tiền dư hằng tháng hoặc tiền đang có của bạn đang quá mỏng — "
                    "cần xem lại hai ô đó trước.",
                    icon="ℹ️",
                )
            else:
                st.metric("Giá cần xuống dưới", vnd(target.price))
                st.markdown(
                    receipt_line("Tức là giảm thêm",
                                 f"{round(target.cut * 100)}% "
                                 f"({vnd(price - target.price)})"),
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Đặt thông báo giá ở mức này. Dưới đó, áp lực tài chính "
                    f"rơi xuống dưới ngưỡng {round(W.threshold)}."
                )

            # Thời điểm mua
            st.markdown(receipt_rule() + receipt_section("THỜI ĐIỂM MUA"),
                        unsafe_allow_html=True)
            if window:
                st.markdown(
                    receipt_line(
                        window.name,
                        "hôm nay" if window.days_away == 0
                        else f"còn {window.days_away} ngày"),
                    unsafe_allow_html=True,
                )
            st.caption(timing)

            # Lời khuyên khi đang sale
            if advice and advice.ends_within_cooling and not m.fake_discount:
                st.markdown(receipt_rule(), unsafe_allow_html=True)
                with st.container(border=True):
                    if advice.hours_left >= 24:
                        st.markdown(
                            "Không cần mua ngay. Chờ đến **ngày cuối đợt sale** "
                            "vẫn giữ nguyên mức giảm."
                        )
                    else:
                        st.markdown(
                            "Sale hết trong chưa đầy một ngày, không còn thời gian để chờ."
                        )
                    st.markdown(
                        receipt_line("Chờ, mất đợt giảm",
                                     f"thiệt ~{vnd(advice.wait_loss)}")
                        + receipt_line("Mua, rồi tiếc",
                                       f"thiệt ~{vnd(advice.buy_loss)}"),
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        f"khả năng tuần sau vẫn muốn ≈ {round(advice.p_still_want * 100)}% "
                        f"(bán rã {round(advice.half_life.days)} ngày, "
                        + ("từ dữ liệu của bạn" if advice.half_life.from_data
                           else "mặc định")
                        + f") · bán lại được {vnd(advice.resale_value)}"
                    )
                    st.markdown(f"**{advice.recommendation}**")

            # Hai thanh điểm
            st.markdown(receipt_rule(), unsafe_allow_html=True)
            for label, score in (("Áp lực tài chính", st_score),
                                 ("Mức độ bốc đồng", im_score)):
                meter(label, score.value, W.threshold, score.top_parts())
            st.caption(f"Vạch dọc là ngưỡng tính là cao: {round(W.threshold)}")

            # Con dấu
            st.markdown(receipt_rule(), unsafe_allow_html=True)
            stamp_color = {"buy": "#2E6B4F", "wait": "#2B4C7E",
                           "plan": "#A2701B", "no": "#B3382C"}[verdict.key]
            st.markdown(
                f'<div style="text-align:center;margin:8px 0">'
                f'<span style="display:inline-block;border:3px double {stamp_color};'
                f'color:{stamp_color};border-radius:5px;padding:8px 18px;'
                f'transform:rotate(-6deg);font-family:monospace">'
                f'<b style="font-size:18px;letter-spacing:.14em">{verdict.title}</b><br>'
                f'<span style="font-size:10px;letter-spacing:.1em">{verdict.subtitle}</span>'
                f"</span></div>",
                unsafe_allow_html=True,
            )
            st.caption(verdict.note)

        # Lưu vào danh sách chờ
        # Thời gian chờ suy ra từ thời gian bán rã ham muốn của chính người
        # dùng, thay vì 7 ngày cố định.
        personal_cooling = personalize.cooling_hours(half_life)
        st.caption(personalize.cooling_explanation(half_life))

        if st.button("Đưa vào danh sách chờ", type="primary",
                     use_container_width=True):
            if price <= 0:
                st.error("Nhập giá trước đã.")
            else:
                review_hours = sale.review_deadline_hours(
                    purchase, cooling_hours=personal_cooling
                )
                item_id = db.add_item(
                    purchase, money, review_hours=review_hours,
                    target=round(target.price) if target.price else 0,
                    goals=goals, offers=offers,
                    profile=profile, path=DB_PATH,
                )
                msg = f"Đã lưu “{purchase.name}” vào danh sách chờ."
                if review_hours < personal_cooling:
                    msg += (" Đợt sale kết thúc trước hạn chờ nên hạn chấm lại "
                            f"được dời lên sau {round(review_hours)} giờ.")
                else:
                    msg += f" Chấm lại sau {round(review_hours / 24)} ngày."
                st.success(msg)


# ============================================================== TAB: CHỜ ĐÃ

with tab_wait:
    st.subheader("Danh sách chờ")
    st.caption(
        "Đến hạn, chấm lại mức thèm muốn **mà không nhìn điểm cũ**. "
        "Món đang sale đến hạn sớm hơn 7 ngày, trước lúc đợt giảm kết thúc vài giờ."
    )

    items = db.list_items(profile=profile, path=DB_PATH)
    if not items:
        st.info("Chưa có món nào. Đánh giá một món rồi bấm “Đưa vào danh sách chờ”.")
    else:
        now = datetime.now()
        for row in items:
            ratings = db.get_ratings(row["id"], path=DB_PATH)
            price_log = db.get_price_log(row["id"], path=DB_PATH)
            review_at = datetime.fromisoformat(row["review_at"])
            due = now >= review_at and row["status"] == "waiting"
            age = (now - datetime.fromisoformat(row["created_at"])).days

            label = f"{row['name']} · {vnd(row['price'])}"
            if row["status"] != "waiting":
                label += "  ·  " + ("đã mua" if row["status"] == "bought"
                                    else "đã bỏ qua")
            elif due:
                label += "  ·  ĐẾN HẠN CHẤM LẠI"

            with st.expander(label, expanded=due):
                first = ratings[0].desire if ratings else None
                last = ratings[-1].desire if ratings else None
                line = f"Ghi {age} ngày trước · thèm muốn lúc đó {first}/10"
                if len(ratings) > 1:
                    line += f" · giờ **{last}/10**"
                st.markdown(line)

                offers_saved = db.get_offers(row["id"], path=DB_PATH)
                if offers_saved:
                    st.markdown("  ·  ".join(
                        f"[{o.store}]({o.url})" if o.url else f"**{o.store}**"
                        + (f" {vnd(o.price)}" if o.price else "")
                        for o in offers_saved
                    ))

                # Theo dõi giá
                if row["status"] == "waiting":
                    current = price_log[-1][1] if price_log else row["price"]
                    tgt = row["target_price"] or 0

                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.metric("Giá hiện tại", vnd(current))
                        if tgt > 0:
                            if current <= tgt:
                                st.success(f"Đã về mức mục tiêu {vnd(tgt)}.",
                                           icon="✅")
                            else:
                                st.caption(
                                    f"Giá mục tiêu {vnd(tgt)} · "
                                    f"còn cách {vnd(current - tgt)}"
                                )
                    with c2:
                        new_price = st.number_input(
                            "Hôm nay bán bao nhiêu?", min_value=0,
                            value=int(current), step=50_000,
                            key=f"price_{row['id']}",
                        )
                        if st.button("Ghi giá", key=f"btn_price_{row['id']}"):
                            db.add_price(row["id"], new_price, path=DB_PATH)
                            st.rerun()

                    # Biểu đồ lịch sử giá — chỉ vẽ khi đã có ít nhất 2 mốc,
                    # một điểm đơn lẻ thì con số ở trên đã nói đủ.
                    if len(price_log) >= 2:
                        st.altair_chart(price_chart(price_log, tgt),
                                        use_container_width=True)
                        st.caption(
                            f"Đã ghi {len(price_log)} lần · thấp nhất "
                            f"{vnd(min(p for _, p in price_log))}"
                        )

                # Chấm lại
                if due:
                    st.divider()
                    new_desire = st.slider(
                        "Giờ bạn còn muốn nó bao nhiêu?", 1, 10, 5,
                        key=f"desire_{row['id']}",
                    )
                    if st.button("Chấm lại", key=f"btn_rate_{row['id']}",
                                 type="primary"):
                        db.add_rating(row["id"], new_desire, path=DB_PATH)
                        st.rerun()
                elif row["status"] == "waiting" and len(ratings) < 2:
                    st.caption(
                        f"Chấm lại vào {review_at.strftime('%H:%M %d/%m')}."
                    )

                if row["status"] == "waiting" and len(ratings) > 1:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Tôi đã mua", key=f"bought_{row['id']}"):
                            db.set_status(row["id"], "bought", path=DB_PATH)
                            st.rerun()
                    with c2:
                        if st.button("Tôi bỏ qua", key=f"skipped_{row['id']}"):
                            db.set_status(row["id"], "skipped", path=DB_PATH)
                            st.rerun()


# =============================================================== TAB: HỒ SƠ

with tab_profile:
    st.subheader(f"Hồ sơ mua sắm — {profile}")
    st.caption("Tính từ chính những món bạn đã ghi lại.")

    stats = db.profile_stats(profile=profile, path=DB_PATH)

    if stats["n_items"] == 0:
        st.info(
            "Chưa có gì để phân tích. Ghi vài món vào danh sách chờ, "
            "hoặc bấm nút bên dưới để nạp dữ liệu mẫu."
        )
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Món đã ghi lại", stats["n_items"])
        c2.metric("Đã cân nhắc chi", vnd(stats["total_value"]))
        c3.metric("Cuối cùng đã mua", f"{stats['n_bought']}/{stats['n_items']}")
        c4.metric("Không tiêu vì đã chờ", vnd(stats["saved"]))

        series = db.all_rating_series(profile=profile, path=DB_PATH)
        hl = decay.estimate_half_life(series, W.default_half_life)
        rated = [s for s in series if len(s) > 1]

        if rated:
            first_avg = sum(s[0].desire for s in rated) / len(rated)
            last_avg = sum(s[-1].desire for s in rated) / len(rated)
            st.markdown(
                f"Trong **{len(rated)} món** bạn đã chấm lại, mức thèm muốn "
                f"trung bình rơi từ **{so(first_avg)}/10** xuống "
                f"**{so(last_avg)}/10**."
            )
            if hl.from_data:
                st.markdown(
                    f"Ham muốn của bạn có **thời gian bán rã khoảng "
                    f"{round(hl.days)} ngày**: cứ chừng đó ngày, mức muốn một "
                    f"món giảm đi một nửa. Con số này đang được dùng để tính "
                    f"lời khuyên khi món đồ đang giảm giá."
                )
        else:
            st.markdown(
                "Chưa món nào được chấm lại lần hai. Khi đến hạn, chấm lại ở "
                "tab **Chờ đã** để bắt đầu thấy đường cong suy giảm."
            )

        if stats["n_regret"]:
            st.warning(
                f"Có **{stats['n_regret']} món đã mua** mà giờ bạn chỉ còn chấm "
                f"4/10 trở xuống, tổng {vnd(stats['regret_value'])}.",
                icon="💭",
            )

        # ---------------------------------------- báo cáo hiệu chỉnh
        st.divider()
        st.markdown("#### Bộ trọng số của bạn đoán đúng đến đâu?")
        st.caption(
            "Chạy lại mô hình với trọng số hiện tại trên chính những quyết "
            "định đã qua của bạn, rồi đối chiếu với kết quả thật."
        )

        rows_all = db.list_items(profile=profile, path=DB_PATH)
        ratings_of = (lambda r: db.get_ratings(r["id"], path=DB_PATH))
        context_of = (lambda r: db.decision_context(r, path=DB_PATH)[:3])

        outcomes = personalize.replay(rows_all, ratings_of, context_of, W)
        cal = personalize.calibrate(outcomes)
        gaps = personalize.factor_gaps(rows_all, ratings_of, context_of, W)

        if cal.n == 0:
            st.info(
                "Chưa có quyết định nào đã biết kết quả. Một quyết định được "
                "tính là đã biết kết quả khi bạn đã chấm lại **và** đã đánh "
                "dấu là đã mua hoặc đã bỏ qua.",
                icon="ℹ️",
            )
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Đoán đúng",
                      f"{cal.n_right}/{cal.n} ({round(cal.accuracy * 100)}%)")
            c2.metric("Khuyên mua mà hối", cal.false_go,
                      help="Loại lỗi nặng hơn: công cụ không chặn được "
                           "một khoản tiêu vô ích.")
            c3.metric("Khuyên dừng mà vẫn muốn", cal.false_hold,
                      help="Gây khó chịu, nhưng không mất tiền.")

            matrix = pd.DataFrame(
                [[cal.correct_go, cal.false_go],
                 [cal.false_hold, cal.correct_hold]],
                index=["Công cụ khuyên tiến tới", "Công cụ khuyên dừng"],
                columns=["Hoá ra đáng", "Hoá ra không đáng"],
            )
            st.dataframe(matrix, use_container_width=True)

            for msg in personalize.suggestions(cal, gaps):
                st.markdown(f"- {msg}")

            if gaps:
                with st.expander("Chi tiết từng yếu tố"):
                    st.caption(
                        "Chênh lệch = giá trị trung bình ở nhóm mua hớ trừ "
                        "nhóm mua đúng. Càng lớn thì yếu tố đó càng phân biệt "
                        "tốt, nên tăng trọng số cho nó."
                    )
                    st.dataframe(
                        pd.DataFrame([
                            {"Yếu tố": g.label,
                             "Nhóm mua hớ": round(g.mean_regret, 3),
                             "Nhóm mua đúng": round(g.mean_good, 3),
                             "Chênh lệch": round(g.gap, 3)}
                            for g in gaps
                        ]),
                        use_container_width=True, hide_index=True,
                    )

            with st.expander("Bảng chi tiết các quyết định đã qua"):
                st.dataframe(
                    pd.DataFrame([
                        {"Món": o.name, "Giá": vnd(o.price),
                         "Con dấu lúc đó": o.verdict,
                         "Kết quả thật": personalize.LABELS[o.label],
                         "Đoán đúng?": "✓" if o.was_right else "✗",
                         "Áp lực": o.strain, "Bốc đồng": o.impulse,
                         "Thèm muốn": f"{o.first_desire} → {o.last_desire}"}
                        for o in outcomes
                    ]),
                    use_container_width=True, hide_index=True,
                )

    # ---------------------------------------- xuất / nhập dữ liệu
    st.divider()
    st.markdown("#### Dữ liệu của bạn")
    st.caption(
        "Bản online không giữ được dữ liệu qua mỗi lần app khởi động lại. "
        "Tải file về là cách giữ, và cũng là cách mang dữ liệu sang máy khác."
        if ON_CLOUD else
        "Tải file về để sao lưu, hoặc mang dữ liệu sang máy khác."
    )

    c1, c2 = st.columns(2)

    with c1:
        payload = db.export_profile(profile, path=DB_PATH)
        st.download_button(
            "Tải dữ liệu về",
            data=json.dumps(payload, ensure_ascii=False, indent=2),
            file_name=f"just-buy-it-{profile}-{datetime.now():%Y%m%d}.json",
            mime="application/json",
            use_container_width=True,
            disabled=not payload["items"],
            help=("Chưa có món nào để tải" if not payload["items"]
                  else f"{len(payload['items'])} món"),
        )

    with c2:
        uploaded = st.file_uploader("Nạp dữ liệu từ file", type="json",
                                    label_visibility="collapsed")
        if uploaded is not None:
            mode = st.radio(
                "Cách nạp",
                ["Thêm vào dữ liệu hiện có", "Thay thế toàn bộ"],
                horizontal=True, label_visibility="collapsed",
            )
            if st.button("Nạp file này", type="primary",
                         use_container_width=True):
                try:
                    data = json.load(uploaded)
                    n = db.import_profile(
                        data, profile=profile,
                        replace=(mode == "Thay thế toàn bộ"), path=DB_PATH,
                    )
                    st.success(f"Đã nạp {n} món vào hồ sơ “{profile}”.")
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("File không phải JSON hợp lệ.")
                except db.ImportError_ as exc:
                    st.error(str(exc))

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Nạp dữ liệu mẫu", use_container_width=True):
            from scripts.seed_demo import seed
            seed(profile=profile, path=DB_PATH)
            st.rerun()
    with c2:
        if st.button("Xoá hết dữ liệu của hồ sơ này",
                     use_container_width=True):
            with db.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM items WHERE profile = ?", (profile,))
            st.rerun()


# ======================================================= TAB: CÁCH TÍNH ĐIỂM

with tab_weights:
    st.subheader("Cách tính điểm")
    st.caption(
        "Mỗi yếu tố được quy về thang 0–1 theo công thức ghi bên dưới, rồi nhân "
        "với trọng số. Điểm cuối là trung bình có trọng số, nhân 100. Trọng số "
        "không cần cộng lại bằng 100 — chỉ tỷ lệ giữa chúng là quan trọng."
    )

    with st.expander("Nên đặt các thanh trượt thế nào?"):
        st.markdown(
            """
**Bước 1 — Chọn điểm xuất phát.** Chọn bộ gần hoàn cảnh bạn nhất ở dưới.

**Bước 2 — Thử lại với những món đã mua.** Nghĩ ra ba món: một món rất đáng
tiền, một món bạn tiếc, một món ở giữa. Nhập lại từng món với hoàn cảnh lúc
mua, rồi xem con dấu. Món đáng tiền nên ra `MUA ĐI` hoặc `LÊN KẾ HOẠCH`; món
đáng tiếc nên ra `CHỜ ĐÃ` hoặc `ĐỪNG MUA`. Nếu sai, xem dòng chữ nhỏ dưới mỗi
thanh trên hoá đơn để biết yếu tố nào đang kéo điểm, rồi chỉnh yếu tố đó.

**Bước 3 — Chỉnh ngưỡng sau cùng**, mỗi lần 5 điểm. Chỉ đụng tới ngưỡng khi
trọng số đã ổn.

**Vài nguyên tắc.** Kéo về 0 để tắt hẳn một yếu tố. Đừng để một yếu tố chiếm
quá 50% nhóm của nó. Mỗi lần chỉ đổi một thanh.
            """
        )
        c1, c2, c3 = st.columns(3)
        presets = [
            (c1, "student", "Sinh viên, thu nhập chưa đều",
             "Ưu tiên tiền đang có. Ngưỡng 35."),
            (c2, "saver", "Đang để dành mục tiêu lớn",
             "Khắt khe nhất. Ngưỡng 30."),
            (c3, "stable", "Thu nhập ổn định",
             "Tập trung chặn mua vội. Ngưỡng 45."),
        ]
        for col, key, title, desc in presets:
            with col:
                st.markdown(f"**{title}**")
                st.caption(desc)
                if st.button("Áp dụng", key=f"preset_{key}",
                             use_container_width=True):
                    st.session_state.weights = Weights(
                        strain=dict(PRESETS[key].strain),
                        impulse=dict(PRESETS[key].impulse),
                        threshold=PRESETS[key].threshold,
                    )
                    st.rerun()

    before = (dict(W.strain), dict(W.impulse), W.threshold,
              W.ref_cost_per_use, W.default_half_life)

    col_a, col_b = st.columns(2)
    for col, group, heading in ((col_a, "strain", "Áp lực tài chính"),
                                (col_b, "impulse", "Mức độ bốc đồng")):
        with col:
            st.markdown(f"**{heading}**")
            weights = getattr(W, group)
            total = sum(max(0, v) for v in weights.values()) or 1
            for key, label, _short, how in scoring.FACTORS[group]:
                weights[key] = st.slider(
                    label, 0, 50, int(weights[key]),
                    key=f"w_{group}_{key}_{profile}",
                )
                share = round(max(0, weights[key]) / total * 100)
                st.caption(f"{share}% của nhóm · {how}")

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        W.threshold = st.slider("Ngưỡng tính là cao", 20, 70,
                                int(W.threshold))
        st.caption("Điểm từ mức này trở lên được tính là cao trong ma trận.")
    with c2:
        W.ref_cost_per_use = st.number_input(
            "Mốc giá mỗi lần dùng", min_value=1_000,
            value=int(W.ref_cost_per_use), step=1_000,
        )
        st.caption("Giá mỗi lần dùng bằng mốc này thì yếu tố đó được nửa điểm.")
    with c3:
        W.default_half_life = st.number_input(
            "Thời gian bán rã mặc định (ngày)", min_value=1, max_value=120,
            value=int(W.default_half_life), step=1,
        )
        hl_now = decay.estimate_half_life(
            db.all_rating_series(profile=profile, path=DB_PATH),
            W.default_half_life,
        )
        st.caption(
            f"Đang dùng {round(hl_now.days)} ngày từ {hl_now.sample_size} món "
            "bạn đã chấm lại." if hl_now.from_data
            else "Chưa có dữ liệu của bạn nên đang dùng giá trị này."
        )

    # Trọng số đổi thì lưu ngay, để lần sau mở app vẫn còn.
    after = (dict(W.strain), dict(W.impulse), W.threshold,
             W.ref_cost_per_use, W.default_half_life)
    if before != after:
        persist_weights(profile, W)

    st.info(
        f"Với món đang đánh giá: áp lực **{st_score.value}**, "
        f"bốc đồng **{im_score.value}**, ngưỡng **{round(W.threshold)}** → "
        f"**{verdict.title}**"
    )
    st.caption(f"Bộ trọng số này được lưu riêng cho hồ sơ “{profile}”.")

    if st.button("Khôi phục mặc định"):
        st.session_state.weights = Weights()
        persist_weights(profile, st.session_state.weights)
        st.rerun()
