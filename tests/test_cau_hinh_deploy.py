"""Kiểm thử cấu hình deploy.

Không có test nào ở đây chạm tới logic. Chúng chặn đúng một loại lỗi: cấu
hình sai chỉ lộ ra khi build trên Vercel, tức là mất một lần build và vài
phút chờ mới biết.

Lỗi đã thật sự xảy ra:

    error: No `project` table found in: /vercel/path0/pyproject.toml

Nguyên nhân: chỉ cần pyproject.toml TỒN TẠI là Vercel dùng `uv` đọc phụ
thuộc từ đó thay vì đọc requirements.txt, mà `uv lock` bắt buộc có
[project]. Bản pyproject.toml trước đó chỉ có [tool.vercel], cố ý bỏ
[project] để tránh khai phụ thuộc hai nơi — và đó chính là chỗ sai.
"""

import pathlib
import tomllib

import pytest

GOC = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((GOC / "pyproject.toml").read_text(encoding="utf-8"))


def _spec_trong_requirements(ten: str) -> str:
    for dong in (GOC / "requirements.txt").read_text(encoding="utf-8").splitlines():
        dong = dong.split("#")[0].strip()
        if dong and dong.lower().startswith(ten):
            return dong
    return ""


# ------------------------------------------------- lỗi đã gặp

def test_pyproject_co_bang_project():
    """Đây là dòng làm đổ build. Thiếu [project] thì `uv lock` không chạy."""
    assert "project" in PYPROJECT, (
        "pyproject.toml phải có [project], không thì Vercel đổ ở bước "
        "`uv lock` với 'No `project` table found'"
    )


@pytest.mark.parametrize("khoa", ["name", "version", "requires-python",
                                  "dependencies"])
def test_bang_project_co_du_khoa_uv_can(khoa):
    assert khoa in PYPROJECT["project"], khoa


def test_khai_ro_khong_phai_package():
    """Đây là ứng dụng, không phải thư viện. Thiếu dòng này thì uv coi nó
    là package và đòi [build-system] để build chính nó."""
    assert PYPROJECT.get("tool", {}).get("uv", {}).get("package") is False


def test_phu_thuoc_khai_o_hai_noi_phai_khop():
    """Vercel đọc pyproject; requirements.txt để cho ai quen `pip install
    -r`. Hai chỗ lệch nhau là bản deploy và bản chạy cục bộ chạy trên hai
    phiên bản thư viện khác nhau — loại lỗi khó thấy nhất."""
    deps = PYPROJECT["project"]["dependencies"]
    for dep in deps:
        ten = dep.split(">")[0].split("=")[0].split("[")[0].strip().lower()
        assert _spec_trong_requirements(ten) == dep, (
            f"pyproject khai {dep!r}, requirements.txt khai "
            f"{_spec_trong_requirements(ten)!r}"
        )


def test_chi_phu_thuoc_fastapi():
    """Phần tính toán trong src/ chỉ dùng thư viện chuẩn. Một phụ thuộc mới
    lọt vào đây nghĩa là có ai đó vừa import pandas vào src/, và bản deploy
    phình lên vài trăm MB."""
    assert PYPROJECT["project"]["dependencies"] == ["fastapi>=0.115"]


# ------------------------------------------------- entrypoint

def test_entrypoint_tro_toi_file_co_that():
    ep = PYPROJECT["tool"]["vercel"]["entrypoint"]
    module, _, bien = ep.partition(":")
    assert bien == "app", "Vercel nhận biến tên `app` cho ASGI"
    duong_dan = GOC / (module.replace(".", "/") + ".py")
    assert duong_dan.is_file(), f"{ep} trỏ tới {duong_dan}, không có file đó"


def test_entrypoint_khong_tro_vao_app_streamlit():
    """app.py ở gốc là giao diện Streamlit: nó không có biến `app` cho ASGI
    và chạy cả app Streamlit ngay lúc được import. Dò tự động sẽ tìm thấy
    nó trước, nên entrypoint phải khai rõ."""
    ep = PYPROJECT["tool"]["vercel"]["entrypoint"]
    assert not ep.startswith("app:"), "đang trỏ vào giao diện Streamlit"


def test_entrypoint_import_duoc():
    pytest.importorskip("fastapi", reason="cần fastapi mới import được API")
    import importlib
    ep = PYPROJECT["tool"]["vercel"]["entrypoint"]
    module, _, bien = ep.partition(":")
    assert hasattr(importlib.import_module(module), bien)


# ------------------------------------------------- phiên bản Python

def test_python_version_nam_trong_khoang_requires_python():
    """`.python-version` quyết định Vercel chạy Python nào; nếu nó không
    thoả requires-python thì uv từ chối resolve."""
    pinned = (GOC / ".python-version").read_text(encoding="utf-8").strip()
    yeu_cau = PYPROJECT["project"]["requires-python"]
    assert yeu_cau.startswith(">="), f"chưa xử lý dạng {yeu_cau!r}"
    toi_thieu = tuple(int(x) for x in yeu_cau[2:].strip().split("."))
    dang_dung = tuple(int(x) for x in pinned.split("."))
    assert dang_dung >= toi_thieu, f"{pinned} không thoả {yeu_cau}"


def test_python_version_la_ban_vercel_ho_tro():
    """Vercel hỗ trợ 3.12 (mặc định), 3.13, 3.14. Ghim bản khác thì nó im
    lặng dùng bản mặc định, và khác biệt chỉ lộ ra khi chạy thật."""
    pinned = (GOC / ".python-version").read_text(encoding="utf-8").strip()
    assert pinned in ("3.12", "3.13", "3.14"), pinned


# ------------------------------------------------- vercel.json

def test_khong_loai_public_khoi_goi():
    """Chính app Python phục vụ public/index.html, nên loại nó khỏi gói là
    trang ra 404 trong khi API vẫn sống — lỗi trông rất khó hiểu."""
    import json
    vercel = json.loads((GOC / "vercel.json").read_text(encoding="utf-8"))
    ep = PYPROJECT["tool"]["vercel"]["entrypoint"].partition(":")[0]
    khoa = ep.replace(".", "/") + ".py"
    assert khoa in vercel["functions"], (
        f"vercel.json cấu hình cho hàm nào? cần khoá {khoa!r}"
    )
    loai = vercel["functions"][khoa]["excludeFiles"]
    assert "public" not in loai


def test_loai_nhung_thu_khong_can_khi_chay():
    loai = __import__("json").loads(
        (GOC / "vercel.json").read_text(encoding="utf-8")
    )["functions"]["api/main.py"]["excludeFiles"]
    for thu in ("tests/**", "docs/**", "data/**", "app.py"):
        assert thu in loai, thu


# ------------------------------------------------- uv.lock

def test_co_uv_lock_va_khop_pyproject():
    """Có lock thì Vercel resolve mất vài ms thay vì hơn một phút. Lock lệch
    pyproject thì uv phải resolve lại, tức là mất luôn cái lợi đó."""
    lock = GOC / "uv.lock"
    assert lock.is_file(), "nên commit uv.lock để build nhanh và lặp lại được"
    noi_dung = tomllib.loads(lock.read_text(encoding="utf-8"))
    assert noi_dung["requires-python"] == PYPROJECT["project"]["requires-python"]
    ten_goi = {g["name"] for g in noi_dung["package"]}
    for dep in PYPROJECT["project"]["dependencies"]:
        ten = dep.split(">")[0].split("=")[0].strip().lower()
        assert ten in ten_goi, f"{ten} không có trong uv.lock"
