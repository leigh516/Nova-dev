"""진척 보기(scripts/progress.py) — 계획 ↔ 인덱스 ↔ task 수 · 요구 상태와 task 의 모순 · 릴리스 초안 형식을 따로 센다."""
import importlib.util
import json
from pathlib import Path

import pytest

import progress

ROOT = Path(__file__).resolve().parents[1]

REQ_IDX = """# 요구사항 인덱스

| ID | 일자 | 제목 | 상태 | 계획 |
|---|---|---|---|---|
| [REQ-300101-01](requirement_300101_01.md) | 2030-01-01 | 하나 | 완료 | [plan_REQ_01](../plans/plan_REQ_01.md) |
| [REQ-300101-02](requirement_300101_02.md) | 2030-01-01 | 둘 | 진행 중 | [plan_REQ_02](../plans/plan_REQ_02.md) |
| [REQ-300101-03](requirement_300101_03.md) | 2030-01-01 | 셋 | 진행 중 | [plan_REQ_03](../plans/plan_REQ_03.md) |
| [REQ-300101-04](requirement_300101_04.md) | 2030-01-01 | 넷 | 적용됨(상시 규칙) | [ux](../conventions/ux.md) |
| [REQ-300101-05](requirement_300101_05.md) | 2030-01-01 | 다섯 | 완료 | [plan_REQ_03](../plans/plan_REQ_03.md) 1단계 |
"""


def make(root: Path, *, master_plans=("01", "02", "03"), index_plans=("01", "02", "03", "04")) -> Path:
    plans = root / "docs/plans"
    (plans / "tasks").mkdir(parents=True)
    rows = "".join(f"| {i} | [plan_REQ_{n}](plan_REQ_{n}.md) | 내용 | - | REQ |\n" for i, n in enumerate(master_plans, 1))
    (plans / "master_plan.md").write_text(f"# 마스터플랜\n\n## 5. 세부 계획\n| 순서 | 계획 | 내용 | 선행 | 요구 |\n|---|---|---|---|---|\n{rows}\n## 6. 원칙\n",
                                          encoding="utf-8")
    rows = "".join(f"| [plan_REQ_{n}](plan_REQ_{n}.md) | 제목 | REQ | v1.0 | 진행 중 |\n" for n in index_plans)
    (plans / "plan_index.md").write_text(f"# 세부 계획 목록\n\n| 계획 | 제목 | 요구 | 버전 | 상태 |\n|---|---|---|---|---|\n{rows}", encoding="utf-8")
    # 01: 완료 요구인데 미완 task 하나(모순) · 02: 진행 중인데 모두 끝(반대 모순) · 03: 진행 중 · 미완(정상)
    (plans / "tasks/tasks_REQ_01.md").write_text("- [x] T01-1.01 가\n- [ ] T01-1.02 나\n", encoding="utf-8")
    (plans / "tasks/tasks_REQ_02.md").write_text("- [x] T02-1.01 가\n- [x] T02-1.02 나 🆕\n", encoding="utf-8")
    (plans / "tasks/tasks_REQ_03.md").write_text("## 1단계 · 기반\n- [x] T03-1.01 가\n## 2단계 · 화면\n- [ ] T03-2.01 나\n- [ ] ~~T03-2.02 다~~ — 취소\n",
                                                 encoding="utf-8")
    (root / "docs/requirement").mkdir(parents=True)
    (root / "docs/requirement/requirement_index.md").write_text(REQ_IDX, encoding="utf-8")
    (root / "docs/releases").mkdir(parents=True)
    rel = {"releases": [{"version": "0.1.0", "status": "draft", "goal": "첫 판본", "reqs": ["REQ-300101-01", "REQ-300101-02"],
                         "not_doing": ["결제"],
                         "exit": [{"id": "E1", "check": "python nova.py test", "expect": "통과", "how": "명령", "judged": ""},
                                  {"id": "E2", "check": "남은 결함을 전부 찾는다", "expect": "없음", "how": "사람", "judged": ""}],
                         "drafted": "2030-01-01", "shipped": "", "tag": ""}]}
    (root / "docs/releases/releases.json").write_text(json.dumps(rel, ensure_ascii=False), encoding="utf-8")
    return root


@pytest.mark.parametrize("status,done,finished", [
    ("완료", True, True), ("완료(종료 조건 충족 2026-11-04 · v0.2.0 대상)", True, True),
    ("적용됨(상시 규칙)", True, True), ("적용됨", True, True),
    ("승인됨", False, False), ("승인됨(v0.2.0 대상)", False, False), ("진행 중", False, False),
    ("구현 완료(E4 사람 확인 대기)", False, False), ("적용됨 · E3 확인 대기", False, False), ("완료됨", False, False),
    ("보류", False, True), ("취소(중복)", False, True), ("없음", False, False),
])
def test_status_head_judgement(status, done, finished):
    """머리말이 완료 · 적용됨이면 끝남 — 꼬리 '(…)' 는 설명이다(REQ-261106-02-1). 꼬리 없이 다른 말이 이어지면 아직이다."""
    assert progress.is_done(status) is done
    assert progress.is_finished(status) is finished


def test_three_axes_separately(tmp_path):
    d = progress.collect(make(tmp_path))
    p = d["plans"]
    assert p["master"] == ["plan_REQ_01", "plan_REQ_02", "plan_REQ_03"]
    assert "plan_REQ_04" in p["index_only"] and "plan_REQ_04" in p["no_tasks"]      # 인덱스엔 있는데 마스터플랜 · task 가 없다
    t = {r["plan"]: r for r in p["tasks"]}
    assert (t["plan_REQ_01"]["done"], t["plan_REQ_01"]["open"]) == (1, 1)
    assert (t["plan_REQ_03"]["done"], t["plan_REQ_03"]["open"], t["plan_REQ_03"]["cancelled"]) == (1, 1, 1)  # 취소는 미완으로 세지 않는다
    bad = {(c["req"], c["kind"]) for c in d["reqs"]["conflicts"]}
    assert t["plan_REQ_03"]["stages"]["1"]["open"] == 0                            # REQ-05 는 1단계만 — 2단계 미완은 그 요구의 것이 아니다
    assert bad == {("REQ-300101-01", "완료인데 미완 task"), ("REQ-300101-02", "task 는 모두 끝났는데 요구가 열려 있다")}
    r = d["releases"]["drafts"][0]
    assert r["version"] == "0.1.0" and r["reqs"] == {"REQ-300101-01": "완료", "REQ-300101-02": "진행 중"}
    assert any("소진형" in e for e in r["errors"])


def test_check_exits_only_on_req_conflict(tmp_path, capsys):
    root = make(tmp_path)
    assert progress.main(["--root", str(root)]) == 0                 # 정보용 — 모순이 있어도 기본은 0
    out = capsys.readouterr().out
    assert "① 계획" in out and "② 요구" in out and "③ 릴리스" in out and "평균" not in out
    assert progress.main(["--root", str(root), "--check"]) == 1
    (root / "docs/plans/tasks/tasks_REQ_01.md").write_text("- [x] 가\n", encoding="utf-8")
    (root / "docs/plans/tasks/tasks_REQ_02.md").write_text("- [ ] 나\n", encoding="utf-8")
    assert progress.main(["--root", str(root), "--check"]) == 0


def test_repo_progress_runs():
    d = progress.collect(ROOT)
    # 새 프로젝트(계획이 아직 없음)에서도 같은 테스트가 돈다 — 모양만 본다
    assert "master" in d["plans"] and "conflicts" in d["reqs"]


def nova_cli():
    spec = importlib.util.spec_from_file_location("nova_cli", ROOT / "nova.py")
    nova = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nova)
    return nova


def test_nova_commands_wired():
    nova = nova_cli()
    for c in ("check", "progress", "upstream", "worktree-sync", "issue", "impact", "learn"):
        assert c in nova.COMMANDS and c in nova.__doc__, c


def test_check_summary_and_order(monkeypatch, capsys):
    """check — test · lint 를 함께 돌리고, 통과한 테스트는 요약 줄만, 실패한 축 이름과 종료 1."""
    nova = nova_cli()
    monkeypatch.setattr(nova, "ensure_env", lambda: None)
    long = "\n".join(f"tests/test_{i}.py ....." for i in range(50))
    outs = {"test": (0, long + "\n120 passed in 3.2s\n\n✓ test 통과\n"), "lint": (1, "✗ docs_index 실패\n")}
    monkeypatch.setattr(nova, "run_both", lambda cmds: [(name, *outs[name]) for name, _ in cmds])
    with pytest.raises(SystemExit) as e:
        nova.cmd_check([])
    out = capsys.readouterr().out
    assert e.value.code == 1 and "test_7.py" not in out and "120 passed" in out
    assert out.index("■ test") < out.index("■ lint") and "docs_index 실패" in out and "실패: lint" in out
    outs["test"] = (1, long + "\n1 failed\n")
    outs["lint"] = (0, "✓ lint 통과\n")
    with pytest.raises(SystemExit):
        nova.cmd_check([])
    out = capsys.readouterr().out
    assert "test_7.py" in out and "실패: test" in out                 # 실패하면 전문
