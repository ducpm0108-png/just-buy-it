"""Kiểm thử lớp API.

Lớp này không có công thức nào, nên test ở đây không kiểm toán học — phần
đó đã có test riêng cho `src/`. Nó kiểm đúng hai thứ mà chỉ lớp vỏ mới
hỏng được:

1. **Biên JSON.** Python có `inf`, JSON thì không. Một con `inf` lọt ra là
   cả phản hồi thành rác trong trình duyệt.
2. **API không tự bịa số.** Gọi qua HTTP phải ra đúng con số gọi thẳng
   `src/`. Nếu một ngày lớp vỏ "tiện tay" làm tròn hay đổi đơn vị, test này
   đổ.
"""

import math
from datetime import datetime

import pytest

pytest.importorskip("fastapi", reason="API cần fastapi; phần src/ thì không")

from fastapi.testclient import TestClient      # noqa: E402

from api.main import app                       # noqa: E402
from src import decay, metrics, scoring        # noqa: E402
from src.models import Finances, Purchase, Sale  # noqa: E402
from src.scoring import Weights                # noqa: E402

client = TestClient(app)

MON_DO = {
    "item": {"name": "Tai nghe chống ồn", "price": 4_500_000,
             "uses_per_month": 20, "months": 24, "category": "tech",
             "wanted_days": 10, "source": "ad", "desire": 8,
             "used_price": 2_800_000},
    "sale": {"on": True, "list_price": 5_490_000, "hours_left": 48},
    "finances": {"income": 8_000_000, "fixed_costs": 5_000_000,
                 "savings": 12_000_000},
    "now": "2026-09-28T14:00:00",
}


def moi_so(obj, duong_dan="$"):
    """Duyệt cả cây phản hồi, sinh ra từng (đường dẫn, số) một."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from moi_so(v, f"{duong_dan}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from moi_so(v, f"{duong_dan}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield duong_dan, obj


# --------------------------------------------------------- biên JSON

@pytest.mark.parametrize("than_bai", [
    # Không dùng lần nào: giá mỗi lần dùng thành vô hạn.
    {"item": {"price": 1_000_000, "uses_per_month": 0, "months": 0}},
    # Không thu nhập: số giờ đi làm thành vô hạn.
    {"item": {"price": 1_000_000}, "finances": {"income": 0}},
    # Không còn tiền dư: phần tiền dư mỗi tháng thành vô hạn.
    {"item": {"price": 1_000_000},
     "finances": {"income": 5_000_000, "fixed_costs": 5_000_000}},
    # Tất cả bằng 0.
    {"item": {"price": 0}, "finances": {"income": 0}},
])
def test_khong_bao_gio_tra_ve_so_vo_han(than_bai):
    """`inf` hay `NaN` lọt ra là JSON.parse của trình duyệt ném lỗi cú pháp
    và mất sạch phản hồi, chứ không phải chỉ sai một ô."""
    r = client.post("/api/evaluate", json=than_bai)
    assert r.status_code == 200
    assert "Infinity" not in r.text and "NaN" not in r.text
    for duong_dan, so in moi_so(r.json()):
        assert math.isfinite(so), f"{duong_dan} = {so}"


def test_vo_han_tra_ve_none_chu_khong_phai_khong():
    """None nghĩa là "không tính được"; 0 nghĩa là "bằng không". Lẫn hai
    thứ này thì hoá đơn báo giá mỗi lần dùng là 0 ₫ — sai theo hướng nguy
    hiểm nhất, vì nó khiến món đồ trông như miễn phí."""
    r = client.post("/api/evaluate",
                    json={"item": {"price": 1_000_000, "uses_per_month": 0}})
    m = r.json()["metrics"]
    assert m["cost_per_use"] is None
    assert m["cost_per_use"] != 0


# --------------------------------------------------- API không bịa số

def test_ket_qua_trung_khop_voi_goi_thang_src():
    r = client.post("/api/evaluate", json=MON_DO).json()

    p = Purchase(
        name="Tai nghe chống ồn", price=4_500_000, uses_per_month=20,
        months=24, category="tech", wanted_days=10, source="ad",
        desire=8, used_price=2_800_000,
        sale=Sale(on=True, list_price=5_490_000, hours_left=48),
    )
    f = Finances(income=8_000_000, fixed_costs=5_000_000, savings=12_000_000)
    w = Weights()
    now = datetime(2026, 9, 28, 14, 0, 0)

    m = metrics.compute(p, f)
    st = scoring.strain_score(p, f, w, m)
    im = scoring.impulse_score(p, w, now=now)
    v = scoring.verdict_for(st.value, im.value, w)
    tp = scoring.target_price(p, f, w)

    assert r["metrics"]["cost_per_use"] == pytest.approx(m.cost_per_use)
    assert r["metrics"]["work_hours"] == pytest.approx(m.work_hours)
    assert r["strain"]["value"] == st.value
    assert r["impulse"]["value"] == im.value
    assert r["verdict"]["key"] == v.key
    assert r["target"]["price"] == pytest.approx(tp.price)


def test_truyen_now_thi_ket_qua_tai_lap_duoc():
    """Yếu tố "giờ khuya" phụ thuộc lúc gọi. Không truyền được `now` thì
    test nào chạm tới nó cũng đổ tuỳ giờ chạy."""
    khuya = dict(MON_DO, now="2026-09-28T23:30:00")
    trua = dict(MON_DO, now="2026-09-28T14:00:00")
    a = client.post("/api/evaluate", json=khuya).json()
    b = client.post("/api/evaluate", json=trua).json()
    assert a["impulse"]["value"] > b["impulse"]["value"]
    # Gọi lại lúc khác vẫn ra đúng con số cũ.
    lai = client.post("/api/evaluate", json=khuya).json()
    assert lai["impulse"]["value"] == a["impulse"]["value"]


def test_ban_ra_tinh_tu_du_lieu_gui_len():
    chuoi = [[{"t": "2026-08-01T10:00:00", "v": 9},
              {"t": "2026-08-08T10:00:00", "v": 3}]]
    r = client.post("/api/evaluate",
                    json=dict(MON_DO, rating_series=chuoi)).json()
    mong_doi = decay.estimate_half_life([[
        decay.Rating(datetime(2026, 8, 1, 10), 9),
        decay.Rating(datetime(2026, 8, 8, 10), 3),
    ]])
    assert r["half_life"]["from_data"] is True
    assert r["half_life"]["days"] == pytest.approx(mong_doi.days)


def test_ban_ra_bo_qua_chuoi_chi_co_mot_lan_cham():
    """Một lần chấm thì chưa biết gì về tốc độ nguội."""
    r = client.post("/api/evaluate", json=dict(
        MON_DO, rating_series=[[{"t": "2026-08-01T10:00:00", "v": 9}]])).json()
    assert r["half_life"]["from_data"] is False


def test_moc_thoi_gian_hong_khong_lam_sap_ca_request():
    """File do người dùng nạp lên có thể có mốc thời gian rác."""
    r = client.post("/api/evaluate", json=dict(MON_DO, rating_series=[[
        {"t": "hôm qua", "v": 9}, {"t": "2026-08-08T10:00:00", "v": 3}]]))
    assert r.status_code == 200
    assert r.json()["half_life"]["from_data"] is False


# --------------------------------------------------------- trọng số

def test_khoa_trong_so_la_bi_bo_qua():
    """Nhận bừa dict của client thì một khoá lạ nằm im trong trọng số và
    làm lệch tổng, mà không ai thấy."""
    r = client.post("/api/evaluate", json=dict(
        MON_DO, weights={"strain": {"share": 35, "khong_co_that": 999}}))
    assert r.status_code == 200
    goc = client.post("/api/evaluate", json=MON_DO).json()
    assert r.json()["strain"]["value"] == goc["strain"]["value"]


def test_trong_so_gui_len_thay_doi_ket_qua():
    r = client.post("/api/evaluate", json=dict(
        MON_DO, weights={"threshold": 95})).json()
    assert r["verdict"]["key"] == "buy"          # ngưỡng cao thì dễ dãi
    assert r["threshold"] == 95


def test_khong_sale_thi_khong_co_ap_luc_het_han():
    r = client.post("/api/evaluate", json=dict(
        MON_DO, sale={"on": False})).json()
    khoa = [p["key"] for p in r["impulse"]["parts"]]
    assert "urgency" not in khoa
    assert r["sale_advice"] is None


def test_hours_left_bo_trong_nghia_la_khong_co_han():
    """None phải thành vô hạn, không phải 0 — 0 giờ nghĩa là sale sắp hết
    tới nơi, tức đảo ngược hẳn ý nghĩa."""
    r = client.post("/api/evaluate", json=dict(
        MON_DO, sale={"on": True, "list_price": 5_490_000})).json()
    khoa = [p["key"] for p in r["impulse"]["parts"]]
    assert "urgency" not in khoa


# ------------------------------------------------------------- meta

def test_meta_du_cac_yeu_to_de_dung_giao_dien():
    """Thiếu một yếu tố ở đây là giao diện thiếu một thanh trượt, mà trọng
    số của nó vẫn có tác dụng — người dùng không chỉnh được thứ đang ảnh
    hưởng tới kết quả của mình."""
    m = client.get("/api/meta").json()
    w = Weights()
    for nhom in ("strain", "impulse"):
        tu_meta = {f["key"] for f in m["factors"][nhom]}
        assert tu_meta == set(getattr(w, nhom))


def test_meta_co_du_bon_ket_luan():
    m = client.get("/api/meta").json()
    assert set(m["verdicts"]) == {"buy", "wait", "plan", "no"}


def test_meta_va_presets_dung_cung_hinh_dang_voi_defaults():
    m = client.get("/api/meta").json()
    for ten, bo in m["presets"].items():
        assert set(bo) == set(m["defaults"]), ten


# ------------------------------------------------------------ hồ sơ

def test_ho_so_dung_cung_ham_ban_ra_voi_tab_danh_gia():
    """Hai tab cho ra hai con số bán rã khác nhau là lỗi kinh điển của việc
    có hai bản công thức."""
    items = [{"id": "a", "name": "Bàn phím", "price": 2_400_000,
              "status": "bought",
              "ratings": [{"t": "2026-08-01T10:00:00", "v": 9},
                          {"t": "2026-08-08T10:00:00", "v": 3}]}]
    ho_so = client.post("/api/profile", json={"items": items}).json()
    danh_gia = client.post("/api/evaluate", json=dict(
        MON_DO, rating_series=[items[0]["ratings"]])).json()
    assert ho_so["half_life"]["days"] == pytest.approx(
        danh_gia["half_life"]["days"])


def test_ho_so_rong_khong_sap():
    r = client.post("/api/profile", json={"items": []})
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 0
    assert d["desire_first_mean"] is None


def test_ho_so_dem_mon_mua_roi_het_muon():
    items = [
        {"id": "a", "name": "Mua rồi hết muốn", "price": 1_000_000,
         "status": "bought", "ratings": [{"t": "2026-08-01T10:00:00", "v": 9},
                                         {"t": "2026-08-20T10:00:00", "v": 2}]},
        {"id": "b", "name": "Mua rồi vẫn thích", "price": 2_000_000,
         "status": "bought", "ratings": [{"t": "2026-08-01T10:00:00", "v": 9},
                                         {"t": "2026-08-20T10:00:00", "v": 9}]},
    ]
    d = client.post("/api/profile", json={"items": items}).json()
    assert d["regret"]["count"] == 1
    assert d["regret"]["total"] == 1_000_000
    assert d["regret"]["names"] == ["Mua rồi hết muốn"]


# ------------------------------------------------------ đầu vào hỏng

@pytest.mark.parametrize("xau", [
    {"item": {"price": -5}},                      # giá âm
    {"item": {"desire": 42}},                     # ngoài thang 1-10
    {"item": {"price": "bốn triệu"}},             # sai kiểu
    {"weights": {"threshold": 500}},              # ngoài 0-100
])
def test_dau_vao_hong_tra_ve_422_chu_khong_phai_500(xau):
    """422 là "bạn gửi sai"; 500 là "máy chủ hỏng". Trả nhầm thì người dùng
    tưởng app chết trong khi thật ra chỉ cần sửa ô nhập."""
    r = client.post("/api/evaluate", json=xau)
    assert r.status_code == 422


def test_danh_muc_la_khong_lam_sap():
    """Danh mục lạ rơi về 'other' thay vì ném lỗi: file nhập vào có thể có
    danh mục của một phiên bản khác."""
    r = client.post("/api/evaluate",
                    json=dict(MON_DO, item=dict(MON_DO["item"],
                                                category="xe-tang")))
    assert r.status_code == 200
    assert r.json()["timing"]["advice"]


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


# --------------------------------------------------- các cách khác

def test_cac_cach_khac_dung_chung_ham_gia_moi_lan_dung():
    r = client.post("/api/evaluate", json=dict(
        MON_DO, alternatives={"used": 2_800_000, "rent": 30_000,
                              "borrow": 0})).json()
    theo_kind = {a["kind"]: a for a in r["alternatives"]}
    assert theo_kind["new"]["cost_per_use"] == pytest.approx(
        r["metrics"]["cost_per_use"])
    # 2.800.000 chia 480 lần
    assert theo_kind["used"]["cost_per_use"] == pytest.approx(2_800_000 / 480)
    # Thuê nhập sẵn theo lần nên không chia.
    assert theo_kind["rent"]["cost_per_use"] == 30_000


def test_muon_khong_duoc_tinh_la_re_nhat():
    """Mượn thường bằng 0 nên sẽ luôn thắng, mà mượn được thì đã không còn
    là quyết định mua."""
    r = client.post("/api/evaluate", json=dict(
        MON_DO, alternatives={"used": 2_800_000, "borrow": 0})).json()
    re_nhat = [a["kind"] for a in r["alternatives"] if a["best"]]
    assert re_nhat == ["used"]


def test_cach_khong_nhap_thi_khong_xuat_hien():
    r = client.post("/api/evaluate", json=MON_DO).json()
    assert [a["kind"] for a in r["alternatives"]] == ["new"]


def test_chi_co_mot_cach_thi_cach_do_la_re_nhat():
    r = client.post("/api/evaluate", json=MON_DO).json()
    assert r["alternatives"][0]["best"] is True


def test_khong_tinh_duoc_thi_khong_co_cach_nao_re_nhat():
    """Chưa nhập số lần dùng thì mọi giá mỗi lần dùng đều là vô hạn."""
    r = client.post("/api/evaluate", json={
        "item": {"price": 1_000_000, "uses_per_month": 0},
        "alternatives": {"used": 500_000}}).json()
    assert all(a["best"] is False for a in r["alternatives"])


# ------------------------------------------------- báo cáo hiệu chỉnh

TIEN = {"income": 8_000_000, "fixed_costs": 5_000_000, "savings": 12_000_000}


def ctx(uses=10, months=24, wanted=30, source="need", **kw):
    d = dict(uses_per_month=uses, months=months, wanted_days=wanted,
             source=source, owns_similar=False, used_price=None, **TIEN)
    d.update(kw)
    return d


def mon(i, name, price, status, v_dau, v_cuoi, hoan_canh=None, cat="tech"):
    """Một món đã có kết luận, chấm hai lần cách nhau 7 ngày."""
    row = {"id": f"m{i}", "name": name, "price": price, "status": status,
           "cat": cat, "created": "2026-08-01T10:00:00",
           "ratings": [{"t": "2026-08-01T10:00:00", "v": v_dau},
                       {"t": "2026-08-08T10:00:00", "v": v_cuoi}]}
    if hoan_canh is not None:
        row["context"] = hoan_canh
    return row


def cal_cua(items, weights=None):
    body = {"items": items}
    if weights:
        body["weights"] = weights
    return client.post("/api/profile", json=body).json()["calibration"]


def test_mon_thieu_hoan_canh_bi_bo_qua_va_duoc_dem():
    """Bỏ qua chứ không đoán bù. Chạy lại mô hình bằng số liệu bịa ra còn
    tệ hơn không chạy lại, vì kết quả trông như thật."""
    c = cal_cua([
        mon(0, "Có hoàn cảnh", 1_000_000, "bought", 9, 2, ctx()),
        mon(1, "Thiếu hoàn cảnh", 2_000_000, "bought", 9, 2, None),
    ])
    assert c["n"] == 1
    assert c["missing_context"] == 1


def test_duoi_5_quyet_dinh_thi_khong_du_du_lieu():
    c = cal_cua([mon(i, f"Món {i}", 1_000_000, "bought", 9, 2, ctx())
                 for i in range(4)])
    assert c["n"] == 4
    assert c["enough_data"] is False


def test_du_5_quyet_dinh_thi_du_du_lieu():
    c = cal_cua([mon(i, f"Món {i}", 1_000_000, "bought", 9, 2, ctx())
                 for i in range(5)])
    assert c["enough_data"] is True


def test_mon_dang_cho_khong_tinh_vao():
    c = cal_cua([mon(0, "Đang chờ", 1_000_000, "waiting", 9, 3, ctx())])
    assert c["n"] == 0
    assert c["missing_context"] == 0


def test_cham_5_tren_10_khong_tinh_vao():
    """5/10 là ở giữa: không rõ còn muốn hay hết muốn."""
    c = cal_cua([mon(0, "Lưng chừng", 1_000_000, "bought", 9, 5, ctx())])
    assert c["n"] == 0


def test_ham_muon_dau_vao_la_lan_cham_DAU_chu_khong_phai_lan_cuoi():
    """Lần chấm cuối chính là kết quả cần đoán. Dùng nó làm đầu vào thì mô
    hình tự biết đáp án, và mọi tỷ lệ đúng đều thành vô nghĩa.

    Cách kiểm: đổi RIÊNG lần chấm cuối. Nhãn kết quả đổi theo, nhưng điểm
    bốc đồng phải giữ nguyên — vì nó chỉ được phép nhìn lần chấm đầu.
    """
    a = cal_cua([mon(0, "X", 1_000_000, "bought", 9, 2, ctx())])   # mua hớ
    b = cal_cua([mon(0, "X", 1_000_000, "bought", 9, 9, ctx())])   # mua đúng
    assert a["outcomes"][0]["label"] == "mua_ho"
    assert b["outcomes"][0]["label"] == "mua_dung"
    assert a["outcomes"][0]["impulse"] == b["outcomes"][0]["impulse"]
    assert a["outcomes"][0]["first_desire"] == b["outcomes"][0]["first_desire"] == 9


def test_hai_loai_loi_khong_bi_gop():
    """false_go (khuyên mua mà hớ) nặng hơn false_hold (cản mà vẫn muốn).
    Gộp thành một con số độ chính xác là mất đúng phần thông tin cần để
    chỉnh trọng số."""
    # Ngưỡng 0: mọi thứ đều "cao" nên mô hình luôn khuyên dừng.
    luon_dung = cal_cua([mon(0, "X", 1_000_000, "bought", 9, 9, ctx())],
                        weights={"threshold": 0})
    assert luon_dung["false_hold"] == 1 and luon_dung["false_go"] == 0
    # Ngưỡng 100: không gì là "cao" nên mô hình luôn khuyên mua.
    luon_mua = cal_cua([mon(0, "X", 1_000_000, "bought", 9, 2, ctx())],
                       weights={"threshold": 100})
    assert luon_mua["false_go"] == 1 and luon_mua["false_hold"] == 0
    assert luon_mua["wasted_value"] == 1_000_000
    # missed_value đếm giá trị công cụ đã cản OAN — kể cả khi người dùng vẫn
    # mua và thấy đáng. Đó chính là thiệt hại nếu họ nghe theo lời khuyên.
    assert luon_dung["missed_value"] == 1_000_000
    assert luon_dung["wasted_value"] == 0


def test_hoan_canh_luu_lai_duoc_dung_thay_vi_tinh_hinh_hom_nay():
    """Cùng một món, chỉ khác thu nhập lúc quyết định, phải ra điểm áp lực
    khác nhau. Nếu không, hoàn cảnh đã lưu đang bị bỏ qua."""
    giau = cal_cua([mon(0, "X", 3_000_000, "bought", 9, 2,
                        ctx(income=40_000_000, savings=100_000_000))])
    ngheo = cal_cua([mon(0, "X", 3_000_000, "bought", 9, 2,
                         ctx(income=6_000_000, savings=1_000_000))])
    assert giau["outcomes"][0]["strain"] < ngheo["outcomes"][0]["strain"]


def test_gaps_can_ca_hai_nhom_moi_do_duoc():
    """Chỉ có món mua hớ mà không có món mua đúng thì không so được."""
    chi_ho = cal_cua([mon(i, f"M{i}", 1_000_000, "bought", 9, 2, ctx())
                      for i in range(3)])
    assert chi_ho["gaps"] == []
    ca_hai = cal_cua([
        mon(0, "Hớ", 1_000_000, "bought", 9, 2, ctx(wanted=1, source="ad")),
        mon(1, "Đúng", 1_000_000, "bought", 9, 9, ctx(wanted=60, source="need")),
    ])
    khoa = {g["key"] for g in ca_hai["gaps"]}
    assert "recency" in khoa and "source" in khoa


def test_gaps_xep_theo_chenh_lech_giam_dan():
    c = cal_cua([
        mon(0, "Hớ", 1_000_000, "bought", 9, 2, ctx(wanted=1, source="ad")),
        mon(1, "Đúng", 1_000_000, "bought", 9, 9, ctx(wanted=60, source="need")),
    ])
    chenh = [g["gap"] for g in c["gaps"]]
    assert chenh == sorted(chenh, reverse=True)


def test_goi_y_la_cau_hoan_chinh():
    """Gợi ý hiện thẳng ra giao diện nên phải là câu đọc được, không phải
    mảnh chuỗi bị cắt."""
    c = cal_cua([mon(i, f"M{i}", 1_000_000, "bought", 9, 2 if i else 9, ctx())
                 for i in range(5)])
    assert c["suggestions"]
    for s in c["suggestions"]:
        assert s.strip()
        assert s.rstrip().endswith((".", "!", "?")), s


def test_ho_so_rong_van_tra_ve_khoi_hieu_chinh():
    c = cal_cua([])
    assert c["n"] == 0 and c["missing_context"] == 0
    assert c["outcomes"] == [] and c["gaps"] == []


def test_hoan_canh_hong_khong_lam_sap():
    """File người dùng nạp lên có thể có hoàn cảnh sai kiểu."""
    r = client.post("/api/profile", json={"items": [
        mon(0, "X", 1_000_000, "bought", 9, 2, ctx(source="không-có-thật"))]})
    assert r.status_code == 200
    assert r.json()["calibration"]["n"] == 1
