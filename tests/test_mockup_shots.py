"""목업 캡처 판정 — 오류 · 빈 화면을 잡는지(브라우저 없이 순수 함수로)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mockup_shots as ms  # noqa: E402


def test_judge_ok():
    assert ms.judge(120, 300, []) == []


def test_judge_blank_page():
    out = ms.judge(3, 0, [])
    assert len(out) == 1 and "빈 화면" in out[0]


def test_judge_errors_are_reported():
    out = ms.judge(120, 300, ["ReferenceError: x is not defined"])
    assert out == ["오류: ReferenceError: x is not defined"]


def test_out_path_per_theme():
    f = Path("docs/plans/mockups/REQ_01/app-items.html")
    assert ms.out_path(f, "light", "light").name == "app-items.png"
    assert ms.out_path(f, "dark", "light").name == "app-items.dark.png"
