"""docs_new · docs_index · git_record 동작 검사 (docs 복사본에서)."""
import datetime as dt
import shutil
from pathlib import Path

import docs_index
import docs_new
import git_record
import pytest

ROOT = Path(__file__).resolve().parents[1]

NOW = dt.datetime(2030, 1, 2, 9, 0)


@pytest.fixture
def docs(tmp_path, monkeypatch):
    d = tmp_path / "docs"
    shutil.copytree(ROOT / "docs", d)
    for f in ROOT.glob("*.md"):  # 문서가 가리키는 루트 문서(CLAUDE.md · README.md)
        shutil.copy(f, tmp_path / f.name)
    monkeypatch.setattr(docs_new, "DOCS", d)
    monkeypatch.setattr(docs_index, "DOCS", d)
    monkeypatch.setattr(docs_index, "ROOT", tmp_path)
    return d


def test_repo_docs_are_consistent():
    assert docs_index.check() == []


def fill_intent(p):
    """새 요구의 '의도' 표 자리표시를 채운다 — 실제 작업에서 요구를 열 때 하는 일."""
    import re
    text = p.read_text(encoding="utf-8")
    text = re.sub(r"^\| (문제|결과|영향|제약|미해결) \| \(.*\) \|$", lambda m: f"| {m.group(1)} | 채움 |", text, flags=re.M)
    p.write_text(text, encoding="utf-8")
    return p


def fill_trace(p):
    """새 문서 머리 표의 사람 칸(원천 · 연결) 자리표시를 채운다 — 문서를 쓸 때 하는 일(REQ-261105-04)."""
    import re
    text = p.read_text(encoding="utf-8")
    text = re.sub(r"^\| (원천|연결) \| \(.*\) \|$", lambda m: f"| {m.group(1)} | 채움 |", text, flags=re.M)
    p.write_text(text, encoding="utf-8")
    return p


def test_new_docs_have_trace_rows(docs):
    """추적 칸 다섯 — 생성기가 문서 ID · 생성 · 위치를 채우고, 원천 · 연결은 사람 칸 자리표시로 둔다(REQ-261105-04-1 · 2)."""
    for kind in docs_new.DAILY:
        p = docs_new.new_daily(kind, "추적 시험", now=NOW)
        text = p.read_text(encoding="utf-8")
        rel = "docs/" + p.relative_to(docs).as_posix()
        assert f"| 위치 | `{rel}` |" in text, kind
        assert f"| 생성 | 2030-01-02 · `docs_new.py {kind}` |" in text, kind
        assert "| 문서 ID | " in text and "{{" not in text, kind
        assert "\n| 원천 | (" in text and "\n| 연결 | (" in text, kind
    h = (docs / "history" / "history_300102_01.md").read_text(encoding="utf-8")
    assert "| 문서 ID | history_300102_01 |" in h
    a = docs_new.new_adr("추적 결정", now=NOW).read_text(encoding="utf-8")
    assert "| 생성 | 2030-01-02 · `docs_new.py adr` |" in a and "| 원천 | (" in a
    fill_intent(docs / "requirement" / "requirement_300102_01.md")
    p = docs_new.new_plan("추적 계획", "REQ-300102-01", now=NOW)
    text = p.read_text(encoding="utf-8")
    assert f"| 위치 | `docs/plans/{p.name}` |" in text and "| 생성 | 2030-01-02 · `docs_new.py plan` |" in text
    assert "| 원천 | (" in text and "{{" not in text
    t = (docs / "plans" / "tasks" / f"tasks_{p.name.removeprefix('plan_')}").read_text(encoding="utf-8")
    assert f"`docs/plans/tasks/tasks_{p.name.removeprefix('plan_')}`" in t and "{{" not in t


def test_new_doc_trace_placeholder_fails(docs):
    """사람 칸(원천 · 연결)이 자리표시 그대로면 검사 실패 — 무엇을 채울지 한국어로 알린다(REQ-261105-04-3)."""
    p = docs_new.new_daily("history", "추적 검사", now=NOW)
    errs = docs_index.check()
    assert any("history_300102_01.md" in e and "'원천'" in e for e in errs), errs
    assert any("history_300102_01.md" in e and "'연결'" in e for e in errs), errs
    fill_trace(p)
    assert docs_index.check() == []
    text = p.read_text(encoding="utf-8").replace("| 연결 | 채움 |\n", "")   # 줄을 지워도 실패
    p.write_text(text, encoding="utf-8")
    assert any("'연결'" in e for e in docs_index.check())


def test_old_docs_trace_not_checked(docs):
    """261105 이전 문서 · ADR-012 이하 · plan_REQ_05 이하는 추적 칸을 검사하지 않는다(소급 없음)."""
    assert docs_index.trace_in_scope(Path("docs/history/history_261104_09.md")) is False
    assert docs_index.trace_in_scope(Path("docs/history/history_261105_01.md")) is True
    assert docs_index.trace_in_scope(Path("docs/adr/ADR-012-x.md")) is False
    assert docs_index.trace_in_scope(Path("docs/adr/ADR-013-x.md")) is True
    assert docs_index.trace_in_scope(Path("docs/plans/plan_REQ_05.md")) is False
    assert docs_index.trace_in_scope(Path("docs/plans/plan_REQ_06.md")) is True
    old = docs / "history" / "history_261101_99.md"
    old.write_text("# history_261101_99 · 옛 이력\n\n| 항목 | 내용 |\n|---|---|\n| 일자 | 2026-11-01 |\n", encoding="utf-8")
    idx = docs / "history" / "history_index.md"
    idx.write_text(idx.read_text(encoding="utf-8") + "| [history_261101_99](history_261101_99.md) | 2026-11-01 | 옛 | - |\n", encoding="utf-8")
    assert docs_index.check() == []


def test_req_numbering_and_index(docs):
    a = fill_trace(fill_intent(docs_new.new_daily("req", "첫 요구", now=NOW)))
    b = fill_trace(fill_intent(docs_new.new_daily("req", "둘째 요구", now=NOW)))
    assert a.name == "requirement_300102_01.md" and b.name == "requirement_300102_02.md"
    assert "# REQ-300102-02 · 둘째 요구" in b.read_text(encoding="utf-8")
    idx = (docs / "requirement" / "requirement_index.md").read_text(encoding="utf-8")
    assert "[REQ-300102-01](requirement_300102_01.md)" in idx
    assert docs_index.check() == []


def test_new_req_intent_must_be_filled(docs):
    """의도(INTENT) — 자리표시 그대로면 검사 실패, 채우면 통과(REQ-261104-08-6)."""
    p = docs_new.new_daily("req", "의도 시험", now=NOW)
    errs = docs_index.check()
    assert any("의도(INTENT)" in e and "'미해결'" in e for e in errs)
    fill_trace(fill_intent(p))
    assert docs_index.check() == []


def test_plan_creates_tasks_pair(docs):
    fill_trace(fill_intent(docs_new.new_daily("req", "요구", now=NOW)))
    p = fill_trace(docs_new.new_plan("새 계획", "REQ-300102-01", now=NOW))
    nn = p.stem.removeprefix("plan_REQ_")
    assert (docs / "plans" / "tasks" / f"tasks_REQ_{nn}.md").exists()
    text = p.read_text(encoding="utf-8")
    assert "{{" not in text and "requirement_300102_01.md" in text
    assert docs_index.check() == []


def test_plan_rejects_bad_req(docs):
    with pytest.raises(SystemExit):
        docs_new.new_plan("x", "REQ-1", now=NOW)


def test_session_updates_latest(docs):
    p = docs_new.new_daily("session", "요약 한 줄", now=NOW)
    assert (docs / "session" / "LATEST.md").read_text(encoding="utf-8") == p.read_text(encoding="utf-8")
    fill_trace(p)
    assert docs_index.check() == []


def test_adr_numbering_and_ascii_slug(docs):
    n = len(list((docs / "adr").glob("ADR-*.md")))
    p = fill_trace(docs_new.new_adr("메시지 브로커 선택", now=NOW))
    assert p.name == f"ADR-{n + 1:03d}-decision.md"
    q = fill_trace(docs_new.new_adr("메시지 브로커", slug="Message Broker", now=NOW))
    assert q.name == f"ADR-{n + 2:03d}-message-broker.md"
    assert docs_index.check() == []


def test_index_detects_missing_entry(docs):
    (docs / "history" / "history_300102_01.md").write_text("# x", encoding="utf-8")
    errs = docs_index.check()
    assert any("인덱스에 빠짐" in e for e in errs)


def test_git_web_url():
    assert git_record.web_url("git@github.com:o/r.git") == "https://github.com/o/r"
    assert git_record.web_url("https://github.com/o/r.git") == "https://github.com/o/r"
    assert git_record.web_url("https://tok@github.com/o/r") == "https://github.com/o/r"


def test_index_requires_korean(docs):
    (docs / "conventions" / "english.md").write_text("# English only", encoding="utf-8")
    assert any("한국어 아님" in e for e in docs_index.check())


def test_standards_require_decision(docs, monkeypatch, tmp_path):
    import json

    meta = json.loads((ROOT / "nova.project.json").read_text(encoding="utf-8"))
    meta["standards"].pop("STD-AX-001")
    (tmp_path / "nova.project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    errs = docs_index.check_standards()
    assert any("STD-AX-001" in e and "판정 없음" in e for e in errs)


def test_interview_numbering_and_index(docs):
    """고객 인터뷰 기록(REQ-261104-01-2) — INT-YYMMDD-NN, 인덱스 한 줄, 빠지면 검사 실패."""
    p = docs_new.new_daily("interview", "매장 예약 인터뷰", now=NOW)
    assert p == docs / "requirement" / "interviews" / "interview_300102_01.md"
    text = p.read_text(encoding="utf-8")
    assert "# INT-300102-01 · 매장 예약 인터뷰" in text and "{{" not in text.replace("{{ID}}", "")
    idx = docs / "requirement" / "interviews" / "interview_index.md"
    assert "[INT-300102-01](interview_300102_01.md)" in idx.read_text(encoding="utf-8")
    fill_trace(p)
    assert docs_index.check() == []
    (p.parent / "interview_300102_02.md").write_text("# 빠진 인터뷰\n", encoding="utf-8")
    assert any("interview_300102_02.md" in e for e in docs_index.check())


def test_superpowers_wiring():
    """Superpowers 연동(REQ-261104-01) — 저장소 설정 · 명령 · 규약이 서로 맞물린다."""
    import json
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"]["superpowers@claude-plugins-official"] is True
    cmds = ROOT / ".claude" / "commands"
    for name in ("req-interview", "req-analyze", "task-run", "review-request", "debug", "finish"):
        assert (cmds / f"{name}.md").exists(), name
    conv = (ROOT / "docs" / "conventions" / "superpowers.md").read_text(encoding="utf-8")
    skills = ["using-superpowers", "brainstorming", "writing-plans", "using-git-worktrees", "subagent-driven-development",
              "executing-plans", "test-driven-development", "dispatching-parallel-agents", "systematic-debugging",
              "requesting-code-review", "receiving-code-review", "verification-before-completion",
              "finishing-a-development-branch", "writing-skills", "diagnosing-superpowers"]
    assert [s for s in skills if f"`{s}`" not in conv] == []  # 15종 모두 지도에 있다
    assert ".superpowers/" in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert not (ROOT / "docs" / "superpowers").exists()  # Nova 위치를 쓴다(ADR-005)


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_git_record_help_writes_nothing(docs, monkeypatch, flag, capsys):
    """회귀 — git_record.py --help 가 '--help' 를 요약으로 받아 docs/git 기록을 만들던 결함."""
    gdir = docs / "git"
    monkeypatch.setattr(git_record, "GIT_DIR", gdir)
    monkeypatch.setattr(git_record, "git", lambda *a: pytest.fail(f"--help 에서 git 을 부르면 안 된다: {a}"))
    before = sorted(p.name for p in gdir.iterdir())
    idx = (gdir / "git_index.md").read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        git_record.main([flag])
    assert e.value.code == 0 and "요약" in capsys.readouterr().out
    assert sorted(p.name for p in gdir.iterdir()) == before
    assert (gdir / "git_index.md").read_text(encoding="utf-8") == idx


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_ledgers_help_writes_nothing(monkeypatch, flag, capsys):
    """회귀 — ledgers.py --help 가 도움말을 무시하고 대장을 다시 만들던 결함."""
    import ledgers
    monkeypatch.setattr(ledgers, "write", lambda *a: pytest.fail("--help 에서 쓰면 안 된다"))
    monkeypatch.setattr(ledgers, "build", lambda: pytest.fail("--help 에서 대장을 만들면 안 된다"))
    with pytest.raises(SystemExit) as e:
        ledgers.cli([flag])
    assert e.value.code == 0 and "--check" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        ledgers.cli(["--모르는인자"])                                                  # 모르는 인자도 쓰기 전에 거절
    assert "raise SystemExit(cli())" in (ROOT / "scripts" / "ledgers.py").read_text(encoding="utf-8")


def test_doc_paths_exist():
    """명령 · 규약 문서가 가리키는 파일이 실제로 있다(예전: services/gateway/rbac.json — 실제는 gateway/gateway/ 아래)."""
    import re
    srcs = [".claude/commands/foundation.md", ".claude/commands/spec.md", "scripts/warehouse.py", "docs/conventions/ui.md",
            "docs/conventions/ux-heuristics.md", "docs/std/STD-DOMAIN-PACK-001.md", "docs/plans/tasks/tasks_REQ_01.md"]
    rx = re.compile(r"services/[\w\-./]+\.json|docs/conventions/[\w\-]+\.md")   # 저장소에 늘 있어야 하는 것만(프로젝트 산출물 경로 제외)
    srcs = [s for s in srcs if (ROOT / s).exists()]                               # 새 프로젝트에는 플랫폼 task 문서가 없다
    missing = [f"{s}: {m}" for s in srcs for m in rx.findall((ROOT / s).read_text(encoding="utf-8"))
               if "<" not in m and not (ROOT / m).exists()]
    assert missing == []
    tasks = ROOT / "docs/plans/tasks/tasks_REQ_01.md"
    assert not tasks.exists() or "new_pack.py" not in tasks.read_text(encoding="utf-8")


def test_ui_paginate_signature_matches_code():
    """ui.md 의 paginate 서명이 nova_common.paging 실제 서명과 같다."""
    import inspect
    from nova_common import paging
    params = list(inspect.signature(paging.paginate).parameters.values())
    kw = [p.name for p in params if p.kind is p.KEYWORD_ONLY]
    pos = [p.name for p in params if p.kind is not p.KEYWORD_ONLY]
    sig = f"paginate({', '.join(pos)}, *, {', '.join(kw)})"
    assert sig in (ROOT / "docs/conventions/ui.md").read_text(encoding="utf-8"), sig


def test_git_record_default_range_and_secret_warning(tmp_path, monkeypatch, capsys):
    """범위를 안 주면 'git 인덱스 마지막 행이 가리키는 기록의 마지막 커밋..HEAD' — 여러 커밋을 한 번에 푸시해도 빠지지 않게.
    기록을 못 찾으면 예전대로 HEAD~1..HEAD. 범위 안에 .env · *.key · *.pem · id_rsa 가 있으면 경고."""
    import subprocess

    def g(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    g("init", "-q", "-b", "main")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    shas = []
    for i, name in enumerate(["a.txt", "b.txt", "server.pem"]):
        (tmp_path / name).write_text(f"{i}\n", encoding="utf-8")
        g("add", "-A")
        g("commit", "-q", "-m", f"c{i}")
        shas.append(g("rev-parse", "--short", "HEAD"))
    gdir = tmp_path / "docs" / "git"
    gdir.mkdir(parents=True)
    head = "# git 기록\n\n| 기록 | 일자 | 커밋 | 요약 |\n|---|---|---|---|\n"
    (gdir / "git_index.md").write_text(head, encoding="utf-8")
    monkeypatch.setattr(git_record, "ROOT", tmp_path)
    monkeypatch.setattr(git_record, "GIT_DIR", gdir)
    assert git_record.default_range(gdir) == "HEAD~1..HEAD"                             # 기록이 없다 — 예전 기본
    (gdir / "git_300101_01.md").write_text(f"# git_300101_01 · 첫\n\n## 커밋\n- `{shas[0]}` c0\n\n## 변경 파일 통계\n", encoding="utf-8")
    (gdir / "git_index.md").write_text(head + f"| [git_300101_01](git_300101_01.md) | 2030-01-01 | `{shas[0]}` | 첫 |\n", encoding="utf-8")
    assert git_record.default_range(gdir) == f"{shas[0]}..HEAD"
    assert git_record.main(["둘째 기록"]) == 0
    out = capsys.readouterr().out
    assert "server.pem" in out and "경고" in out
    rec = next(p for p in gdir.glob("git_*_*.md") if p.name != "git_300101_01.md").read_text(encoding="utf-8")
    assert f"`{shas[1]}`" in rec and f"`{shas[2]}`" in rec and f"`{shas[0]}`" not in rec   # 지난 기록 뒤 커밋 둘 다
    # 추적 칸(REQ-261105-04) — 생성기가 다섯 칸 모두 채운다(원천 = 커밋 범위, 연결 = 범위 안 이력)
    assert f"| 원천 | 커밋 범위 `{shas[0]}..HEAD` |" in rec and "| 생성 | " in rec and "`git_record.py`" in rec
    assert "| 연결 | 없음 — " in rec and "| 위치 | `docs/git/git_" in rec and "| 문서 ID | git_" in rec
    (gdir / "git_300101_01.md").write_text("# 해시 없음\n", encoding="utf-8")
    (gdir / "git_index.md").write_text(head + "| [git_300101_01](git_300101_01.md) | 2030-01-01 | `-` | 첫 |\n", encoding="utf-8")
    assert git_record.default_range(gdir) == "HEAD~1..HEAD"


def test_docs_link_into_claude_is_rejected(docs):
    """docs → .claude 마크다운 링크는 저장소 안에서 실재해도 금지 — docs 만 복사한 곳에서 깨진다(두 번 겪은 함정)."""
    claude = docs.parent / ".claude" / "agents"
    claude.mkdir(parents=True)
    (claude / "README.md").write_text("# 에이전트\n", encoding="utf-8")
    g = docs / "conventions" / "glossary.md"
    g.write_text(g.read_text(encoding="utf-8") + "\n[편제](../../.claude/agents/README.md)\n", encoding="utf-8")
    assert any("docs → .claude 링크 금지" in e for e in docs_index.check())
