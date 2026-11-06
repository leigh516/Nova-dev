"""상류 판본 받기(scripts/upstream.py) — 3-way 판정 표 · 공통부 분류 · surface 가 있으면 아무것도 쓰지 않음(임시 git 저장소 두 개)."""
import json
import subprocess

import pytest

import new_project
import upstream as up


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


# ───────────────────────── 판정 표(순수 함수)
@pytest.mark.parametrize("base,theirs,mine,verdict", [
    ("a", "b", "a", "replace"),       # 내가 안 건드렸다 → 상류 것으로
    ("a", "b", "b", "already"),       # 이미 그 내용
    ("a", "a", "a", "already"),       # 아무도 안 바꿨다
    (None, "b", None, "add"),         # 상류가 새로 만들었다
    (None, "b", "b", "already"),      # 기준선엔 없지만 양쪽이 같다
    (None, "b", "c", "surface"),      # 양쪽이 같은 경로를 각자 만들었다
    (None, None, "c", "skip"),        # 복제본이 만든 것
    ("a", "a", "c", "skip"),          # 복제본만 고쳤고 상류는 안 바꿨다 — 받을 것이 없다
    ("a", "b", "c", "surface"),       # 둘 다 바꿨다
    ("a", None, "a", "surface"),      # 상류가 지웠다 — 삭제는 판단
    ("a", None, None, "already"),     # 양쪽 다 지웠다
    ("a", "b", None, "surface"),      # 복제본이 지웠는데 상류는 바꿨다
    ("a", "a", None, "skip"),         # 복제본이 지웠고 상류는 그대로 — 되살리지 않는다
])
def test_decide_table(base, theirs, mine, verdict):
    v, reason = up.decide(base, theirs, mine)
    assert v == verdict and reason


def test_scope_is_one_constant():
    assert up.in_scope("scripts/x.py") and up.in_scope(".claude/commands/a.md") and up.in_scope("infra/docker/Dockerfile.web")
    assert not up.in_scope("services/sample/a.py") and not up.in_scope("nova.project.json") and not up.in_scope("docs/history/h.md")
    assert not up.in_scope("packages/common-py/nova_common/services.json")   # 서비스 목록은 프로젝트 소유
    assert not up.in_scope("web/packages/ui/src/tokens.css")                 # 생성물 — 적용 뒤 gen 으로
    assert not up.in_scope("scripts/__pycache__/x.cpython-312.pyc")
    # 도메인 에이전트 — 틀은 받고(packs/_template/), 팩과 짝인 정의 · 생성 편제표는 프로젝트 소유 · 생성물
    assert up.in_scope("packs/_template/agent.md") and up.in_scope(".claude/agents/research/researcher.md")
    assert not up.in_scope(".claude/agents/example-specialist.md")
    # 폴더형(ADR-010) — domain/ 은 통째로 프로젝트 소유
    assert not up.in_scope(".claude/agents/domain/example-specialist.md")
    assert not up.in_scope(".claude/agents/domain/README.md")
    assert not up.in_scope(".claude/agents/README.md")
    assert not up.in_scope("packs/example/pack.json")


def test_classify_tokens_surface_only_and_out_of_scope_ignored():
    base = {"scripts/a.py": "1", "design/tokens/brand.tokens.json": "t1"}
    theirs = {"scripts/a.py": "2", "design/tokens/brand.tokens.json": "t2", "design/tokens/new.json": "n", "services/x.py": "s"}
    mine = {"scripts/a.py": "1", "design/tokens/brand.tokens.json": "t1", "services/x.py": "mine", "scripts/mine.py": "m"}
    out = up.classify(base, theirs, mine)
    assert out["scripts/a.py"][0] == "replace"
    assert out["design/tokens/brand.tokens.json"][0] == "surface"   # 토큰 원천은 프로젝트가 바꾼다 — 자동 덮어쓰기 금지
    assert out["design/tokens/new.json"][0] == "surface"
    assert out["scripts/mine.py"][0] == "skip"
    assert "services/x.py" not in out                                  # 공통부 밖은 판정하지 않는다


# ───────────────────────── 실제 git 저장소 두 개
@pytest.fixture
def pair(tmp_path):
    u = tmp_path / "upstream"
    u.mkdir()
    git(u, "init", "-q", "-b", "main")
    git(u, "config", "user.email", "t@t")
    git(u, "config", "user.name", "t")
    for p, t in {"scripts/a.py": "a = 1\n", "scripts/b.py": "b = 1\n", "docs/conventions/c.md": "# 규약\n",
                 "services/s/x.py": "x = 1\n"}.items():
        (u / p).parent.mkdir(parents=True, exist_ok=True)
        (u / p).write_text(t, encoding="utf-8")
    git(u, "add", "-A")
    git(u, "commit", "-q", "-m", "v1")
    git(u, "tag", "v1.0.0")
    base = git(u, "rev-parse", "HEAD")
    c = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(u), "clone")
    git(c, "config", "user.email", "t@t")
    git(c, "config", "user.name", "t")
    (c / "nova.project.json").write_text(json.dumps({"name": "쇼핑몰", "slug": "shop", "upstream": {"url": str(u), "base": base}},
                                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (c / "scripts/mine.py").write_text("mine = 1\n", encoding="utf-8")               # 복제본이 만든 것 → skip
    (c / "services/s/x.py").write_text("x = 2\n", encoding="utf-8")                  # 공통부 밖 → 대상 아님
    (c / "scripts/b.py").write_text("b = 'clone'\n", encoding="utf-8")               # 복제본도 고침 → surface
    git(c, "add", "-A")
    git(c, "commit", "-q", "-m", "복제본 작업")
    (u / "scripts/a.py").write_text("a = 2\n", encoding="utf-8")                     # 상류만 고침 → replace
    (u / "scripts/b.py").write_text("b = 2\n", encoding="utf-8")
    (u / "scripts/d.py").write_text("d = 1\n", encoding="utf-8")                     # 상류 신규 → add
    git(u, "add", "-A")
    git(u, "commit", "-q", "-m", "v2")
    git(u, "tag", "v2.0.0")
    return u, c


def snapshot(c):
    return {p.relative_to(c).as_posix(): p.read_bytes() for p in c.rglob("*") if p.is_file() and ".git" not in p.parts}


@pytest.mark.slow  # 실측 10초 이상 — quick 에서 빠지고 전체 test 에서만(REQ-261104-17)
def test_plan_and_apply_atomic(pair):
    u, c = pair
    res = up.plan("v2.0.0", root=c)
    got = {p: v for p, (v, _) in res["files"].items()}
    assert got["scripts/a.py"] == "replace" and got["scripts/b.py"] == "surface" and got["scripts/d.py"] == "add"
    assert got["scripts/mine.py"] == "skip" and got["docs/conventions/c.md"] == "already"
    assert "services/s/x.py" not in got
    before = snapshot(c)
    with pytest.raises(SystemExit) as e:
        up.apply("v2.0.0", root=c)
    assert e.value.code == 1
    assert snapshot(c) == before                                       # surface 하나면 한 글자도 쓰지 않는다
    # 복제본이 b.py 를 기준선으로 되돌리면 적용된다
    (c / "scripts/b.py").write_text("b = 1\n", encoding="utf-8")
    out = up.apply("v2.0.0", root=c)
    assert (c / "scripts/a.py").read_text(encoding="utf-8") == "a = 2\n"
    assert (c / "scripts/b.py").read_text(encoding="utf-8") == "b = 2\n"
    assert (c / "scripts/d.py").read_text(encoding="utf-8") == "d = 1\n"
    assert (c / "scripts/mine.py").exists() and (c / "services/s/x.py").read_text(encoding="utf-8") == "x = 2\n"
    snap = c / out["snapshot"]
    assert (snap / "scripts/a.py").read_text(encoding="utf-8") == "a = 1\n"  # 덮어쓰기 전 내용을 남긴다
    meta = json.loads((c / "nova.project.json").read_text(encoding="utf-8"))
    assert meta["upstream"]["base"] == git(u, "rev-parse", "v2.0.0") and meta["upstream"]["tag"] == "v2.0.0"
    rows = json.loads((c / "docs/releases/adoption.json").read_text(encoding="utf-8"))["adoptions"]
    assert len(rows) == 1 and rows[0]["tag"] == "v2.0.0" and rows[0]["replace"] == 2 and rows[0]["add"] == 1
    # 같은 판본을 다시 계획하면 받을 것이 없다
    again = up.plan("v2.0.0", root=c)
    assert not [p for p, (v, _) in again["files"].items() if v in ("replace", "add", "surface")]


def test_status_on_platform_itself(tmp_path, capsys):
    (tmp_path / "nova.project.json").write_text(json.dumps({"name": "Nova", "slug": "nova"}), encoding="utf-8")
    assert up.main(["--root", str(tmp_path), "status"]) == 0
    assert "원천" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="원천"):
        up.plan("v1.0.0", root=tmp_path)


def test_new_project_records_upstream():
    meta = new_project.upstream_meta()
    assert set(meta) == {"url", "base"} and meta["url"]
    assert new_project.upstream_meta(tag="v0.1.0", base="abc")["tag"] == "v0.1.0"


# ───────────────────────── 판본 고르기 · 거리 · 건너뛰는 판본 안내(REQ-261105-06)
CLONE_NOTE = "# v{v}\n## 복제본이 받을 때\n{v} 받을 때 — {say}\n\n## 되돌리기\n이전 태그로\n"


@pytest.fixture
def released(tmp_path):
    """정식 태그 셋 · rc 하나를 낸 상류와, v0.1.0 에서 시작한 복제본."""
    u = tmp_path / "upstream"
    u.mkdir()
    git(u, "init", "-q", "-b", "main")
    git(u, "config", "user.email", "t@t")
    git(u, "config", "user.name", "t")
    (u / "scripts").mkdir()
    (u / "docs/releases").mkdir(parents=True)
    for v, say in (("0.1.0", "첫 판본"), ("0.2.0-rc.1", "사전"), ("0.2.0", "명령 이름 바뀜"), ("0.3.0", "토큰 칸 추가")):
        (u / "scripts/a.py").write_text(f"a = '{v}'\n", encoding="utf-8")
        (u / f"docs/releases/v{v}.md").write_text(CLONE_NOTE.format(v=v, say=say), encoding="utf-8")
        git(u, "add", "-A")
        git(u, "commit", "-q", "-m", f"판본 {v}")
        git(u, "tag", "-a", f"v{v}", "-m", v)
    c = tmp_path / "clone"
    c.mkdir()
    git(c, "init", "-q", "-b", "main")
    (c / "scripts").mkdir()
    (c / "scripts/a.py").write_text("a = '0.1.0'\n", encoding="utf-8")
    (c / "nova.project.json").write_text(json.dumps({"name": "쇼핑몰", "slug": "shop", "upstream": {
        "url": str(u), "base": git(u, "rev-parse", "v0.1.0^{commit}"), "tag": "v0.1.0"}}, ensure_ascii=False), encoding="utf-8")
    return u, c


def test_status_shows_latest_formal_and_distance(released, capsys):
    _, c = released
    assert up.main(["--root", str(c), "status"]) == 0
    out = capsys.readouterr().out
    assert "최신 정식 v0.3.0" in out and "내 기준 v0.1.0" in out and "사이 정식 판본 2개" in out


def test_tags_lists_formal_candidates_and_mine(released, capsys):
    _, c = released
    assert up.main(["--root", str(c), "tags"]) == 0
    out = capsys.readouterr().out
    assert "v0.2.0" in out and "v0.3.0" in out and "v0.2.0-rc.1" not in out
    assert "← 내 기준" in out and "자동으로 고르지 않는다" in out


def test_plan_takes_formal_tag_only_unless_allow_ref(released):
    _, c = released
    with pytest.raises(SystemExit, match="정식 태그"):
        up.plan("main", root=c)
    with pytest.raises(SystemExit, match="정식 태그"):
        up.plan("v0.2.0-rc.1", root=c)
    assert up.plan("v0.2.0-rc.1", root=c, allow_ref=True)["theirs"]          # --allow-ref 로 풀면 받는다


def test_plan_collects_clone_notes_of_skipped_versions(released, capsys):
    _, c = released
    res = up.plan("v0.3.0", root=c)
    assert [t for t, _, _ in res["notes"]] == ["v0.2.0", "v0.3.0"]           # rc 는 빼고, 내 기준(v0.1.0) 뒤부터 대상까지
    assert res["notes"][0][1] == "건너뜀" and "명령 이름 바뀜" in res["notes"][0][2]
    up.report(res)
    out = capsys.readouterr().out
    assert "건너뛰는 판본 1개" in out and "명령 이름 바뀜" in out and "토큰 칸 추가" in out


def test_main_plan_accepts_allow_ref_flag(released):
    _, c = released
    assert up.main(["--root", str(c), "plan", "v0.2.0-rc.1", "--allow-ref"]) == 0
