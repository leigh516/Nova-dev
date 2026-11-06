"""병렬 개발 · 메시지 버스 · 종료 조건 · 릴리스(ADR-008) — 임시 git 저장소에서."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import collab
import goals
import novalib
import parallel
import release

PLAN = """# 마스터플랜

## 공통 영역 완료 선언
| 항목 | 상태 | 증거 |
|---|---|---|
| CI · 테스트 녹색 | {ci} | {ev} |
| 화면 틀 · 토큰 | 완료 | web/packages/ui |

## 병렬 묶음
| 묶음 | 경로 | 담당 REQ |
|---|---|---|
| order | services/order/**, web/apps/app/app/orders/** | REQ-300102-01 |
| {b2} | {p2} | REQ-300102-02 |
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
    plan(r)
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "시작")
    return r


def plan(r, ci="완료", ev="test 녹색 a1b2c3", b2="member", p2="services/member/**"):
    (r / "docs/plans/master_plan.md").write_text(PLAN.format(ci=ci, ev=ev, b2=b2, p2=p2), encoding="utf-8")


def test_gate_reasons(repo):
    assert parallel.gate(repo / "docs/plans/master_plan.md")[0] == []
    plan(repo, ci="진행")
    assert any("완료(또는 미해당)" in w for w in parallel.gate(repo / "docs/plans/master_plan.md")[0])
    plan(repo, ev="-")
    assert any("증거가 없다" in w for w in parallel.gate(repo / "docs/plans/master_plan.md")[0])
    plan(repo, p2="services/order/api/**")
    assert any("겹친다" in w for w in parallel.gate(repo / "docs/plans/master_plan.md")[0])
    plan(repo, b2="order")
    assert any("2개 이상" in w for w in parallel.gate(repo / "docs/plans/master_plan.md")[0])
    (repo / "docs/plans/master_plan.md").write_text("# 표 없음\n", encoding="utf-8")
    assert any("공통 영역 완료 선언" in w for w in parallel.gate(repo / "docs/plans/master_plan.md")[0])


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_worktree_bus_single_writer_and_converge(repo, monkeypatch):
    monkeypatch.delenv("NOVA_ALLOW_WORKTREE_WRITE", raising=False)  # 가드 자체를 시험한다(conftest 가 연 것을 닫음)
    wt = parallel.new("order", root=repo, install=False, push=False)
    assert wt == repo / ".worktrees" / "wt-order" and novalib.current_branch(wt) == "wt-order"
    assert novalib.in_linked_worktree(wt) and not novalib.in_linked_worktree(repo)
    assert novalib.main_root(wt) == repo                                   # worktree 에서도 버스는 본 트리 하나
    inbox = [m for m in collab.messages(wt) if collab.for_me(m, "wt-order")]
    assert inbox and inbox[0]["type"] == "handoff" and "services/order/**" in inbox[0]["body"]
    with pytest.raises(SystemExit, match="단일 기록자"):
        novalib.require_main("요구 문서", wt)
    with pytest.raises(SystemExit, match="게이트"):
        plan(repo, ci="진행")
        parallel.new("member", root=repo, install=False, push=False)
    git(repo, "checkout", "--", "docs/plans/master_plan.md")
    # 작업 → 질문 · 회신 · 끝
    q = collab.send(["main"], "question", "공통 버튼을 고쳐도 되나요", "주문 화면에 필요합니다", cwd=wt)
    assert q["from"] == "wt-order"
    with pytest.raises(SystemExit, match="받는 사람만"):
        collab.done(q["id"], "됨", actor="wt-member", cwd=repo)
    a = collab.send(["wt-order"], "report", "답", "main 이 고칩니다", reply_to=q["id"], cwd=repo)
    assert a["thread"] == q["id"] and a["hop"] == 2
    collab.done(q["id"], "main 이 공통부 수정", cwd=repo)
    assert any(m["id"] == q["id"] and m["done"] for m in collab.messages(repo, archived=True))
    b = collab.send(["main"], "question", "또", "또", reply_to=a["id"], cwd=wt)
    with pytest.raises(SystemExit, match="escalation"):
        collab.send(["main"], "question", "또또", "또또", reply_to=b["id"], cwd=repo)
    # worktree 에서 커밋 → main 에서 병합
    (wt / "services/order").mkdir(parents=True)
    (wt / "services/order/a.py").write_text("x = 1\n", encoding="utf-8")
    git(wt, "add", "-A")
    git(wt, "commit", "-q", "-m", "주문 서비스")
    assert "merge: wt-order" in parallel.converge("order", root=repo)
    assert (repo / "services/order/a.py").exists()


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_converge_scope_handoff_broadcast_and_sync(repo, capsys):
    """converge 는 묶음 경로 밖 파일이 있으면 병합을 거부하고(HANDOFF.md 는 허용), 병합 뒤 남은 worktree 에 알린다.
    worktree-sync 는 뒤처짐 0 이면 끝, 아니면 들어올 변경을 갈라 보이고 merge(rebase 아님) 뒤 main 에 보고한다."""
    order = parallel.new("order", root=repo, install=False, push=False)
    member = parallel.new("member", root=repo, install=False, push=True)          # 원격이 없으면 push 는 경고만
    assert "push" in capsys.readouterr().out
    assert parallel.sync(cwd=member)["behind"] == 0                                 # 뒤처짐 0 — 할 일 없음
    (order / "services/order").mkdir(parents=True)
    (order / "services/order/a.py").write_text("x = 1\n", encoding="utf-8")
    (order / "scripts").mkdir()
    (order / "scripts/common.py").write_text("y = 1\n", encoding="utf-8")         # 묶음 경로 밖(공통부)
    git(order, "add", "-A")
    git(order, "commit", "-q", "-m", "주문 + 경로 밖")
    with pytest.raises(SystemExit, match="scripts/common.py"):
        parallel.converge("order", root=repo, notify=False)
    assert not (repo / "services/order/a.py").exists()                             # 병합하지 않았다
    git(order, "rm", "-q", "scripts/common.py")
    (order / "HANDOFF.md").write_text("# 인계\n주문 API 는 아직 페이지 없음\n", encoding="utf-8")
    git(order, "add", "-A")
    git(order, "commit", "-q", "-m", "경로 밖 되돌림 · 인계 메모")
    assert "merge: wt-order" in parallel.converge("order", root=repo)
    out = capsys.readouterr().out
    assert "주문 API 는 아직 페이지 없음" in out and "history" in out
    bc = [m for m in collab.messages(repo) if m["to"] == ["*"] and m["type"] == "report"]
    assert bc and "worktree-sync" in bc[0]["subject"]
    with pytest.raises(SystemExit, match="worktree"):
        parallel.sync(cwd=repo)                                                     # 본 트리에서는 쓰지 않는다
    (member / "services/member").mkdir(parents=True)
    (member / "services/member/dirty.py").write_text("z\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="커밋"):
        parallel.sync(cwd=member)                                                   # 더러우면 거부
    (member / "services/member/dirty.py").unlink()
    (member / "services/member").rmdir()
    r = parallel.sync(cwd=member)
    assert r["behind"] >= 1 and "services/order/a.py" in r["groups"]["다른 묶음"]
    assert (member / "services/order/a.py").exists()
    assert novalib.git("rev-list", "--count", "HEAD..main", cwd=member) == "0"      # main 을 품었다(merge — 기존 커밋을 다시 쓰지 않는다)
    assert any(m["from"] == "wt-member" and m["to"] == ["main"] for m in collab.messages(repo))


def test_exit_rules():
    good = [{"id": "E1", "check": "python -c \"print(1)\"", "expect": "통과", "how": "명령", "judged": ""}]
    assert goals.lint(good, "t") == []
    bad = good + [{"id": "E2", "check": "남은 결함을 전부 찾는다", "expect": "없음", "how": "사람", "judged": ""},
                  {"id": "E3", "check": "x", "expect": "y", "how": "기계", "judged": ""}]
    errs = "\n".join(goals.lint(bad, "t"))
    assert "소진형" in errs and "방식" in errs
    md = "## 종료 조건 (exit)\n| ID | 확인 | 기대 | 방식 | 판정 |\n|---|---|---|---|---|\n| E1 | `python -c \"import sys; sys.exit(3)\"` | 통과 | 명령 | |\n| E2 | 화면 확인 | 보인다 | 사람 | 충족 2030-01-02 |\n"
    items = goals.parse_table(md)
    res = goals.judge(items)
    assert [ok for _, ok, _ in res] == [False, True]


def test_release_ship(repo):
    (repo / "nova.project.json").write_text(json.dumps({"name": "t"}), encoding="utf-8")
    (repo / "docs/requirement").mkdir(parents=True)
    (repo / "docs/requirement/requirement_index.md").write_text("| ID | 일자 | 제목 | 상태 | 계획 |\n|---|---|---|---|---|\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "준비")  # ship 은 docs/releases/ 밖 변경이 있으면 거부한다
    d = {"releases": [{"version": "0.1.0", "status": "draft", "goal": "첫 판본", "reqs": [], "not_doing": ["결제"],
                       "exit": [{"id": "E1", "check": f"\"{sys.executable}\" -c \"print(1)\"", "expect": "통과", "how": "명령", "judged": ""}],
                       "drafted": "2030-01-01", "shipped": "", "tag": ""}]}
    release.save(d, repo)
    assert [e for e in release.check(release.load(repo), repo) if "CHANGELOG" not in e] == []   # CHANGELOG 는 ship 이 만든다
    with pytest.raises(SystemExit, match="릴리스 노트"):
        release.ship("0.1.0", repo)
    (repo / "docs/releases/v0.1.0.md").write_text("# v0.1.0\n## 복제본이 받을 때\n충돌 없음\n## 되돌리기\n이전 태그 이미지로 재배포 · DB 변경 없음\n", encoding="utf-8")
    r = release.ship("0.1.0", repo)
    assert r["status"] == "shipped" and r["tag"] == "v0.1.0"
    assert json.loads((repo / "nova.project.json").read_text(encoding="utf-8"))["version"] == "0.1.0"
    two = release.load(repo)
    two["releases"].append({**two["releases"][0], "version": "0.2.0", "status": "draft", "goal": "x" * 400, "not_doing": []})
    errs = "\n".join(release.check(two, repo))
    assert "1~300자" in errs and "하지 않는 것" in errs


FAKE_GEN = """import json, pathlib, sys
if {code}:
    sys.exit({code})  # 실제 gen_k3s 처럼 실패하면 아무것도 쓰지 않는다
root = pathlib.Path(__file__).resolve().parent.parent
v = json.loads((root / "nova.project.json").read_text(encoding="utf-8"))["version"]
(root / "infra").mkdir(exist_ok=True)
(root / "infra" / "tag.txt").write_text(v, encoding="utf-8")
"""


def _ship_ready(repo, gen_code=0):
    """낼 수 있는 draft 판본 + 생성기 대역(scripts/gen_k3s.py — meta version 을 infra/tag.txt 에 쓴다)."""
    (repo / "nova.project.json").write_text(json.dumps({"name": "t", "version": "0.0.1"}), encoding="utf-8")
    (repo / "docs/requirement").mkdir(parents=True)
    (repo / "docs/requirement/requirement_index.md").write_text("| ID | 일자 | 제목 | 상태 | 계획 |\n|---|---|---|---|---|\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts/gen_k3s.py").write_text(FAKE_GEN.format(code=gen_code), encoding="utf-8")
    d = {"releases": [{"version": "0.2.0", "status": "draft", "goal": "둘째 판본", "reqs": [], "not_doing": ["결제"],
                       "exit": [{"id": "E1", "check": f"\"{sys.executable}\" -c \"print(1)\"", "expect": "통과", "how": "명령", "judged": ""}],
                       "drafted": "2030-01-01", "shipped": "", "tag": ""}]}
    release.save(d, repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "판본 준비")
    (repo / "docs/releases/v0.2.0.md").write_text("# v0.2.0\n## 복제본이 받을 때\n충돌 없음\n## 되돌리기\n이전 태그 v0.1.0 으로 재배포 · DB 변경 없음\n", encoding="utf-8")


def test_release_ship_tags_after_commit(repo):
    """P-3 — 판본 기록 · 생성물 재생성 → 커밋 → 태그. 태그가 가리키는 커밋에 그 판본의 version · 생성물 · shipped 가 들어 있다."""
    _ship_ready(repo)
    release.ship("0.2.0", repo)
    show = lambda path: novalib.git("show", f"v0.2.0:{path}", cwd=repo)  # noqa: E731
    assert json.loads(show("nova.project.json"))["version"] == "0.2.0"
    assert show("infra/tag.txt") == "0.2.0"
    assert json.loads(show("docs/releases/releases.json"))["releases"][0]["status"] == "shipped"
    assert "v0.2.0" in show("docs/releases/v0.2.0.md")                                   # 노트도 같은 커밋에
    assert novalib.git("rev-parse", "v0.2.0^{commit}", cwd=repo) == novalib.git("rev-parse", "HEAD", cwd=repo)
    assert novalib.git("status", "--porcelain", cwd=repo) == ""                           # 남은 변경 없음


def test_release_ship_refuses_dirty_tree_and_existing_tag(repo):
    """판본 커밋에 남의 변경이 섞이지 않게 docs/releases/ 밖 변경이 있으면 거부, 태그가 이미 있으면 기록 전에 멈춘다."""
    _ship_ready(repo)
    (repo / "scripts/other.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="scripts/other.py"):
        release.ship("0.2.0", repo)
    (repo / "scripts/other.py").unlink()
    git(repo, "tag", "-a", "v0.2.0", "-m", "먼저 있던 태그")
    with pytest.raises(SystemExit, match="태그 v0.2.0 이 이미"):
        release.ship("0.2.0", repo)
    assert json.loads((repo / "nova.project.json").read_text(encoding="utf-8"))["version"] == "0.0.1"  # 아무것도 쓰지 않았다


def test_release_ship_tag_failure_exits_nonzero(repo, monkeypatch):
    """태그를 못 만들면 성공으로 끝내지 않는다(예전엔 실패를 출력만 하고 종료 0)."""
    _ship_ready(repo)
    real = release.git

    def fail_tag(*a, **k):
        if a[:2] == ("tag", "-a"):
            raise RuntimeError("git tag 실패: 대역")
        return real(*a, **k)
    monkeypatch.setattr(release, "git", fail_tag)
    with pytest.raises(SystemExit, match="태그") as e:
        release.ship("0.2.0", repo)
    assert e.value.code != 0
    assert "chore(release): v0.2.0" in novalib.git("log", "-1", "--format=%s", cwd=repo)  # 커밋은 됐다 — 태그만 다시


def test_release_check_rejects_not_doing_placeholder(repo):
    """draft 가 넣는 자리표시 '(… 채운다)' 를 그대로 두면 하지 않는 것이 정해지지 않은 것이다."""
    _ship_ready(repo)
    d = release.load(repo)
    d["releases"][0]["not_doing"] = ["(이 판본에서 하지 않는 것 — 채운다)"]
    assert any("자리표시" in e for e in release.check(d, repo))
    release.save(d, repo)
    with pytest.raises(SystemExit, match="자리표시"):
        release.ship("0.2.0", repo)


def test_release_ship_regenerates_infra(repo):
    """판본 기록 직후 인프라 생성물을 다시 만든다 — 안 그러면 운영 이미지 태그가 지난 판본에 머물고 lint 가 깨진다."""
    _ship_ready(repo)
    release.ship("0.2.0", repo)
    assert (repo / "infra/tag.txt").read_text(encoding="utf-8") == "0.2.0"


def test_release_ship_regen_failure_stops_before_shipped(repo):
    """생성기가 실패하면 멈추고 판본은 draft 로 남는다(다시 ship 할 수 있다)."""
    _ship_ready(repo, gen_code=3)
    with pytest.raises(SystemExit, match="gen_k3s"):
        release.ship("0.2.0", repo)
    assert release.load(repo)["releases"][0]["status"] == "draft"
    assert json.loads((repo / "nova.project.json").read_text(encoding="utf-8"))["version"] == "0.0.1"  # meta 도 되돌린다
    assert release.changed_paths(repo) == ["docs/releases/v0.2.0.md"]   # 고친 뒤 다시 ship 할 수 있는 상태


def test_masterplan_first_adopt_from_start_draft(tmp_path):
    """새 프로젝트의 첫 채택 — 정본이 '시작 초안 v0.1'(정식 줄 없음)이어도 v1.0 으로 채택된다(리허설에서 멈췄던 결함)."""
    import masterplan as mp
    p = tmp_path / "r" / "docs" / "plans"
    (p / "drafts").mkdir(parents=True)
    (p / "archive").mkdir()
    head = "| 항목 | 값 |\n|---|---|\n| 버전 | **v{v}** |\n| 상태 | {s} |\n| 채택일 | - |\n| 이전 정식 | - |\n"
    (p / "master_plan.md").write_text("# 마스터플랜\n\n" + head.format(v="0.1", s="초안(첫 요구를 정리한 뒤 v1.0 으로 채택)"), encoding="utf-8")
    (p / "master_plan_changelog.md").write_text(
        "# 이력\n\n| 버전 | 상태 | 날짜 | 바뀐 것 | 근거 | 원본 |\n|---|---|---|---|---|---|\n"
        "| v0.1 | 초안 | 2026-11-04 | Nova 에서 생성 | - | [master_plan.md](master_plan.md) |\n", encoding="utf-8")
    root = tmp_path / "r"
    assert mp.check(root) == []
    draft = p / "drafts" / "master_plan_v1.0-draft.md"
    draft.write_text("# 마스터플랜\n\n" + head.format(v="1.0", s="초안"), encoding="utf-8")
    assert mp.adopt(draft, "REQ-261104-01", "첫 판본", root) == "1.0"
    rows = mp.changelog_rows(root)
    assert [(r["version"], r["state"]) for r in rows] == [("0.1", "보관"), ("1.0", "정식")]
    assert "보관(봉인)" in (p / "archive" / "master_plan_v0.1.md").read_text(encoding="utf-8")
    assert mp.check(root) == []


def test_masterplan_adopt_seal_and_tamper(tmp_path):
    """마스터플랜 판본 — 초안 채택이 지난 판본을 봉인하고, 봉인본을 고치면 잡는다(psg05 ADR-0065 · 0066)."""
    import shutil
    import masterplan as mp
    root = tmp_path / "r"
    shutil.copytree(Path(__file__).resolve().parents[1] / "docs" / "plans", root / "docs" / "plans")
    assert mp.check(root) == []
    cur = mp.version_of((root / "docs/plans/master_plan.md").read_text(encoding="utf-8"))
    nxt = f"{cur.split('.')[0]}.{int(cur.split('.')[1]) + 1}"
    draft = root / "docs/plans/drafts" / f"master_plan_v{nxt}-draft.md"
    draft.write_text((root / "docs/plans/master_plan.md").read_text(encoding="utf-8")
                     .replace(f"**v{cur}**", f"**v{nxt}**").replace("| 상태 | 정식 |", "| 상태 | 초안 |"), encoding="utf-8")
    with pytest.raises(SystemExit, match="--why"):
        mp.adopt(draft, "", "바뀐 것", root)
    assert mp.adopt(draft, "REQ-300102-01", "병렬 게이트 표 추가", root) == nxt
    assert not draft.exists()
    arch = root / "docs/plans/archive" / f"master_plan_v{cur}.md"
    assert arch.exists() and arch.name in mp.seals(root)
    rows = mp.changelog_rows(root)
    assert rows[-1]["version"] == nxt and rows[-1]["state"] == "정식" and [r["state"] for r in rows].count("정식") == 1
    assert mp.check(root) == []
    arch.write_text(arch.read_text(encoding="utf-8") + "\n몰래 고침\n", encoding="utf-8")
    assert any("봉인된 보관본" in e for e in mp.check(root))
    (root / "docs/plans/drafts/x.md").write_text("| 버전 | **v9.0** |\n| 상태 | 정식 |\n", encoding="utf-8")
    assert any("초안은 정본이 될 수 없다" in e for e in mp.check(root))


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_sync_dry_base_unknown_bundle_and_conflict_advice(repo, capsys):
    """worktree-sync --dry 는 갈라 보이기만 하고 병합하지 않는다(파괴적 변경 판독 관문 앞).
    병합하면 상속 기준(옛 갈래점 → 새 main)을 돌려주고, 내 묶음 행이 없으면 0개가 아니라 '판정 불가'로 말한다.
    충돌 처방은 경로 부류로 정해진다 — 공통부 · 기록은 main, 내 묶음은 브랜치, 그 밖은 사용자 판정."""
    member = parallel.new("member", root=repo, install=False, push=False)
    base0 = novalib.git("rev-parse", "--short", "HEAD", cwd=member)
    (repo / "scripts").mkdir()
    (repo / "scripts/common.py").write_text("y = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "공통부 갱신")
    d = parallel.sync(cwd=member, dry=True, notify=False)
    assert d["dry"] and not d["merged"] and d["behind"] == 1 and d["mine_known"]
    assert not (member / "scripts/common.py").exists()                              # 병합하지 않았다
    r = parallel.sync(cwd=member, notify=False)
    assert r["merged"] and r["base_before"] == base0
    assert r["base_after"] == novalib.git("rev-parse", "--short", "main", cwd=repo)
    assert "상속 기준" in capsys.readouterr().out
    # 묶음 표에 내 행이 없다 → 판정 불가(0개와 다르다)
    plan(repo, b2="pay", p2="services/pay/**")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "묶음 표에서 member 를 뺌")
    u = parallel.sync(cwd=member, dry=True, notify=False)
    assert u["mine_known"] is False and "판정 불가" in capsys.readouterr().out
    # 충돌 처방
    bundles = [{"묶음": "member", "경로": "services/member/**"}, {"묶음": "order", "경로": "services/order/**"}]
    mine = bundles[0]
    adv = parallel.conflict_advice(["scripts/common.py", "docs/history/h.md", "services/member/a.py",
                                    "services/order/b.py", "zzz.txt"], mine, bundles)
    assert adv["scripts/common.py"].startswith("main 채택")
    assert adv["docs/history/h.md"].startswith("main 채택") and "단일 기록자" in adv["docs/history/h.md"]
    assert adv["services/member/a.py"].startswith("브랜치 채택")
    assert adv["services/order/b.py"].startswith("정지") and adv["zzz.txt"].startswith("정지")


# ───────────────────────── 심층 감사 1회차 고침(T04-9.01 · 9.02)
def inbox_ids(repo, who):
    """받은함 판정 두 곳(collab inbox · handoff 관측)이 같은 답을 내는지 함께 본다 — cwd 를 넘겨 임시 저장소의 버스만 읽는다."""
    import handoff
    ids = {m["id"][-8:] for m in collab.pending(who, repo)}
    if who != "main":
        assert ids == {m["id"][-8:] for m in handoff.unread(who, repo)}
    return ids


@pytest.mark.slow  # 실측 11초(준비 3.4 + 본문 8.2) — 받은함 판정마다 git 을 부른다
def test_broadcast_done_is_per_recipient(repo):
    """L-F1 — 전체 수신(*) 메시지는 받는 세션마다 처리 상태가 따로다. 한 세션이 끝내도 다른 세션 받은함에는 남는다."""
    m = collab.send(["*"], "report", "main 갱신 — /worktree-sync", "따라잡는다", sender="main", cwd=repo)
    short = m["id"][-8:]
    collab.done(m["id"], "따라잡음", actor="wt-a", cwd=repo)
    assert short not in inbox_ids(repo, "wt-a")          # 끝낸 세션에서는 닫힘
    assert short in inbox_ids(repo, "wt-b")              # 다른 세션에는 그대로
    assert short in inbox_ids(repo, "main")              # 거두는 것은 main — main 이 끝내기 전에는 보인다
    collab.done(m["id"], "따라잡음", actor="wt-b", cwd=repo)
    assert short not in inbox_ids(repo, "wt-b")
    collab.done(m["id"], "모두 거둠", actor="main", cwd=repo)
    assert short not in inbox_ids(repo, "main") and short not in inbox_ids(repo, "wt-c")


def test_multi_recipient_done_is_per_recipient(repo):
    """L-F1 형제 — --to a,b 도 한 사람이 끝냈다고 다른 사람 받은함에서 사라지지 않는다(모두 끝내면 archive)."""
    m = collab.send(["wt-a", "wt-b"], "question", "둘에게", "각자 답한다", sender="main", cwd=repo)
    short = m["id"][-8:]
    collab.done(m["id"], "a 답", actor="wt-a", cwd=repo)
    assert short not in inbox_ids(repo, "wt-a")
    assert short in inbox_ids(repo, "wt-b")
    collab.done(m["id"], "b 답", actor="wt-b", cwd=repo)
    assert short not in inbox_ids(repo, "wt-b")
    assert any(x["id"] == m["id"] for x in collab.messages(repo, archived=True))
    assert not any(x["id"] == m["id"] for x in collab.messages(repo))    # 모두 끝냈으니 버스에서 archive 로


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_converge_scope_catches_rename_from_outside(repo):
    """L-F3 — 묶음 경로 밖 파일을 경로 안으로 git mv 해도 옛 경로(밖)가 범위 검사에 걸린다."""
    (repo / "scripts").mkdir()
    (repo / "scripts/common.py").write_text("y = 1\n" * 20, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "공통부")
    order = parallel.new("order", root=repo, install=False, push=False, notify=False)
    (order / "services/order").mkdir(parents=True)
    git(order, "mv", "scripts/common.py", "services/order/common.py")
    git(order, "commit", "-q", "-m", "공통부를 묶음 안으로 옮김")
    with pytest.raises(SystemExit, match="scripts/common.py"):
        parallel.converge("order", root=repo, notify=False)
    assert (repo / "scripts/common.py").exists()                                    # 병합하지 않았다


# ───────────────────────── 격리 작업 폴더 · 병합 끝난 worktree 정리(REQ-261105-10-4)
def _branches(repo):
    return novalib.git("branch", "--format=%(refname:short)", cwd=repo).split()


def test_scratch_needs_no_gate_and_registers_on_bus(repo):
    """격리 작업 폴더는 병렬 게이트 · 묶음 표를 보지 않는다 — 게이트가 닫혀 있어도 만든다. 버스에 인계 카드를 남긴다."""
    plan(repo, ci="진행")                                                            # 게이트 닫힘
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "게이트 닫음")
    p = parallel.scratch("heavy-test", root=repo, install=False)
    assert p == repo / ".worktrees" / "scratch-heavy-test"
    assert novalib.current_branch(p) == "scratch-heavy-test"
    assert (p / ".pytest_tmp").is_dir()
    cards = [m for m in collab.messages(repo) if collab.for_me(m, "scratch-heavy-test")]
    assert len(cards) == 1 and cards[0]["type"] == "handoff"
    body = cards[0]["body"]
    assert "격리 작업" in body and "번호" in body and "report" in body and "worktree-prune" in body


def test_scratch_refusals(repo, capsys):
    """이름 규칙 · 이미 있음 · 본 트리 미커밋 변경은 거부. 원격 푸시는 기본으로 하지 않는다."""
    with pytest.raises(SystemExit, match="이름"):
        parallel.scratch("Bad_Name", root=repo, install=False, notify=False)
    parallel.scratch("x1", root=repo, install=False, notify=False)
    assert "push" not in capsys.readouterr().out                                   # 기본은 푸시 안 함
    with pytest.raises(SystemExit, match="이미"):
        parallel.scratch("x1", root=repo, install=False, notify=False)
    (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="커밋"):
        parallel.scratch("x2", root=repo, install=False, notify=False)
    assert not (repo / ".worktrees" / "scratch-x2").exists()


def test_scratch_cli_rejects_both_or_neither(repo, monkeypatch):
    monkeypatch.setattr(parallel, "main_root", lambda *a, **k: repo)
    with pytest.raises(SystemExit):
        parallel.main(["new"])
    with pytest.raises(SystemExit):
        parallel.main(["new", "order", "--scratch", "x"])


@pytest.mark.slow  # worktree 셋 + 병합 — 실측 수 초
def test_prune_dry_then_yes(repo, capsys):
    """병합됨 · 미커밋 0 · 받은함 미처리 0 인 것만 정리한다. 기본은 보여 주기만, --yes 일 때만 지운다. 원격은 건드리지 않는다."""
    done_wt = parallel.scratch("done", root=repo, install=False)                    # 병합됨 + 깨끗 + 카드 처리 → 정리 대상
    open_wt = parallel.scratch("open", root=repo, install=False, notify=False)     # 병합 안 됨
    dirty_wt = parallel.scratch("dirty", root=repo, install=False, notify=False)   # 병합됨 + 미커밋
    mail_wt = parallel.scratch("mail", root=repo, install=False, notify=False)     # 병합됨 + 받은함 미처리
    for wt, f in ((done_wt, "a.txt"), (open_wt, "b.txt")):
        (wt / f).write_text("x\n", encoding="utf-8")
        git(wt, "add", "-A")
        git(wt, "commit", "-q", "-m", f)
    git(repo, "merge", "-q", "--no-ff", "scratch-done", "-m", "병합")
    (dirty_wt / "wip.txt").write_text("작업 중\n", encoding="utf-8")
    collab.send(["scratch-mail"], "question", "확인", "답 주세요", sender="main", cwd=repo)
    card = next(m for m in collab.messages(repo) if collab.for_me(m, "scratch-done"))
    collab.done(card["id"], "끝", actor="scratch-done", cwd=repo)

    rows = {r["branch"]: r for r in parallel.prune(root=repo)}
    out = capsys.readouterr().out
    assert rows["scratch-done"]["ok"] and not rows["scratch-done"]["removed"]
    assert not rows["scratch-open"]["ok"] and any("병합" in w for w in rows["scratch-open"]["why"])
    assert not rows["scratch-dirty"]["ok"] and any("미커밋" in w for w in rows["scratch-dirty"]["why"])
    assert not rows["scratch-mail"]["ok"] and any("받은함" in w for w in rows["scratch-mail"]["why"])
    assert "남김" in out and "--yes" in out
    assert done_wt.exists() and "scratch-done" in _branches(repo)                    # dry — 아무것도 지우지 않았다

    rows = {r["branch"]: r for r in parallel.prune(root=repo, yes=True)}
    out = capsys.readouterr().out
    assert rows["scratch-done"]["removed"] and not done_wt.exists()
    assert "scratch-done" not in _branches(repo)
    assert all(b in _branches(repo) for b in ("scratch-open", "scratch-dirty", "scratch-mail"))
    assert open_wt.exists() and dirty_wt.exists() and mail_wt.exists()
    assert "원격" in out


@pytest.mark.slow  # worktree 둘 + 병합 — 실측 수 초
def test_prune_ignores_broadcast_report(repo):
    """전체 공지(to * · report — converge 의 "main 갱신")는 병합 끝난 worktree 정리를 막지 않는다.
    병합된 쪽에는 따라올 일이 없어서다. 전체에 보낸 질문 · 인계처럼 답이 필요한 것은 계속 막는다."""
    notice_wt = parallel.scratch("notice", root=repo, install=False, notify=False)
    ask_wt = parallel.scratch("ask", root=repo, install=False, notify=False)
    for wt in (notice_wt, ask_wt):
        (wt / f"{wt.name}.txt").write_text("x\n", encoding="utf-8")
        git(wt, "add", "-A")
        git(wt, "commit", "-q", "-m", wt.name)
        git(repo, "merge", "-q", "--no-ff", wt.name, "-m", "병합")
    collab.send(["*"], "report", "main 갱신 — /worktree-sync", "따라오세요", sender="main", cwd=repo)
    rows = {r["branch"]: r for r in parallel.prune(root=repo)}
    assert rows["scratch-notice"]["ok"] and rows["scratch-ask"]["ok"]               # 공지만 있으면 둘 다 정리 대상

    collab.send(["*"], "question", "모두 확인", "답 주세요", sender="main", cwd=repo)
    rows = {r["branch"]: r for r in parallel.prune(root=repo)}
    assert not rows["scratch-ask"]["ok"] and any("받은함 미처리 1개" in w for w in rows["scratch-ask"]["why"])


def test_prune_windows_locked_folder_still_deletes_branch(repo, monkeypatch, capsys):
    """Windows 함정 — worktree remove 가 등록만 풀고 폴더 삭제에서 Permission denied, 빈 폴더 rmdir 도 busy.
    실패로 끝내지 않고 worktree prune → 브랜치 삭제는 진행, 남은 폴더는 경고로 보고한다."""
    import shutil
    wt = parallel.scratch("locked", root=repo, install=False, notify=False)
    real = parallel._run

    def fake(args, cwd):
        if args[:3] == ["git", "worktree", "remove"]:
            shutil.rmtree(wt)                       # 내용(.git 파일 포함)은 지워지고
            wt.mkdir()                              # 빈 폴더만 남는다 — 다른 창이 잡고 있다
            return subprocess.CompletedProcess(args, 1, "", f"error: failed to delete '{wt}': Permission denied")
        return real(args, cwd)

    def busy(p):
        raise OSError("Device or resource busy")
    monkeypatch.setattr(parallel, "_run", fake)
    monkeypatch.setattr(parallel, "_rmdir", busy)
    rows = parallel.prune(root=repo, yes=True)
    out = capsys.readouterr().out
    r = next(x for x in rows if x["branch"] == "scratch-locked")
    assert r["removed"] and r["leftover"] == str(wt)
    assert "scratch-locked" not in _branches(repo)                                  # 브랜치 삭제는 막히지 않았다
    assert "남은 폴더" in out and str(wt) in out
    assert "scratch-locked" not in novalib.git("worktree", "list", cwd=repo)
