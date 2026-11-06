"""task 묶음 판정(task_batch) — tasks 문서를 읽어 겹치지 않는 다음 묶음을 고른다(읽기 전용)."""
import subprocess
import sys
from pathlib import Path

import pytest

import task_batch
from task_batch import next_batch, overlaps, parse_tasks, pending_ids, task_paths

ROOT = Path(__file__).resolve().parent.parent

DOC = """# tasks

## 1단계 · 첫째
- [x] T01-1.01 끝난 일 `a/x.py`
- [ ] T01-1.02 열린 일 `a/y.py`
  - 파일: 고치기 `a/y.py` · 테스트 `tests/test_y.py`
  - [ ] 실패 테스트 → 실패 확인
- ~~[ ] T01-1.03~~ 취소 — 이유
- [ ] ~~T01-1.04~~ 취소 `a/z.py`
- [ ] 🆕 T01-1.05 발견한 일 `b/`

## 2단계 · 둘째
- [ ] T01-2.01 다음 단계 `c/x.py`

## 작업 중 발견
- [ ] 🆕 T01-9.01 단계 밖 `d/x.py`
"""


def _t(tid, body, state="open", stage=1):
    return task_batch.Task(id=tid, state=state, body=body, stage=stage)


def test_parse_tasks_states():
    ts = {t.id: t for t in parse_tasks(DOC)}
    assert list(ts) == ["T01-1.01", "T01-1.02", "T01-1.03", "T01-1.04", "T01-1.05", "T01-2.01", "T01-9.01"]
    assert ts["T01-1.01"].state == "done"
    assert ts["T01-1.02"].state == "open"
    assert ts["T01-1.03"].state == "cancelled"
    assert ts["T01-1.04"].state == "cancelled"
    assert ts["T01-1.05"].state == "open"          # 🆕 줄도 같은 task
    assert ts["T01-1.02"].stage == 1 and ts["T01-2.01"].stage == 2
    assert ts["T01-9.01"].stage is None            # 단계 밖 절
    # 하위 줄은 본문에 붙고 task 로 세지 않으며, 하위 체크박스가 상태를 바꾸지 않는다
    assert "tests/test_y.py" in ts["T01-1.02"].body
    assert "실패 테스트" in ts["T01-1.02"].body
    assert len(ts) == 7


def test_task_paths_extracts_and_empty():
    ts = {t.id: t for t in parse_tasks(DOC)}
    assert task_paths(ts["T01-1.02"]) == ["a/y.py", "tests/test_y.py"]
    assert task_paths(ts["T01-1.05"]) == ["b/"]
    assert task_paths(_t("T01-1.09", "경로 없는 일")) == []
    # 괄호 안 테스트 경로 · ::이름 제거 · 역슬래시 통일
    body = "만들기 (`tests/test_q.py::test_a` — 설명) `scripts\\q.py`"
    assert task_paths(_t("T01-1.10", body)) == ["tests/test_q.py", "scripts/q.py"]


def test_overlaps_same_dir_prefix_and_disjoint():
    assert overlaps(["a/b.py"], ["a/b.py"])
    assert overlaps(["a/b/"], ["a/b/c.py"])        # 폴더 포함
    assert overlaps(["a/b/c.py"], ["a/b"])
    assert not overlaps(["a/b.py"], ["a/bc.py"])   # 이름 앞부분만 같은 것은 겹침 아님
    assert not overlaps(["a/x.py"], ["b/y.py", "c/"])
    assert overlaps([], ["a/x.py"])                # 경로 없는 task 는 모두와 겹침
    assert overlaps(["a/x.py"], [])
    assert overlaps([], [])


def test_next_batch_prerequisite_stage_gate_and_max():
    tasks = parse_tasks(DOC)
    # 1단계 열린 것 중 겹치지 않는 둘(1.02 · 1.05) — 2단계 · 단계 밖은 관문 전이라 제외
    assert next_batch(tasks, max_parallel=5) == ["T01-1.02", "T01-1.05"]
    assert next_batch(tasks, max_parallel=1) == ["T01-1.02"]
    with pytest.raises(ValueError):
        next_batch(tasks, max_parallel=0)

    # 선행이 미완이면 제외, 끝나면 포함
    blocked = [
        _t("T02-1.01", "먼저 `a/a.py`"),
        _t("T02-1.02", "(선행: T02-1.01) `b/b.py`"),
        _t("T02-1.03", "`c/c.py`"),
    ]
    assert next_batch(blocked, 5) == ["T02-1.01", "T02-1.03"]
    blocked[0] = _t("T02-1.01", "먼저 `a/a.py`", state="done")
    assert next_batch(blocked, 5) == ["T02-1.02", "T02-1.03"]

    # 경로 없는 task 는 혼자 한 묶음, 겹치면 뒤로 미룬다
    mixed = [_t("T03-1.01", "`a/`"), _t("T03-1.02", "`a/x.py`"), _t("T03-1.03", "경로 없음"), _t("T03-1.04", "`z.py`")]
    assert next_batch(mixed, 5) == ["T03-1.01", "T03-1.04"]
    assert next_batch([_t("T03-1.05", "경로 없음"), _t("T03-1.06", "`z.py`")], 5) == ["T03-1.05"]

    # 앞 단계가 끝나면 다음 단계, 그다음에 단계 밖 task
    done1 = [_t("T04-1.01", "`a.py`", state="done"), _t("T04-2.01", "`b.py`", stage=2), _t("T04-9.01", "`c.py`", stage=None)]
    assert next_batch(done1, 5) == ["T04-2.01"]
    done2 = [_t("T04-2.01", "`b.py`", state="cancelled", stage=2), _t("T04-9.01", "`c.py`", stage=None)]
    assert next_batch(done2, 5) == ["T04-9.01"]


def test_pending_ids_skips_done_and_cancelled():
    tasks = parse_tasks(DOC)
    assert pending_ids(tasks) == ["T01-1.02", "T01-1.05", "T01-2.01", "T01-9.01"]
    # 같은 입력에서 next_batch 는 pending 의 순서 있는 부분 집합
    batch = next_batch(tasks, 10)
    assert [i for i in pending_ids(tasks) if i in batch] == batch


def test_cli_skip_excludes_ids(tmp_path):
    """--skip 은 사람 판단 대기 task 를 묶음에서 뺀다 — 남은 것이 없으면 '막힘'(2)이 아니라 '대기'(4)."""
    f = tmp_path / "tasks.md"
    f.write_text(DOC, encoding="utf-8")
    run = lambda *a: subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "task_batch.py"), *a],
        capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL,
    )
    r = run(str(f), "--max", "2", "--skip", "T01-1.02")
    assert r.returncode == 0, r.stderr
    assert "T01-1.02" not in r.stdout and "T01-1.05" in r.stdout
    # 제외했어도 단계 관문은 유지 — 2단계 task 가 앞당겨지지 않는다
    assert "T01-2.01" not in r.stdout

    r = run(str(f), "--max", "2", "--skip", "T01-1.02,T01-1.05")
    assert r.returncode == 4 and "대기" in r.stdout

    # 제외 없이도 막힌 경우(선행 미완)는 계속 '막힘'(2)
    g = tmp_path / "blocked.md"
    g.write_text("## 1단계 · 막힘\n- [ ] T02-1.01 (선행: T02-9.99) `a.py`\n- [ ] T02-9.99 (선행: T02-1.01) `b.py`\n", encoding="utf-8")
    r = run(str(g), "--max", "2", "--skip", "T02-9.99")
    assert r.returncode == 2


def test_cli_skip_warns_unknown_id(tmp_path):
    """--skip 에 열린 task 가 아닌 ID(오타 · 이미 끝남)가 있으면 조용히 무시하지 않고 stderr 로 알린다."""
    f = tmp_path / "tasks.md"
    f.write_text(DOC, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "task_batch.py"), str(f), "--max", "2", "--skip", "T01-1.02,T99-9.99"],
        capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL,
    )
    assert r.returncode == 0, r.stderr
    assert "T99-9.99" in r.stderr and "T01-1.02" not in r.stderr


def test_cli_prints_batch_and_done(tmp_path):
    f = tmp_path / "tasks.md"
    f.write_text(DOC, encoding="utf-8")
    run = lambda *a: subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "task_batch.py"), *a],
        capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL,
    )
    r = run(str(f), "--max", "2")
    assert r.returncode == 0, r.stderr
    assert "다음 묶음 2개: T01-1.02 · T01-1.05" in r.stdout
    assert "남은 열린 task 4개" in r.stdout

    g = tmp_path / "done.md"
    g.write_text("## 1단계 · 끝\n- [x] T05-1.01 끝 `a.py`\n", encoding="utf-8")
    r = run(str(g), "--max", "2")
    assert r.returncode == 0 and "끝 — 열린 task 없음" in r.stdout

    r = run(str(tmp_path / "없음.md"), "--max", "2")
    assert r.returncode == 1 and r.stderr.strip()


# ---- 고치기 1회차: 글롭 · 부분 추출 · 모양 이상 · 종료 코드 -------------------------------------
def test_overlaps_glob_means_folder_prefix():
    assert overlaps(["scripts/*.py"], ["scripts/task_batch.py"])
    assert overlaps(["scripts/task_batch.py"], ["scripts/*.py"])
    assert overlaps(["src/**/x.py"], ["src/a/y.py"])
    assert overlaps(["*.py"], ["a/b.py"])               # 글롭 앞 폴더가 없으면 전체와 겹침
    assert overlaps(["a/[xy].py"], ["a/z.py"])
    assert not overlaps(["a/*.py"], ["b/x.py"])


def test_task_paths_robust_tokens_and_uncertain():
    body = "파일: 고치기 `a/b.py`(신규) · c/d.py; e/f.py:12 · src/{x,y}.py · g/h.py를\n  - 테스트 docs/plans/x.md 와 web/ 를 본다"
    t = _t("T06-1.01", body)
    assert task_paths(t) == ["a/b.py", "c/d.py", "e/f.py", "src/x.py", "src/y.py", "g/h.py", "docs/plans/x.md", "web/"]
    assert not task_batch.paths_uncertain(t)
    # 실제 tasks 에 있는 모양은 불확실로 치지 않는다
    real = _t("T06-1.02", "x\n  - 파일: 고치기 `models.py` · `items.py`(record_activity) · 테스트 `test_items.py`")
    assert task_paths(real) == ["models.py", "items.py", "test_items.py"] and not task_batch.paths_uncertain(real)
    # `파일:` 줄에 경로로 해석 못 한 조각이 남으면 불확실 → 혼자 한 묶음
    odd = _t("T06-1.03", "x\n  - 파일: 고치기 mystuff `a/b.py`")
    assert task_batch.paths_uncertain(odd)
    assert next_batch([odd, _t("T06-1.04", "`z.py`")], 5) == ["T06-1.03"]
    assert next_batch([_t("T06-1.04", "`z.py`"), odd], 5) == ["T06-1.04"]


def test_parse_anomalies_and_cli_exit_codes(tmp_path):
    bad = "## 1단계 · x\n- [ ] **T07-1.01** 굵은 ID\n- [ ] [T07-1.02] 대괄호\n- [~] T07-1.03 이상한 상태\n- [ ] T07-1.04 정상 `a.py`\n  - [ ] 하위 체크박스는 본문\n"
    tasks, anomalies = task_batch.parse_tasks_checked(bad)
    assert [t.id for t in tasks] == ["T07-1.04"]
    assert [n for n, _ in anomalies] == [2, 3, 4]
    run = lambda *a: subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "task_batch.py"), *a],
        capture_output=True, text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL,
    )
    f = tmp_path / "bad.md"
    f.write_text(bad, encoding="utf-8")
    r = run(str(f), "--max", "2")
    assert r.returncode == 3 and "2" in r.stderr and "형식" in r.stderr

    blocked = tmp_path / "blocked.md"
    blocked.write_text("## 1단계 · x\n- [ ] T08-1.01 첫째 (선행: T08-1.02) `a.py`\n- [ ] T08-1.02 둘째 (선행: T08-1.01) `b.py`\n", encoding="utf-8")
    r = run(str(blocked), "--max", "2")
    assert r.returncode == 2 and "막힘" in r.stdout

    unk = tmp_path / "unk.md"
    unk.write_text("## 1단계 · x\n- [ ] T09-1.01 일 (선행: T99-1.01) `a.py`\n", encoding="utf-8")
    r = run(str(unk), "--max", "2")
    assert r.returncode == 0 and "T99-1.01" in r.stderr and "T09-1.01" in r.stdout

    assert run(str(unk), "--max", "0").returncode == 1


# ── 단일 원천 지키기 (T08-4.06 · 4.07) ──────────────────────────────

import json
import re


def _limit_names(task_run_text):
    """task-run 의 '안전장치' 표에서 상한 항목 이름(첫 칸)을 읽는다 — 하드코딩하지 않는다."""
    names, inside = [], False
    for line in task_run_text.splitlines():
        if line.startswith("### 안전장치"):
            inside = True
            continue
        if inside and line.startswith("#"):
            break
        if inside and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and re.search(r"\d", cells[1]):
                names.append(cells[0])
    return names


def _limit_leaks(root):
    """상한 이름과 숫자가 같은 줄에 나오는 다른 문서의 (파일, 줄 번호) 목록."""
    task_run = root / ".claude" / "commands" / "task-run.md"
    names = _limit_names(task_run.read_text(encoding="utf-8"))
    targets = [p for p in (root / ".claude" / "commands").glob("*.md") if p.name != "task-run.md"]
    targets += list((root / "docs" / "conventions").glob("*.md"))
    readme = root / ".claude" / "agents" / "README.md"
    if readme.exists():
        targets.append(readme)
    heads = [_head(nm) for nm in names]
    leaks = []
    for p in targets:
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if any(_near_digit(line, h) for h in heads):
                leaks.append((p.name, n))
    return names, leaks


def _head(name):
    """항목 이름의 머리말 — 영문 · 조사 붙은 낱말 · 일반어('수' · '회차')를 빼고 남은 끝 두 낱말.
    한 낱말('호출' · '실패')만 쓰면 무관한 문장('실패 3회 → dlq')이 걸려 두 낱말로 좁힌다."""
    keep = [w for w in name.replace("`", " ").split()
            if len(w) >= 2 and not re.search(r"[A-Za-z-]", w) and not w.endswith(("당", "의")) and w not in ("수", "회차")]
    return " ".join(keep[-2:]) if keep else name


# 개수로 읽히는 숫자 — 앞이 글자 · § · 점이 아니고, 뒤가 단위(회차 · 회 · 번 …)이거나 홀로 선 숫자
_COUNT = r"(?<![\w§.\-])\d+(?:(?:회차|회|번|개|건|명|차)|(?![\w.\-]))"


def _near_digit(line, head):
    """같은 줄에서 머리말과 개수 숫자가 12자 안에 붙어 있는가(줄여 쓴 누출 포함)."""
    h = r"\s+".join(re.escape(w) for w in head.split())
    return bool(re.search(rf"{h}.{{0,12}}{_COUNT}|{_COUNT}.{{0,12}}{h}", line))


def _blanket_allows(settings):
    """접두 일괄 허용 · push · tag · 릴리스 허용으로 보이는 allow 항목."""
    bad = []
    for rule in settings.get("permissions", {}).get("allow", []):
        m = re.fullmatch(r"Bash(?:\((.*)\))?", rule)
        if not m or m.group(1) is None:
            if m:
                bad.append(rule)  # 괄호 없는 Bash = 전부 허용
            continue
        cmd = re.sub(r"(:\*|\s\*)$", "", m.group(1).strip()).strip()
        wild = cmd in ("", "*") or m.group(1).strip() != cmd  # 끝 와일드카드가 붙었는가
        if cmd in ("", "*", "python", "python3", "uv", "uv run", "python nova.py", "uv run python nova.py", "python -m", "git"):
            bad.append(rule)
        elif re.search(r"push|git tag|release", m.group(1)):
            bad.append(rule)  # 되돌리기 어려운 명령은 어떤 모양이든 허용 금지
        elif re.search(r"nova\.py", m.group(1)) and "*" in m.group(1):
            bad.append(rule)  # nova.py 밑 하위명령을 여럿 품는 모든 별표 모양
    return bad


def test_limits_single_source(tmp_path):
    # 어긋난 견본: 규약 문서가 상한 이름과 숫자를 함께 적으면 잡아야 한다
    (tmp_path / ".claude" / "commands").mkdir(parents=True)
    (tmp_path / "docs" / "conventions").mkdir(parents=True)
    (tmp_path / ".claude" / "commands" / "task-run.md").write_text(
        "### 안전장치\n| 상한 | 값 |\n|---|---|\n| 동시 구현자 수 | 3 |\n| 연속 실패 task 수 | 2 |\n\n## 다음\n", encoding="utf-8")
    (tmp_path / "docs" / "conventions" / "x.md").write_text(
        "깨끗한 줄\n동시 구현자 수 3 을 넘기지 않는다\n고치기 5회차에 멈춘다\n연속 실패 2번이면 멈춘다\n", encoding="utf-8")
    names, leaks = _limit_leaks(tmp_path)
    assert names == ["동시 구현자 수", "연속 실패 task 수"]
    assert [_head(n) for n in names] == ["동시 구현자", "연속 실패"]
    assert leaks == [("x.md", 2), ("x.md", 4)]  # 줄여 쓴 '연속 실패 2번' 도 잡힌다
    assert _head("task 당 고치기 회차") == "고치기"
    assert _near_digit("고치기 5회차에 멈춘다", "고치기")
    assert _head("한 번의 `--auto` 실행당 하위 에이전트 호출 수") == "에이전트 호출"
    assert not _near_digit("실패 3회 → dlq", "연속 실패") and not _near_digit("## 6. 고치기", "고치기")
    # 실제 저장소 — 상한 이름은 읽혀야 하고(빈 목록이면 검사가 헛돈다) 새는 곳이 없어야 한다
    names, leaks = _limit_leaks(ROOT)
    assert len(names) >= 3, "task-run 안전장치 표에서 상한 이름을 읽지 못했다"
    assert leaks == [], f"상한 숫자가 task-run 밖에 적혔다: {leaks}"


def test_settings_has_no_blanket_allow():
    # 어긋난 견본 — 막아야 하는 모양
    for rule in ("Bash(python nova.py:*)", "Bash(python nova.py *)", "Bash(python nova.py)", "Bash(git push:*)",
                 "Bash(git push origin main)", "Bash(git tag v1)", "Bash(python nova.py release ship:*)",
                 "Bash(python nova.py release publish)", "Bash(uv run python nova.py:*)", "Bash", "Bash(*)",
                 "Bash(python nova.py*)", "Bash(python nova.py release:*)"):
        assert _blanket_allows({"permissions": {"allow": [rule]}}) == [rule], rule
    # 통과해야 하는 모양 — 하위명령 정확 일치 · 읽기 명령
    ok = ["Bash(python nova.py lint)", "Bash(python nova.py quick)", "Bash(git status)", "Bash(git log:*)", "Read(./docs/**)"]
    assert _blanket_allows({"permissions": {"allow": ok}}) == []
    # 실제 settings.json
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert _blanket_allows(settings) == []
