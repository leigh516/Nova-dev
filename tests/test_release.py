"""판본 릴리스 체계(REQ-261105-06) — 판본 규칙 · 번호 제안 · rc · 목표일 · 공개 명령 · CHANGELOG · release 브랜치 워크플로."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import release
import versions

ROOT = Path(__file__).resolve().parents[1]


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    (r / "nova.project.json").write_text(json.dumps({"name": "t", "version": "0.1.0"}), encoding="utf-8")
    (r / "docs/requirement").mkdir(parents=True)
    (r / "docs/requirement/requirement_index.md").write_text("| ID | 일자 | 제목 | 상태 | 계획 |\n|---|---|---|---|---|\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "feat: 시작")
    return r


def commit(r, msg, body=""):
    (r / "f.txt").write_text(msg + body, encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", msg, *(["-m", body] if body else []))


def rel(version, status="draft", **kw):
    return {"version": version, "status": status, "goal": f"{version} 판본", "reqs": [], "not_doing": ["결제"],
            "exit": [{"id": "E1", "check": f"\"{sys.executable}\" -c \"print(1)\"", "expect": "통과", "how": "명령", "judged": ""}],
            "drafted": "2030-01-01", "shipped": "", "tag": "", **kw}


NOTES = ("# v{v}\n## 새로운 것\n- 새 명령 하나\n\n## 바뀐 것 (올릴 때 알아야 할 것)\n- 없음\n\n## 고친 것\n- \n\n"
         "## 복제본이 받을 때\n예상 충돌 없음 — upstream plan v{v} 뒤 apply\n\n## 되돌리기\n이전 태그로 재배포 · DB 변경 없음\n")


# ───────────────────────── 판본 번호 규칙(scripts/versions.py)
def test_versions_parse_sort_and_formal():
    assert versions.is_formal("v0.2.0") and not versions.is_formal("v0.2.0-rc.1") and not versions.is_formal("v1")
    tags = ["v0.1.0", "v0.2.0-rc.1", "v0.10.0-rc.2", "v0.9.1", "main", "v0.2.0"]
    assert versions.latest_formal(tags) == "v0.9.1"                    # 숫자 순서(문자 순서면 0.10 < 0.9) · rc 제외
    assert versions.latest_formal(["v0.1.0-rc.1"]) == "" and versions.latest_formal([]) == ""
    assert versions.key("0.2.0-rc.1") < versions.key("0.2.0") < versions.key("0.2.1")


@pytest.mark.parametrize("last,level,want", [
    ("0.1.0", "major", "0.2.0"),     # 0.x 동안은 깨짐도 0.y 올림
    ("1.4.2", "major", "2.0.0"),
    ("1.4.2", "minor", "1.5.0"),
    ("1.4.2", "patch", "1.4.3"),
    ("0.1.0", "patch", "0.1.1"),
])
def test_versions_bump(last, level, want):
    assert versions.bump(last, level) == want


# ───────────────────────── 원장 칸(rc · due · masterplan)
def test_check_allows_rc_due_masterplan_and_rejects_bad_forms(repo):
    ok = {"releases": [rel("0.2.0-rc.1", due="2030-02-01", masterplan="v1.3")]}
    assert [e for e in release.check(ok, repo) if "CHANGELOG" not in e] == []
    bad = {"releases": [rel("0.2.0-beta", due="2월 초", masterplan="1.3")]}
    errs = "\n".join(release.check(bad, repo))
    assert "X.Y.Z" in errs and "due" in errs and "masterplan" in errs


def test_status_shows_due_and_masterplan(repo, capsys, monkeypatch):
    release.save({"releases": [rel("0.2.0", due="2030-02-01", masterplan="v1.3")]}, repo)
    monkeypatch.setattr(release, "ROOT", repo)
    assert release.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "목표일 2030-02-01" in out and "마스터플랜 v1.3" in out


# ───────────────────────── 번호 제안(release suggest)
def test_suggest_counts_commit_types_since_last_formal_tag(repo):
    git(repo, "tag", "-a", "v0.1.0", "-m", "첫 판본")
    commit(repo, "fix(ui): 고침")
    git(repo, "tag", "-a", "v0.2.0-rc.1", "-m", "사전 판본")      # rc 는 기준이 아니다
    commit(repo, "docs: 문서")
    s = release.suggest(repo)
    assert s["last"] == "v0.1.0" and s["level"] == "patch" and s["minimum"] == "0.1.1"
    commit(repo, "feat(gate): 새 검사")
    assert release.suggest(repo)["level"] == "minor"
    commit(repo, "refactor!: 명령 이름 바꿈")
    s = release.suggest(repo)
    assert s["level"] == "major" and s["minimum"] == "0.2.0"          # 0.x 면 깨짐도 MINOR 올림
    assert s["counts"]["feat"] == 1 and s["counts"]["fix"] == 1 and s["breaking"] == 1


def test_suggest_breaking_change_footer(repo):
    git(repo, "tag", "-a", "v1.0.0", "-m", "정식")
    commit(repo, "fix: 경로 정리", "BREAKING CHANGE: scripts/old.py 를 지웠다")
    s = release.suggest(repo)
    assert s["level"] == "major" and s["minimum"] == "2.0.0"


def test_suggest_without_tags_has_no_minimum(repo):
    s = release.suggest(repo)
    assert s["last"] == "" and s["minimum"] == ""


def test_ship_refuses_version_below_minimum_bump(repo):
    git(repo, "tag", "-a", "v0.1.0", "-m", "첫 판본")
    commit(repo, "feat: 새 기능")
    release.save({"releases": [rel("0.1.1")]}, repo)
    (repo / "docs/releases/v0.1.1.md").write_text(NOTES.format(v="0.1.1"), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs: 판본 준비")
    with pytest.raises(SystemExit, match="최소 0.2.0"):
        release.ship("0.1.1", repo)


# ───────────────────────── 노트의 '복제본이 받을 때'
def test_ship_refuses_clone_section_placeholder_or_missing(repo):
    release.save({"releases": [rel("0.1.0")]}, repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs: 판본 준비")
    notes = repo / "docs/releases/v0.1.0.md"
    notes.write_text(NOTES.format(v="0.1.0").replace("예상 충돌 없음 — upstream plan v0.1.0 뒤 apply", "(예상 충돌 · 올리는 법 — 채운다)"), encoding="utf-8")
    with pytest.raises(SystemExit, match="복제본이 받을 때"):
        release.ship("0.1.0", repo)
    notes.write_text("# v0.1.0\n## 되돌리기\n이전 태그로 재배포\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="복제본이 받을 때"):
        release.ship("0.1.0", repo)


def test_template_has_clone_section():
    t = (ROOT / "docs/releases/_template.md").read_text(encoding="utf-8")
    assert "## 복제본이 받을 때" in t and "## 되돌리기" in t


# ───────────────────────── 공개(release publish — 실행은 사람 확인 뒤, 테스트는 --dry)
def test_publish_dry_builds_gh_command(repo, capsys):
    release.save({"releases": [rel("0.1.0", status="shipped", tag="v0.1.0", shipped="2030-01-02"),
                               rel("0.2.0-rc.1", status="shipped", tag="v0.2.0-rc.1", shipped="2030-01-03")]}, repo)
    for v in ("0.1.0", "0.2.0-rc.1"):
        (repo / f"docs/releases/v{v}.md").write_text(NOTES.format(v=v), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore(release): 기록")
    git(repo, "tag", "-a", "v0.1.0", "-m", "x")
    git(repo, "tag", "-a", "v0.2.0-rc.1", "-m", "x")
    cmd = release.publish("0.1.0", repo, dry=True)
    assert cmd[:4] == ["gh", "release", "create", "v0.1.0"] and "--verify-tag" in cmd
    assert cmd[cmd.index("--notes-file") + 1] == "docs/releases/v0.1.0.md" and "--prerelease" not in cmd
    assert "release 브랜치" in capsys.readouterr().out                       # 공개하면 템플릿 = 최신 정식본으로 앞당겨진다
    assert "--prerelease" in release.publish("0.2.0-rc.1", repo, dry=True)


def test_publish_refuses_draft_or_missing_tag(repo):
    release.save({"releases": [rel("0.2.0"), rel("0.1.0", status="shipped", tag="v0.1.0")]}, repo)
    (repo / "docs/releases/v0.1.0.md").write_text(NOTES.format(v="0.1.0"), encoding="utf-8")
    with pytest.raises(SystemExit, match="shipped"):
        release.publish("0.2.0", repo, dry=True)
    with pytest.raises(SystemExit, match="태그 v0.1.0"):
        release.publish("0.1.0", repo, dry=True)


# ───────────────────────── CHANGELOG(생성물)
def test_changelog_generated_from_ledger_and_notes(repo):
    d = {"releases": [rel("0.1.0", status="shipped", tag="v0.1.0", shipped="2030-01-02", masterplan="v1.2"),
                      rel("0.2.0", due="2030-03-01", masterplan="v1.3")]}
    release.save(d, repo)
    (repo / "docs/releases/v0.1.0.md").write_text(NOTES.format(v="0.1.0"), encoding="utf-8")
    text = release.changelog(d, repo)
    assert text.index("## [Unreleased]") < text.index("## [0.1.0]")          # 맨 위 = 아직 내지 않은 판본
    assert "v0.2.0" in text.split("## [0.1.0]")[0] and "목표일 2030-03-01" in text
    part = text.split("## [0.1.0]")[1]
    assert "2030-01-02" in part and "- 새 명령 하나" in part and "마스터플랜 v1.2" in part
    assert "docs/releases/v0.1.0.md#되돌리기" in part                         # 판본마다 되돌리기 링크
    assert "- \n" not in text                                                # 빈 항목은 옮기지 않는다
    # release check 가 최신인지 본다 — 없거나 낡으면 실패
    assert any("CHANGELOG" in e for e in release.check(d, repo))
    (repo / "CHANGELOG.md").write_text(text, encoding="utf-8")
    assert release.check(d, repo) == []
    d["releases"][1]["goal"] = "목표가 바뀌었다"
    assert any("CHANGELOG" in e for e in release.check(d, repo))


def test_changelog_empty_ledger_for_new_project(repo):
    """새 프로젝트(빈 원장)에서도 생성 · 검사가 통한다."""
    text = release.changelog({"releases": []}, repo)
    assert "Unreleased" in text
    (repo / "CHANGELOG.md").write_text(text, encoding="utf-8")
    assert release.check({"releases": []}, repo) == []


def test_repo_changelog_is_current():
    assert not [e for e in release.check(release.load(ROOT), ROOT) if "CHANGELOG" in e]


# ───────────────────────── release 브랜치 앞당기기 워크플로
def test_release_branch_workflow_structure():
    wf = ROOT / ".github/workflows/release-branch.yml"
    doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))                                        # PyYAML 은 on 을 True 로 읽는다
    assert on["release"]["types"] == ["published"]
    job = next(iter(doc["jobs"].values()))
    assert "prerelease" in job["if"]                                         # 사전 판본은 앞당기지 않는다
    runs = "\n".join(s.get("run", "") for s in job["steps"])
    assert "--force" not in runs and " -f " not in runs and "+refs" not in runs   # 강제 푸시 금지
    assert "merge-base --is-ancestor" in runs                               # 앞당기기만 — 되감기면 실패
    assert "nova.project.json" in runs and "GITHUB_REPOSITORY" in runs      # 원천 저장소에서만(복제본 제외)
    assert doc["permissions"] == {"contents": "write"}


# ───────────────────────── 묶인 요구 상태 판정 — 꼬리 붙은 완료(REQ-261106-02-1)
def index_rows(r, rows):
    body = "".join(f"| [{q}](x.md) | 2030-01-01 | 제목 | {st} | - |\n" for q, st in rows)
    (r / "docs/requirement/requirement_index.md").write_text(
        "| ID | 일자 | 제목 | 상태 | 계획 |\n|---|---|---|---|---|\n" + body, encoding="utf-8")


def test_ship_accepts_tailed_done_status_but_refuses_open(repo):
    reqs = [("REQ-300101-01", "완료(종료 조건 충족 2030-01-01 · v0.1.0 대상)"), ("REQ-300101-02", "적용됨(상시 규칙)"),
            ("REQ-300101-03", "적용됨"), ("REQ-300101-04", "승인됨(v0.1.0 대상)"), ("REQ-300101-05", "진행 중"),
            ("REQ-300101-06", "구현 완료(E4 사람 확인 대기)")]
    index_rows(repo, reqs)
    release.save({"releases": [rel("0.1.0", reqs=[q for q, _ in reqs])]}, repo)
    (repo / "docs/releases/v0.1.0.md").write_text(NOTES.format(v="0.1.0"), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs: 판본 준비")
    with pytest.raises(SystemExit) as e:
        release.ship("0.1.0", repo)
    msg = str(e.value)
    for q in ("REQ-300101-01", "REQ-300101-02", "REQ-300101-03"):
        assert q not in msg                                                  # 머리말이 완료 · 적용됨이면 통과
    for q in ("REQ-300101-04", "REQ-300101-05", "REQ-300101-06"):
        assert q in msg                                                      # 승인됨 · 진행 중 · '구현 완료' 는 거부


# ───────────────────────── 체크포인트 · 되돌리기(REQ-261106-02-2 · -3)
TODAY = __import__("datetime").date(2030, 1, 2)


def events(r):
    p = r / release.CHECKPOINTS
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def test_checkpoint_tags_head_and_records_event(repo, capsys):
    head = git(repo, "rev-parse", "HEAD")
    tag = release.checkpoint("마이그레이션 직전", repo, today=TODAY)
    assert tag == "checkpoint/300102-01"
    assert git(repo, "rev-parse", f"{tag}^{{commit}}") == head                # 지점 = 체크포인트를 부른 순간의 HEAD
    assert git(repo, "cat-file", "-t", tag) == "tag"                          # 주석 태그
    ev = events(repo)
    assert len(ev) == 1 and ev[0]["event"] == "checkpoint" and ev[0]["tag"] == tag
    assert ev[0]["commit"] == head and ev[0]["reason"] == "마이그레이션 직전"
    assert git(repo, "status", "--porcelain") == ""                          # 원장 사건은 커밋까지 — 다음 명령을 막지 않는다
    assert "git push origin" in capsys.readouterr().out                     # 원격은 안내만
    assert release.checkpoint("두 번째", repo, today=TODAY) == "checkpoint/300102-02"   # 같은 날 순번


def test_checkpoint_refuses_dirty_tree_and_empty_reason(repo):
    (repo / "scripts").mkdir()
    (repo / "scripts/a.py").write_text("x = 1\n", encoding="utf-8")         # docs/releases 밖 · 추적 안 하는 파일도 막는다
    with pytest.raises(SystemExit, match="커밋하지 않은 변경"):
        release.checkpoint("사유", repo, today=TODAY)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat: a")
    with pytest.raises(SystemExit, match="사유"):
        release.checkpoint("  ", repo, today=TODAY)
    assert git(repo, "tag", "--list", "checkpoint/*") == ""


@pytest.fixture
def checkpointed(repo):
    """체크포인트 → 코드 수정 · 새 코드 파일 · 기록 문서 · 봉인 · 원장 변경 커밋."""
    (repo / "scripts").mkdir()
    (repo / "scripts/a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "docs/plans/archive").mkdir(parents=True)
    (repo / "docs/plans/archive/seals.json").write_text('{"v1.0": "aaa"}\n', encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat: 시작 코드")
    tag = release.checkpoint("큰 병합 직전", repo, today=TODAY)
    point = {p: (repo / p).read_bytes() for p in ("scripts/a.py", "nova.project.json")}
    (repo / "scripts/a.py").write_text("x = 2  # 잘못된 변경\n", encoding="utf-8")
    (repo / "scripts/new_mod.py").write_text("y = 1\n", encoding="utf-8")
    (repo / "docs/history").mkdir(parents=True)
    (repo / "docs/history/history_300102_01.md").write_text("# 이력 — 잘못된 변경을 기록\n", encoding="utf-8")
    (repo / "docs/plans/archive/seals.json").write_text('{"v1.0": "aaa", "v1.1": "bbb"}\n', encoding="utf-8")
    (repo / "registry").mkdir()
    (repo / "registry/naming.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat: 잘못된 변경")
    return repo, tag, point


def test_rollback_dry_shows_plan_and_changes_nothing(checkpointed, capsys):
    repo, tag, _ = checkpointed
    head = git(repo, "rev-parse", "HEAD")
    plan = release.rollback(tag, repo, yes=False, today=TODAY)
    out = capsys.readouterr().out
    assert git(repo, "rev-parse", "HEAD") == head and git(repo, "branch", "--list", "discarded/*") == ""
    assert plan["restore"] == ["scripts/a.py"] and plan["delete"] == ["scripts/new_mod.py"]
    assert "--yes" in out and "scripts/new_mod.py" in out
    assert "docs/history/history_300102_01.md" not in plan["restore"] + plan["delete"]
    assert any(p.startswith("docs/") for p in plan["kept"]) and "registry/naming.json" in plan["kept"]


def test_rollback_restores_code_only_and_keeps_records(checkpointed, capsys):
    repo, tag, point = checkpointed
    old_head = git(repo, "rev-parse", "HEAD")
    release.rollback(tag, repo, yes=True, today=TODAY)
    # 코드는 지점과 같다 · 새 코드 파일은 지워졌다
    assert (repo / "scripts/a.py").read_bytes() == point["scripts/a.py"]
    assert not (repo / "scripts/new_mod.py").exists()
    # 기록 · 봉인 · 원장은 그대로(이력은 앞으로만 간다)
    assert (repo / "docs/history/history_300102_01.md").exists()
    assert "v1.1" in (repo / "docs/plans/archive/seals.json").read_text(encoding="utf-8")
    assert (repo / "registry/naming.json").exists()
    # 폐기 브랜치가 옛 HEAD 를 가리킨다 · 되돌림은 새 커밋(옛 HEAD 의 자손)
    assert git(repo, "rev-parse", "discarded/300102-300102-01") == old_head
    assert git(repo, "rev-parse", "HEAD~1") == old_head
    assert git(repo, "status", "--porcelain") == ""
    ev = events(repo)
    assert [e["event"] for e in ev] == ["checkpoint", "rolled_back"]
    rb = ev[1]
    assert rb["tag"] == tag and rb["head_before"] == old_head and rb["discarded"] == "discarded/300102-300102-01"
    assert rb["restored"] == ["scripts/a.py"] and rb["deleted"] == ["scripts/new_mod.py"]
    out = capsys.readouterr().out
    assert "python nova.py gen" in out and "git push origin" in out and "--force" not in out


def test_rollback_refuses_dirty_unknown_tag_and_non_ancestor(checkpointed):
    repo, tag, _ = checkpointed
    with pytest.raises(SystemExit, match="태그"):
        release.rollback("checkpoint/000000-99", repo, yes=True, today=TODAY)
    (repo / "scripts/a.py").write_text("x = 3\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="커밋하지 않은 변경"):
        release.rollback(tag, repo, yes=True, today=TODAY)
    git(repo, "checkout", "-q", "--", "scripts/a.py")
    git(repo, "checkout", "-q", "-b", "side", f"{tag}~1")
    (repo / "z.txt").write_text("옆 갈래\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "chore: 옆")
    git(repo, "tag", "-a", "checkpoint/300102-09", "-m", "옆 지점")
    git(repo, "checkout", "-q", "main")
    with pytest.raises(SystemExit, match="조상"):
        release.rollback("checkpoint/300102-09", repo, yes=True, today=TODAY)


def test_record_paths_constant_covers_records():
    keep = release.RECORD_PATHS
    for p in ("docs/history/history_1.md", "docs/plans/archive/seals.json", "registry/naming.json",
              ".claude/state/x.json", "SOUL.md", "CHANGELOG.md", "nova.project.json"):
        assert release.is_record(p), p
    for p in ("scripts/release.py", "services/sample/sample/items.py", "nova.py", "web/apps/app/page.tsx",
              ".claude/commands/release.md", "newtop/mod.py"):
        assert not release.is_record(p), p                                    # 새 최상위 폴더도 코드로 친다
    assert all(isinstance(x, str) for x in keep)
