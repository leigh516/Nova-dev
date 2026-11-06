"""마스터플랜 ↔ 릴리스 맞물림(REQ-261105-06-6) — 정본 종료 조건 절이 가리키는 판본 · 릴리스와 원장 masterplan 칸이 서로 맞는지."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import masterplan as mp  # noqa: E402

PLAN = """# 마스터플랜

| 항목 | 값 |
|---|---|
| 버전 | **v1.3** |
| 상태 | 정식 |

## 종료 조건 (exit)
{line}
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | python nova.py test | 통과 | 명령 | |
"""


def make(tmp_path, line="이 판본(v1.3)이 끝나는 조건 — 모두 녹색이면 릴리스 v0.2.0 으로 닫는다.", releases=None):
    p = tmp_path / "docs" / "plans"
    p.mkdir(parents=True)
    (p / "master_plan.md").write_text(PLAN.format(line=line), encoding="utf-8")
    if releases is not None:
        (tmp_path / "docs" / "releases").mkdir(parents=True)
        (tmp_path / "docs/releases/releases.json").write_text(json.dumps({"releases": releases}, ensure_ascii=False), encoding="utf-8")
    return tmp_path


R1 = {"version": "0.1.0", "status": "shipped", "masterplan": "v1.2"}
R2 = {"version": "0.2.0", "status": "draft", "masterplan": "v1.3"}


def test_matching_plan_and_ledger_pass(tmp_path):
    assert mp.release_errors(make(tmp_path, releases=[R1, R2])) == []


def test_stale_plan_version_in_sentence_fails(tmp_path):
    root = make(tmp_path, line="이 판본(v1.2)이 끝나는 조건 — 모두 녹색이면 릴리스 v0.2.0 으로 닫는다.", releases=[R1, R2])
    assert any("v1.2" in e and "v1.3" in e for e in mp.release_errors(root))


def test_release_not_in_ledger_or_other_masterplan_fails(tmp_path):
    root = make(tmp_path, line="이 판본(v1.3)이 … 릴리스 v0.9.0 으로 닫는다.", releases=[R1, R2])
    assert any("v0.9.0" in e and "원장" in e for e in mp.release_errors(root))


def test_sentence_release_must_belong_to_this_plan(tmp_path):
    root = make(tmp_path, line="이 판본(v1.3)이 … 릴리스 v0.1.0 으로 닫는다.", releases=[R1, R2])
    assert any("v0.1.0" in e and "masterplan" in e for e in mp.release_errors(root))


def test_draft_masterplan_must_be_canon(tmp_path):
    root = make(tmp_path, releases=[R1, {**R2, "masterplan": "v1.2"}])
    assert any("draft" in e and "v1.2" in e for e in mp.release_errors(root))


def test_new_project_without_release_number_or_ledger_passes(tmp_path):
    """새 프로젝트 — 문장에 릴리스 번호가 없고 원장이 비었거나 없어도 통한다."""
    assert mp.release_errors(make(tmp_path, line="이 판본이 끝나는 조건 — 모두 녹색이면 판본을 닫고(릴리스)")) == []
    other = tmp_path / "b"
    assert mp.release_errors(make(other, line="이 판본이 끝나는 조건", releases=[])) == []


def test_repo_master_plan_matches_ledger():
    assert mp.release_errors(ROOT) == []
