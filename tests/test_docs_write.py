"""기록 분량 정하기(scripts/docs_write.py) — 등급 경계 · 신호로 올림 · 생성물 · 기록 제외 · tasks 나열을 임시 git 저장소로 확인한다."""
import subprocess
from pathlib import Path

import pytest

import docs_write


def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=True)
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "시험")
    git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("# 시험\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "처음")
    return tmp_path


def touch(root: Path, *rels: str, body: str = "내용\n") -> None:
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def record_git(root: Path) -> None:
    """git 기록 인덱스 · 문서를 만들어 지금 HEAD 를 기준으로 삼게 한다."""
    sha = git(root, "rev-parse", "HEAD")
    touch(root, "docs/git/git_index.md", body="# git\n\n| 기록 | 요약 |\n|---|---|\n| [git_300101_01](git_300101_01.md) | 처음 |\n")
    touch(root, "docs/git/git_300101_01.md", body=f"# 기록\n\n## 커밋\n- `{sha}` 처음\n")


@pytest.mark.parametrize("n, expected", [(2, "작은 일"), (3, "보통 일"), (4, "보통 일"), (5, "큰 일")])
def test_등급_경계(repo, n, expected):
    touch(repo, *[f"src/f{i}.py" for i in range(n)])
    r = docs_write.grade(repo)
    assert r["grade"] == expected
    assert len(r["authored"]) == n


def test_범위를_주면_그_커밋만_본다(repo):
    touch(repo, "a.py", "b.py", "c.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "셋")
    touch(repo, "d.py", "e.py", "f.py")   # 작업 트리 변경은 범위에 안 들어간다
    r = docs_write.grade(repo, "HEAD~1..HEAD")
    assert r["grade"] == "보통 일" and sorted(r["authored"]) == ["a.py", "b.py", "c.py"]


def test_기록_기준_이후_커밋과_작업_트리를_합친다(repo):
    record_git(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "기록")
    touch(repo, "a.py", "b.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "둘")
    touch(repo, "c.py")
    r = docs_write.grade(repo)
    assert sorted(r["authored"]) == ["a.py", "b.py", "c.py"]
    assert r["grade"] == "보통 일"
    assert len(docs_write.commits(repo, None)) == 2   # 기록 기준 커밋 뒤 '기록' · '둘'


def test_ADR_신호는_한_파일이어도_큰_일(repo):
    touch(repo, "docs/adr/ADR-011-시험.md")
    r = docs_write.grade(repo)
    assert r["grade"] == "큰 일" and r["signals"]["ADR"] == ["docs/adr/ADR-011-시험.md"]


def test_DB_모델과_계약_신호(repo):
    touch(repo, "services/x/x/models.py")
    assert docs_write.grade(repo)["signals"]["DB 모델"] == ["services/x/x/models.py"]
    touch(repo, "services/x/x/items.py", body="router = APIRouter()\n")
    touch(repo, "services/gateway/gateway/rbac.json", body="{}\n")
    r = docs_write.grade(repo)
    assert sorted(r["signals"]["계약"]) == ["services/gateway/gateway/rbac.json", "services/x/x/items.py"]
    assert r["grade"] == "큰 일"


def test_생성물만_바뀐_것은_세지_않는다(repo):
    touch(repo, "docs/registry/screens.md", "docs/registry/events.md", "uv.lock")
    touch(repo, "infra/k3s/base/svc.yaml", "web/tokens.css", body="# 생성물: scripts/gen_k3s.py — 손으로 고치지 않는다\n")
    r = docs_write.grade(repo)
    assert r["grade"] == "작은 일" and r["authored"] == [] and len(r["generated"]) == 5


def test_번호_붙는_기록은_세지_않는다(repo):
    touch(repo, "docs/history/history_300101_01.md", "docs/git/git_300101_02.md", "docs/session/LATEST.md",
          "docs/requirement/requirement_300101_01.md", "a.py")
    r = docs_write.grade(repo)
    assert r["grade"] == "작은 일" and r["authored"] == ["a.py"] and len(r["records"]) == 4


def test_기록_하한은_등급마다_늘어난다():
    f = docs_write.FLOOR
    assert len(f["작은 일"]) < len(f["보통 일"]) < len(f["큰 일"])
    assert any("history-new" in x for x in f["보통 일"]) and not any("history-new" in x for x in f["작은 일"])
    assert any("REQ" in x for x in f["큰 일"])


def test_tasks_남은_칸을_갈래_표시와_함께_나열(tmp_path):
    touch(tmp_path, "docs/plans/tasks/tasks_REQ_01.md", body="# task\n- [x] T01-1.01 끝난 일\n- [ ] T01-1.02 남은 일\n"
          "- [ ] 🆕 T01-1.03 새 일\n- [ ] ~~T01-1.04 안 할 일~~ — 범위 밖\n  - [ ] 하위 칸\n")
    touch(tmp_path, "docs/plans/tasks/tasks_REQ_02.md", body="# task\n- [x] 끝\n")
    t = docs_write.open_tasks(tmp_path)
    items = t["docs/plans/tasks/tasks_REQ_01.md"]
    assert [i["kind"] for i in items] == ["미판정", "넘김 표시(🆕)", "기각 표시", "미판정"]
    assert items[0]["line"] == 3 and items[-1]["sub"]
    assert t["docs/plans/tasks/tasks_REQ_02.md"] == []
    out = docs_write.render_tasks(t)
    assert "일괄 체크 금지" in out and "tasks_REQ_01.md:3" in out
    # 읽기 전용 — 파일을 고치지 않는다
    assert "- [ ] T01-1.02" in (tmp_path / "docs/plans/tasks/tasks_REQ_01.md").read_text(encoding="utf-8")


def test_tasks_하나만_고르기와_없는_이름(tmp_path):
    touch(tmp_path, "docs/plans/tasks/tasks_REQ_01.md", body="- [ ] 하나\n")
    touch(tmp_path, "docs/plans/tasks/tasks_REQ_02.md", body="- [ ] 둘\n")
    assert list(docs_write.open_tasks(tmp_path, "tasks_REQ_02")) == ["docs/plans/tasks/tasks_REQ_02.md"]
    with pytest.raises(SystemExit):
        docs_write.open_tasks(tmp_path, "tasks_REQ_09")


def test_facts_는_커밋_등급_미판정_수를_한_장으로(repo):
    record_git(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "기록")
    touch(repo, "docs/plans/tasks/tasks_REQ_01.md", body="- [ ] 남은 일\n- [ ] 🆕 넘긴 일\n")
    f = docs_write.facts(repo)
    assert f["open_tasks"] == {"docs/plans/tasks/tasks_REQ_01.md": 1}
    assert f["grade"]["grade"] == "작은 일"
    assert "숫자를 지어내지 않는다" in docs_write.render_facts(f)
