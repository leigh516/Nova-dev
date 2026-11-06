"""회차 분할안(dispatch) — 병렬 묶음 표 + 묶음 담당 REQ 상태로 파도를 나누고, 사람이 고친 초안을 읽어 worktree-new 명령만 안내한다."""
import subprocess
from pathlib import Path

import pytest

import dispatch

PLAN = """# 마스터플랜

## 공통 영역 완료 선언
| 항목 | 상태 | 증거 |
|---|---|---|
| CI · 테스트 녹색 | 완료 | test 녹색 a1b2c3 |

## 병렬 묶음
| 묶음 | 경로 | 담당 REQ | 선행 묶음 |
|---|---|---|---|
| order | services/order/** | REQ-300102-01 | - |
| member | services/member/** | REQ-300102-02 | - |
| billing | services/billing/** | REQ-300102-03 | {dep} |
"""

INDEX = """# 요구사항 인덱스

| ID | 일자 | 제목 | 상태 | 계획 |
|---|---|---|---|---|
| [REQ-300102-01](requirement_300102_01.md) | 2030-01-02 | 주문 | {s1} | - |
| [REQ-300102-02](requirement_300102_02.md) | 2030-01-02 | 회원 | 진행 중 | - |
| [REQ-300102-03](requirement_300102_03.md) | 2030-01-02 | 청구 | 진행 중 | - |
"""


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "docs" / "plans").mkdir(parents=True)
    (r / "docs" / "requirement").mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    write(r)
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "시작")
    return r


def write(r: Path, dep="order", s1="진행 중"):
    (r / "docs/plans/master_plan.md").write_text(PLAN.format(dep=dep), encoding="utf-8")
    (r / "docs/requirement/requirement_index.md").write_text(INDEX.format(s1=s1), encoding="utf-8")


def test_plan_waves_from_predecessor(repo):
    p = dispatch.plan(repo)
    assert not p["errors"]
    assert p["waves"] == [["order", "member"], ["billing"]]           # billing 은 order 가 끝난 뒤
    assert p["bundles"]["order"]["reqs"] == {"REQ-300102-01": "진행 중"}


def test_finished_predecessor_does_not_split_wave(repo):
    write(repo, s1="완료")                                              # order 의 REQ 가 끝났다
    p = dispatch.plan(repo)
    assert p["finished"] == ["order"]
    assert p["waves"] == [["member", "billing"]]                         # 끝난 선행은 기다리지 않는다


def test_cycle_and_unknown_predecessor_are_errors(repo):
    text = (repo / "docs/plans/master_plan.md").read_text(encoding="utf-8").replace(
        "| order | services/order/** | REQ-300102-01 | - |", "| order | services/order/** | REQ-300102-01 | billing |")
    (repo / "docs/plans/master_plan.md").write_text(text, encoding="utf-8")
    assert any("순환" in e for e in dispatch.plan(repo)["errors"])
    write(repo, dep="ghost")
    assert any("ghost" in e for e in dispatch.plan(repo)["errors"])


def test_write_draft_then_next_reads_human_edit(repo):
    path = dispatch.write_draft(repo, date="2030-01-02")
    assert path == repo / "docs/plans/drafts/dispatch_2030-01-02.md"
    text = path.read_text(encoding="utf-8")
    assert "## 분할안" in text and "python nova.py worktree-new order" in text
    with pytest.raises(SystemExit, match="이미 있다"):
        dispatch.write_draft(repo, date="2030-01-02")                    # 사람이 고친 초안을 덮지 않는다
    nx = dispatch.next_step(repo, path)
    assert nx["wave"] == 1 and nx["commands"] == ["python nova.py worktree-new order", "python nova.py worktree-new member"]
    # 사람이 member 를 파도 2 로 옮겼다 → 파도 1 은 order 하나
    path.write_text(text.replace("| 1 | member |", "| 2 | member |"), encoding="utf-8")
    assert dispatch.next_step(repo, path)["commands"] == ["python nova.py worktree-new order"]
    # order 가 끝나면 다음 파도
    write(repo, s1="완료")
    nx = dispatch.next_step(repo, path)
    assert nx["wave"] == 2 and "python nova.py worktree-new member" in nx["commands"]


def test_next_skips_open_worktree_and_stops_when_gate_closed(repo):
    path = dispatch.write_draft(repo, date="2030-01-02")
    (repo / ".worktrees" / "wt-order").mkdir(parents=True)               # 이미 열려 있다
    nx = dispatch.next_step(repo, path)
    assert nx["open"] == ["order"] and nx["commands"] == ["python nova.py worktree-new member"]
    text = (repo / "docs/plans/master_plan.md").read_text(encoding="utf-8").replace("| 완료 | test 녹색 a1b2c3 |", "| 진행 | - |")
    (repo / "docs/plans/master_plan.md").write_text(text, encoding="utf-8")
    nx = dispatch.next_step(repo, path)
    assert nx["commands"] == [] and nx["gate"]                            # 게이트가 닫히면 안내하지 않는다


def test_write_requires_main(repo, monkeypatch):
    monkeypatch.delenv("NOVA_ALLOW_WORKTREE_WRITE", raising=False)  # 가드 자체를 시험한다(conftest 가 연 것을 닫음)
    git(repo, "worktree", "add", "-q", "-b", "wt-x", str(repo / ".worktrees" / "wt-x"))
    with pytest.raises(SystemExit, match="단일 기록자"):
        dispatch.write_draft(repo / ".worktrees" / "wt-x", date="2030-01-02")
