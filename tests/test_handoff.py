"""worktree 세션 인수인계(handoff status · close-check)와 main 의 읽기 전용 관측(observe)."""
import subprocess

import pytest

import collab
import handoff
import parallel

PLAN = """# 마스터플랜

## 공통 영역 완료 선언
| 항목 | 상태 | 증거 |
|---|---|---|
| CI · 테스트 녹색 | 완료 | test 녹색 a1b2c3 |

## 병렬 묶음
| 묶음 | 경로 | 담당 REQ |
|---|---|---|
| order | services/order/** | REQ-300102-01 |
| member | services/member/** | REQ-300102-02 |
"""


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "docs" / "plans").mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    (r / ".gitignore").write_text(".worktrees/\n.collab/\n", encoding="utf-8")
    (r / "docs/plans/master_plan.md").write_text(PLAN, encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "시작")
    return r


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_status_and_close_check(repo):
    wt = parallel.new("order", root=repo, install=False, push=False)      # 인계 카드(handoff)가 받은함에 온다
    s = handoff.status(cwd=wt)
    assert s["branch"] == "wt-order" and s["behind"] == 0 and s["inbox"] == 1 and not s["handoff"]
    (repo / "README.md").write_text("main 갱신\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "main 갱신")
    assert handoff.status(cwd=wt)["behind"] == 1
    why = handoff.close_check(cwd=wt)
    assert any("받은함" in w for w in why) and any("HANDOFF.md" in w for w in why)
    card = next(m for m in collab.messages(wt) if collab.for_me(m, "wt-order"))
    collab.done(card["id"], "인계 받음", cwd=wt)
    (wt / "HANDOFF.md").write_text("# 인계\n한 일 · 검증 · 남은 것\n", encoding="utf-8")
    assert handoff.close_check(cwd=wt) == []
    collab.send(["main"], "question", "내가 보낸 것", "보낸 것은 내 받은함이 아니다", cwd=wt)
    assert handoff.close_check(cwd=wt) == []
    with pytest.raises(SystemExit, match="worktree 안"):
        handoff.status(cwd=repo)


def test_observe_is_read_only_and_finds_contamination(repo):
    wt = parallel.new("order", root=repo, install=False, push=False)
    (wt / "services/order").mkdir(parents=True)
    (wt / "services/order/a.py").write_text("x = 1\n", encoding="utf-8")
    (wt / "scripts").mkdir()
    (wt / "scripts/common.py").write_text("y = 1\n", encoding="utf-8")     # 묶음 경로 밖 — 커밋됨
    git(wt, "add", "-A")
    git(wt, "commit", "-q", "-m", "주문 + 경로 밖")
    (wt / "docs").mkdir(exist_ok=True)
    (wt / "docs/note.md").write_text("미커밋\n", encoding="utf-8")         # 묶음 경로 밖 — 커밋 안 됨
    before = subprocess.run(["git", "status", "--porcelain"], cwd=wt, capture_output=True, text=True).stdout
    obs = handoff.observe(repo)
    after = subprocess.run(["git", "status", "--porcelain"], cwd=wt, capture_output=True, text=True).stdout
    assert before == after                                                    # 관측은 worktree 를 바꾸지 않는다
    o = next(x for x in obs if x["branch"] == "wt-order")
    assert o["bundle"] == "order" and o["ahead"] == 1 and o["dirty"] == 1 and o["inbox"] == 1
    assert "scripts/common.py" in o["outside"] and "docs/note.md" in o["outside"]
    assert "services/order/a.py" not in o["outside"]
    assert o["row"].startswith("docs/plans/master_plan.md:")                 # 허용 경로가 적힌 줄을 짚는다
    assert any("경로 밖" in p for p in o["problems"])
    with pytest.raises(SystemExit, match="main"):
        handoff.observe(wt)


@pytest.mark.slow  # 실측 10초 이상 — worktree 를 만든다
def test_observe_catches_rename_from_outside(repo):
    """L-F3 형제 — 관측도 묶음 밖 파일을 안으로 옮긴(rename) 옛 경로를 경로 밖 변경으로 잡는다(커밋 · 미커밋 둘 다)."""
    (repo / "scripts").mkdir()
    (repo / "scripts/common.py").write_text("y = 1\n" * 20, encoding="utf-8")
    (repo / "scripts/other.py").write_text("z = 1\n" * 20, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "공통부")
    wt = parallel.new("order", root=repo, install=False, push=False, notify=False)
    (wt / "services/order").mkdir(parents=True)
    git(wt, "mv", "scripts/common.py", "services/order/common.py")
    git(wt, "commit", "-q", "-m", "옮김")
    git(wt, "mv", "scripts/other.py", "services/order/other.py")                # 커밋 안 한 이름 바꾸기
    o = next(x for x in handoff.observe(repo) if x["branch"] == "wt-order")
    assert "scripts/common.py" in o["outside"] and "scripts/other.py" in o["outside"]
