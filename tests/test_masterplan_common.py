"""마스터플랜 '공통 영역 완료 선언' 필수 항목 — 줄을 지워 병렬 게이트를 여는 길을 막는다(특히 화면 공통 모듈)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import masterplan as mp  # noqa: E402

FULL = """## 공통 영역 완료 선언
| 항목 | 상태 | 증거 |
|---|---|---|
| CI — test · lint 녹색 | 진행 | |
| DB · 마이그레이션 | 진행 | |
| 인증 · 권한 한 경로 | 진행 | |
| 화면 틀 · 공통 UI 부품 · 템플릿 · 디자인 토큰 | 진행 | |
| 서비스 사이 계약(API · 이벤트) | 진행 | |
| 공통 컴포넌트(라이브러리) — nova_common · @nova/sdk · kr.nova.shared | 진행 | |
| 공통 명명 규약 · 개념 원장 | 진행 | |

## 병렬 묶음
"""


def test_full_table_passes():
    assert mp.common_errors(FULL, "x") == []


def test_missing_screen_row_fails():
    text = FULL.replace("| 화면 틀 · 공통 UI 부품 · 템플릿 · 디자인 토큰 | 진행 | |\n", "")
    errs = mp.common_errors(text, "x")
    assert len(errs) == 1 and "화면 공통 모듈" in errs[0]


def test_document_without_section_is_not_checked():
    assert mp.common_errors("# 옛 판본\n본문\n", "x") == []


def test_repo_and_new_project_template_have_all_rows():
    assert mp.common_errors((ROOT / "docs/plans/master_plan.md").read_text(encoding="utf-8"), "정본") == []
    src = (ROOT / "scripts/new_project.py").read_text(encoding="utf-8")
    block = src[src.index("## 공통 영역 완료 선언"):src.index("## 병렬 묶음")] + "## 병렬 묶음\n"
    assert mp.common_errors(block, "새 프로젝트 틀") == []


def test_missing_common_component_and_naming_rows_fail():
    text = FULL.replace("| 공통 컴포넌트(라이브러리) — nova_common · @nova/sdk · kr.nova.shared | 진행 | |\n", "")
    text = text.replace("| 공통 명명 규약 · 개념 원장 | 진행 | |\n", "")
    errs = mp.common_errors(text, "x")
    assert len(errs) == 2 and any("공통 컴포넌트" in e for e in errs) and any("명명" in e for e in errs)
