"""빠른 검사 — 바뀐 파일 · 단계 task 에 닿는 테스트와 lint 단계만 골라 한 번에 돌린다 (REQ-261104-17-1).

task 마다는 이것, 단계 끝 · 푸시 묶음 · [DEEP] · /finish · /release 는 전체 `python nova.py check`.
느린 테스트(`@pytest.mark.slow` — 하위 프로세스 · 생성기 전체 · 실제 DB)는 빼고 돈다(`--slow` 로 포함).

  python nova.py quick                    # 지난 커밋 이후 바뀐 파일(+ 새 파일) 기준
  python nova.py quick --stage T02-1      # 그 단계 task 에 적힌 테스트 + 바뀐 파일
  python nova.py quick --base main        # 비교 기준 바꾸기
  python nova.py quick --dry              # 고른 것만 보여 주고 돌리지 않는다
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = os.environ.get("PY") or sys.executable

# 테스트 경로 표기 — tasks 문서 · 바뀐 파일 양쪽에서 같은 모양을 쓴다
TEST_PATH = re.compile(r"(?:services/[\w-]+/tests|packages/common-py/tests|tests)/[\w/.-]*?test_\w+\.py(?:::[\w\[\]-]+)?")

# 경로 없이 함수 이름만 적은 테스트(`test_x 통과`) — 관문이 테스트 폴더에서 def 를 찾아 경로로 바꾼다
TEST_NAME = re.compile(r"(?<![\w/.:])test_\w+(?![\w.])")
TEST_DIRS = ("tests", "packages/common-py/tests", "services")


def resolve_names(names: list[str]) -> list[str]:
    """테스트 함수 이름 → `경로::이름`. 아직 없는 이름(작성 전)은 빼고, 이름이 여러 곳이면 모두."""
    if not names:
        return []
    want = set(names)
    found: dict[str, list[str]] = {}
    for d in TEST_DIRS:
        for f in sorted((ROOT / d).rglob("test_*.py")):
            if "_template" in f.parts:
                continue
            try:
                body = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                print(f"  ! 테스트 파일을 읽지 못함: {f} — {e}", file=sys.stderr)
                continue
            for n in re.findall(r"^\s*(?:async\s+)?def (test_\w+)\(", body, re.M):
                if n in want:
                    found.setdefault(n, []).append(f"{f.relative_to(ROOT).as_posix()}::{n}")
    return [x for n in names for x in found.get(n, [])]


# 데이터 원천(앞부분) → 그것을 읽는 모듈 이름 — 그 모듈을 import 하는 테스트를 고른다
DATA_OWNERS: list[tuple[str, tuple[str, ...]]] = [
    ("registry/naming.json", ("naming",)),
    ("registry/entities.json", ("naming",)),
    ("registry/ledgers.json", ("ledgers",)),
    ("registry/registry", ("registry",)),
    ("registry/events.jsonl", ("registry",)),
    ("design/tokens/", ("gen_tokens",)),
    ("packages/common-py/nova_common/services.json", ("catalog", "gen_k3s", "new_service")),
    ("infra/k3s/base/kafka-topics.txt", ("gen_k3s", "topic_catalog")),
    ("nova.project.json", ("gen_k3s", "new_project", "project_profile", "gen_tokens", "kits")),   # design.kit 이 토큰 생성물을 정한다
    ("docs/releases/releases.json", ("release",)),
    ("docs/issues/", ("issues",)),
    ("docs/memo/lessons", ("lessons",)),
    ("docs/warehouse/", ("checklist", "warehouse")),
    ("docs/product/", ("warehouse",)),
    (".claude/", ("claude_check",)),
]

# 바뀐 경로(앞부분) → 돌릴 lint 단계. 이름은 scripts/<이름>.py, 인자는 nova.py lint 와 같다
LINT_STEPS = {
    "gen_tokens": ("gen_tokens.py", "--check"),
    "gen_k3s": ("gen_k3s.py", "--check"),
    "gen_dashboards": ("gen_dashboards.py", "--check"),
    "validate_infra": ("validate_infra.py",),
    "registry": ("registry.py", "check"),
    "ledgers": ("ledgers.py", "--check"),
    "naming": ("naming.py", "check"),
    "packs": ("packs.py", "check"),
    "docs_index": ("docs_index.py", "--check"),
    "checklist": ("checklist.py", "check"),
    "warehouse": ("warehouse.py", "check"),
    "masterplan": ("masterplan.py", "check"),
    "release": ("release.py", "check"),
    "issues": ("issues.py", "check"),
    "lessons": ("lessons.py", "check"),
    "claude_check": ("claude_check.py", "--check"),
    "tasks": ("quick_check.py", "--check-tasks"),
    "profile": ("project_profile.py", "check"),
}
LINT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("design/tokens/", ("gen_tokens",)),
    ("scripts/gen_tokens.py", ("gen_tokens",)),
    ("packages/common-py/nova_common/services.json", ("gen_k3s", "gen_dashboards", "validate_infra", "registry", "ledgers")),
    ("infra/", ("gen_k3s", "gen_dashboards", "validate_infra")),
    ("scripts/gen_k3s.py", ("gen_k3s", "validate_infra")),
    ("scripts/gen_dashboards.py", ("gen_dashboards", "validate_infra")),
    ("scripts/validate_infra.py", ("validate_infra",)),
    ("nova.project.json", ("gen_k3s", "docs_index", "claude_check", "profile", "gen_tokens")),   # design.kit
    ("scripts/project_profile.py", ("profile",)),
    ("services/", ("registry", "ledgers", "naming", "packs")),
    ("web/", ("registry", "ledgers")),
    ("apps/kmp/", ("registry",)),
    ("registry/", ("registry", "ledgers", "naming")),
    ("scripts/registry.py", ("registry",)),
    ("scripts/ledgers.py", ("ledgers",)),
    ("scripts/naming.py", ("naming",)),
    ("packs/", ("packs", "claude_check")),
    ("docs/", ("docs_index",)),
    ("scripts/docs_index.py", ("docs_index",)),
    ("docs/plans/master_plan", ("masterplan",)),
    ("docs/plans/drafts/", ("masterplan",)),
    ("docs/plans/tasks/", ("tasks",)),
    ("scripts/quick_check.py", ("tasks",)),
    ("docs/releases/", ("release",)),
    ("docs/issues/", ("issues",)),
    ("docs/memo/lessons", ("lessons",)),
    ("docs/warehouse/", ("checklist", "warehouse")),
    ("docs/product/", ("warehouse",)),
    (".claude/", ("claude_check",)),
    ("CLAUDE.md", ("claude_check", "docs_index")),
]


def _rel(p: str) -> str:
    # lstrip("./") 는 '.claude/' 의 점까지 지운다 — 앞의 './' 한 번만 뗀다
    return p.replace("\\", "/").removeprefix("./")


def _module_tests(module: str, dirs: list[Path]) -> list[str]:
    """그 모듈을 import · 실행하는 테스트 파일 — import 문 · 스크립트 경로 · 모듈 경로 표기로 찾는다."""
    pat = re.compile(
        rf"(^\s*import [\w, ]*\b{module}\b|^\s*from {module} import|^\s*from nova_common(?:\.\w+)* import [^\n]*\b{module}\b"
        rf"|nova_common\.{module}\b|scripts/{module}\.py|[\"']{module}\.py[\"'])", re.M)
    out = []
    for d in dirs:
        for f in sorted(d.rglob("test_*.py")):
            try:
                if pat.search(f.read_text(encoding="utf-8")):
                    out.append(f.relative_to(ROOT).as_posix())
            except (OSError, UnicodeDecodeError) as e:   # 읽지 못한 테스트는 건너뛰되 알린다 — 조용히 빼면 덜 돈다
                print(f"  ! 테스트 파일을 읽지 못함: {f} — {e}", file=sys.stderr)
    return out


def select_tests(files: list[str]) -> list[str]:
    """바뀐 파일 → 돌릴 테스트 경로(중복 없이 처음 나온 순서)."""
    picked: list[str] = []
    root_tests = [ROOT / "tests"]
    common_tests = [ROOT / "packages/common-py/tests", ROOT / "tests"]

    def add(*xs: str) -> None:
        for x in xs:
            if x not in picked:
                picked.append(x)

    for raw in files:
        f = _rel(raw)
        m = re.match(r"services/([\w-]+)/", f)
        if f.startswith("services/_template/"):
            # 자리표시(__PKG__)가 든 원본이라 그 폴더에서는 못 돌린다 — 템플릿으로 서비스를 만들어 보는 테스트로
            add("tests/test_new_service.py")
        elif TEST_PATH.fullmatch(f):
            add(f)
        elif m and (ROOT / "services" / m.group(1) / "tests").is_dir():
            add(f"services/{m.group(1)}/tests")
        elif f.startswith("packages/common-py/") and f.endswith(".py"):
            add(*_module_tests(Path(f).stem, common_tests))
        elif f.startswith("scripts/") and f.endswith(".py"):
            add(*_module_tests(Path(f).stem, root_tests))
        elif any(f.startswith(src) for src, _ in DATA_OWNERS):
            # 데이터 원천 → 그것을 읽는 스크립트 · 모듈의 테스트(lint 만으로는 테스트 픽스처와의 어긋남을 못 잡는다)
            for src, owners in DATA_OWNERS:
                if f.startswith(src):
                    for o in owners:
                        add(*_module_tests(o, common_tests if o in ("catalog",) else root_tests))
        elif f == "nova.py":
            add(*_module_tests("nova", root_tests))
        elif f == "conftest.py":
            # 루트 conftest 는 저장소 전체에 걸린다 — 전체(`.`)를 한 pytest 로 돌리면 이름이 같은 테스트 파일이 부딪힌다.
            # 그것을 지키는 테스트로 보내고, 전체 확인은 단계 관문의 전체 check 가 한다
            add("tests/test_pytest_tmp.py")
        elif f.endswith("conftest.py"):
            add(str(Path(f).parent.as_posix()))
    return picked


def select_lint(files: list[str]) -> list[str]:
    """바뀐 파일 → 돌릴 lint 단계 이름(LINT_STEPS 순서)."""
    want: set[str] = set()
    for raw in files:
        f = _rel(raw)
        for prefix, steps in LINT_RULES:
            if f.startswith(prefix):
                want.update(steps)
    return [k for k in LINT_STEPS if k in want]


def stage_tests(tasks_text: str, stage: int) -> list[str]:
    """tasks 문서의 '## N단계' 절에 적힌 테스트 경로."""
    out: list[str] = []
    names: list[str] = []
    inside = False
    for line in tasks_text.splitlines():
        h = re.match(r"^## (\d+)단계", line)
        if h:
            inside = int(h.group(1)) == stage
            continue
        if line.startswith("## "):
            inside = False
        if inside:
            for t in TEST_PATH.findall(line):
                if t not in out:
                    out.append(t)
            for n in TEST_NAME.findall(TEST_PATH.sub(" ", line)):
                if n not in names:
                    names.append(n)
    for t in resolve_names(names):
        if t not in out:
            out.append(t)
    return out


def check_tasks(text: str, where: str) -> list[str]:
    """tasks 문서가 '단계 단위 검사' 형식인지 — 체크하지 않은 task 에만 적용한다(끝난 기록은 그대로 둔다).

    ① 체크 안 한 코드 task(테스트 경로 · TDD 하위 줄)가 있는 단계에는 '**단계 관문**' 줄
    ② 체크 안 한 task 하위 줄에 커밋을 두지 않는다 — 커밋 · git 기록은 관문에서 묶는다
    ③ TDD 하위 줄이 있는 task 는 테스트 경로를 적는다 — 관문의 quick --stage 가 그것을 모은다
    """
    errs: list[str] = []
    stage: tuple[str, list[str]] | None = None
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("## "):
            stage = (line[3:].strip(), [])
            sections.append(stage)
        elif stage is not None:
            stage[1].append(line)
    for title, lines in sections:
        if not re.match(r"\d+단계", title):
            continue
        tasks: list[tuple[str, bool, list[str]]] = []   # (머리 줄, 끝남, 하위 줄)
        for line in lines:
            m = re.match(r"^- \[( |x)\] (.*)$", line)
            if m:
                tasks.append((m.group(2), m.group(1) == "x", []))
            elif tasks and re.match(r"^\s+\S", line):
                tasks[-1][2].append(line)
        open_code = False
        for head, done, subs in tasks:
            if done:
                continue
            tid = (re.search(r"T\d{2}-\d+\.\d+", head) or re.search(r"\S+", head)).group(0)
            block = "\n".join([head, *subs])
            tdd = any("실패 테스트" in s for s in subs)
            # 코틀린 테스트(…Test.kt · kmp-test)도 테스트 표기 — pytest 관문이 모으지 않을 뿐 형식 위반은 아니다
            has_path = bool(TEST_PATH.search(block) or TEST_NAME.search(block) or re.search(r"\w+Test\.kt|kmp-test", block))
            if tdd or has_path:
                open_code = True
            if tdd and not has_path:
                errs.append(f"{where} · {tid}: TDD task 인데 테스트 경로(tests/…py::이름) · 이름(test_…)이 없다 — 단계 관문이 모을 수 없다")
            if any(re.match(r"^\s+- \[ \] 커밋", s) or "· [ ] 커밋" in s for s in subs):
                errs.append(f"{where} · {tid}: task 하위 줄에 커밋이 있다 — 커밋 · git 기록은 단계 관문에서 묶는다")
        if open_code and not any("**단계 관문**" in ln for ln in lines):
            errs.append(f"{where} · {title}: 남은 코드 task 가 있는데 '**단계 관문**' 줄이 없다 — quick --stage → 전체 check → 커밋 묶음")
    return errs


def group_by_root(tests: list[str]) -> dict[str, list[str]]:
    """서비스 테스트는 그 서비스 폴더에서 돌린다(nova.py test 와 같은 방식) — 실행 위치별로 묶는다."""
    groups: dict[str, list[str]] = {}
    for t in tests:
        m = re.match(r"services/([\w-]+)/(tests.*)$", t)
        if m:
            key, arg = f"services/{m.group(1)}", m.group(2)
        elif t.startswith("packages/common-py/"):
            # 저장소 테스트와 한 프로세스에 섞으면 전역 상태가 엉킨다 — 전체 test 와 같은 경계(실행 위치는 저장소 루트)
            key, arg = "packages/common-py", t
        else:
            key, arg = ".", t
        groups.setdefault(key, [])
        if arg not in groups[key]:
            groups[key].append(arg)
    # 폴더를 통째로 고른 묶음에서는 그 안의 파일 · 테스트를 따로 넣지 않는다(두 번 돌지 않게)
    for key, args in groups.items():
        dirs = [a for a in args if "::" not in a and not a.endswith(".py")]
        whole = {a for a in args if "::" not in a}
        groups[key] = [a for a in args if (a in dirs or not any(a.startswith(d.rstrip("/") + "/") for d in dirs))
                       and not ("::" in a and a.split("::")[0] in whole)]
    return groups


def basetemp(i: int) -> Path:
    """묶음별 임시 폴더 — 프로세스 번호를 넣는다. 여러 세션 · 담당이 동시에 돌리면 같은 폴더를 서로 지운다
    (pytest 는 시작할 때 --basetemp 를 비운다 · 2026-11-04 WinError 32 로 드러남)."""
    return ROOT / ".pytest_tmp" / f"quick-{os.getpid()}-{i}"


def changed_files(base: str) -> list[str]:
    def git(*a: str) -> list[str]:
        r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise SystemExit(f"✗ git {' '.join(a)} 실패: {r.stderr.strip()}")
        return [x for x in r.stdout.splitlines() if x.strip()]
    files = git("diff", "--name-only", base) + git("ls-files", "--others", "--exclude-standard")
    return [f for f in dict.fromkeys(files) if (ROOT / f).exists()]


def _tasks_file(stage_id: str) -> tuple[Path, int]:
    m = re.fullmatch(r"T(\d{2})-(\d+)", stage_id)
    if not m:
        raise SystemExit(f"✗ 단계 표기는 T<NN>-<단계> 형식이다(예: T02-1): {stage_id}")
    p = ROOT / "docs/plans/tasks" / f"tasks_REQ_{m.group(1)}.md"
    if not p.exists():
        raise SystemExit(f"✗ tasks 문서가 없다: {p.relative_to(ROOT).as_posix()}")
    return p, int(m.group(2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="빠른 검사 — 바뀐 곳에 닿는 테스트 · lint 단계만")
    ap.add_argument("--stage", help="단계 표기 T<NN>-<단계> — 그 단계 task 에 적힌 테스트를 더한다")
    ap.add_argument("--base", default="HEAD", help="비교 기준(기본 HEAD — 아직 커밋하지 않은 변경)")
    ap.add_argument("--slow", action="store_true", help="느린 테스트(slow 표시)도 함께")
    ap.add_argument("--dry", action="store_true", help="고른 것만 보여 주고 돌리지 않는다")
    ap.add_argument("--check-tasks", action="store_true", help="tasks 문서가 단계 단위 검사 형식인지 검사(lint 단계)")
    a = ap.parse_args(argv)

    if a.check_tasks:
        files = sorted((ROOT / "docs/plans/tasks").glob("tasks_REQ_*.md"))
        errs = [e for p in files for e in check_tasks(p.read_text(encoding="utf-8"), p.name)]
        for e in errs:
            print(f"  ✗ {e}")
        if errs:
            print(f"✗ tasks 형식 위반 {len(errs)}건 — 규칙: docs/plans/README.md §3 '테스트는 단계 단위로 모은다'")
            return 1
        print(f"✓ tasks 형식 정상: {len(files)}개 — 단계 관문 · 테스트 경로")
        return 0

    files = changed_files(a.base)
    tests = select_tests(files)
    if a.stage:
        p, n = _tasks_file(a.stage)
        tests = list(dict.fromkeys(stage_tests(p.read_text(encoding="utf-8"), n) + tests))
    tests = [t for t in tests if (ROOT / t.split("::")[0]).exists()]
    lint = select_lint(files)

    print(f"■ 빠른 검사 — 바뀐 파일 {len(files)}개 · 테스트 {len(tests)}곳 · lint {len(lint)}단계"
          + ("" if a.slow else " (느린 테스트 제외)"))
    for t in tests:
        print(f"  · test {t}")
    for s in lint:
        print(f"  · lint {s}")
    if a.dry:
        return 0

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    failed: list[str] = []
    for i, (where, args) in enumerate(group_by_root(tests).items()):
        cmd = [PY, "-m", "pytest", "-q", f"--basetemp={basetemp(i)}", *args]
        if not a.slow:
            cmd += ["-m", "not slow"]
        r = subprocess.run(cmd, cwd=ROOT / where if where.startswith("services/") else ROOT, env=env)
        if r.returncode not in (0, 5):   # 5 = 고른 테스트가 모두 slow 라 돌 것이 없음 — 실패가 아니다
            failed.append(f"test {where}")
    for s in lint:
        r = subprocess.run([PY, str(ROOT / "scripts" / LINT_STEPS[s][0]), *LINT_STEPS[s][1:]], cwd=ROOT, env=env)
        if r.returncode != 0:
            failed.append(f"lint {s}")
    if failed:
        print(f"\n✗ 빠른 검사 실패: {' · '.join(failed)}")
        return 1
    print("\n✓ 빠른 검사 통과 — 단계 끝 · 푸시 묶음에는 전체 `python nova.py check`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
