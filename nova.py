#!/usr/bin/env python3
"""Nova 작업 진입점 — Windows · Linux 공통. `python nova.py help`

  install        uv sync — .venv 생성 + uv.lock 기준 설치 (uv 필수)
  test           전체 파이썬 테스트 (common · 서비스별 · 통합 · 저장소 검사 — 묶음을 동시에, --serial 이면 차례로. pytest-xdist 병렬은 기본 끔 — NOVA_TEST_WORKERS=<수>|auto 면 저장소(repo) 묶음만, auto 는 max(1, 코어 − 다른 묶음 수) 최대 4)
  quick          빠른 검사 — 바뀐 파일 · 단계 task 에 닿는 테스트 · lint 단계만(느린 테스트 제외) [--stage T<NN>-<단계> · --base · --slow · --dry]
  lint           정적 검사 (토큰 · 인프라 생성물 · 원장 · 명명 · 문서 인덱스 · 인프라 검증 · 이슈 · 교훈)
  check          test 와 lint 를 동시에 돌려 차례로 보고(통과한 테스트는 요약 줄만) · 실패한 축 이름 · 종료 1
  profile        규모 프로파일 — get | set <lite|product|platform> --why "<이유>" | check | suggest (scripts/project_profile.py)
  progress       진척 세 축을 따로 — 계획 · task 수 / 요구 상태 ↔ task 모순 / 릴리스 초안 [--check · --json]
  docs-write     기록 분량 — grade [범위](등급 · 기록 하한) | tasks [tasks_REQ_NN](3갈래 대조) | facts [범위](회차 사실) [--json]
  run            로컬 실행 — KAFKA_BOOTSTRAP 있으면 서비스별 프로세스, 없으면 단일 프로세스(:8080)
  gen            생성물 다시 만들기 (토큰 · k3s/helm/compose/관측 · 원장 sync)
  new-service    새 서비스 — python nova.py new-service <이름> --group <그룹> --scope <범위>
  new-pack       도메인 팩 — python nova.py new-pack <팩> --title "<이름>" --extends <서비스>
  new-project    새 프로젝트 — python nova.py new-project <폴더> --name "<이름>" --slug <영문> [--remote URL]
  dispatch       회차 분할안 — plan [--write] | next (scripts/dispatch.py)
  handoff        worktree 인수인계 · 관측 — status | close-check | observe (scripts/handoff.py)
  init           템플릿에서 시작 — GitHub "Use this template" 로 만든 저장소에서: python nova.py init --name "<이름>" --slug <영문>
  tokens         디자인 토큰 생성 + WCAG 검사
  kit            디자인 킷 — list | show(지금 설정 · 출처 · 날짜) | use <id> [--by 이름](목록 · 대비 통과 킷만 · 되돌리기 use nova) (scripts/kits.py)
  web            웹 샘플 앱 개발 서버 (npm install 후 dev)
  web-build      웹 전체 빌드
  mockups        계획서 화면 목업 HTML → PNG (docs/plans/mockups)
  stack          실행 스택 — up [--no-web · --no-build · --gw-port N · --web-port N] | status [--json] | down
                 (게이트웨이 메모리 DB + 데모 로그인 웹 · 빈 포트 자동 · 자식 프로세스까지 정리 · 상태 .stack/state.json)
  ui-smoke       웹 브라우저 스모크 (주소는 stack 상태 → 없으면 http://localhost:3100) · 캡처가 바뀌면 체크리스트 · 출고본 재생성
  kmp-test       KMP shared 단위 테스트 (JAVA_HOME = JDK 21)
  kmp-build      KMP uikit · composeApp 데스크톱 컴파일
  kmp-smoke      KMP 실연동 스모크 (게이트웨이 주소: NOVA_API → stack 상태 → :8080)
  kmp-snapshots  KMP 화면 PNG → docs/screenshots (주소는 kmp-smoke 와 같음 · 캡처가 바뀌면 체크리스트 · 출고본 재생성)
  e2e-kafka      실제 Kafka 로 E2E (bash · Linux/WSL)
  checklist      요구 체크리스트 폼 열기(저장 → inbound/checklist)
  checklist-smoke 체크리스트 폼 브라우저 스모크
  doctor         도구 설치 상태 점검
  exit-check     종료 조건 판정 — python nova.py exit-check REQ-YYMMDD-NN [--dry]
  release        릴리스 — status | check | suggest | changelog | draft <버전> | ship <버전> | publish <버전> [--dry]
                 | checkpoint "<사유>"(되돌릴 지점 태그) | rollback <태그> [--yes](코드 경로만 되돌림 · 폐기 브랜치 보존) (scripts/release.py)
  masterplan     마스터플랜 판본 — status | check | seal | adopt <초안> --why … --what …
  parallel-gate  병렬 개발 게이트 판정(공통 영역 완료 · 묶음 · 경로 겹침)
  worktree-new   병렬 묶음 worktree 만들기 — python nova.py worktree-new <묶음> · 격리용은 --scratch <이름>(게이트 안 봄 · 버스 등록 · --push 일 때만 푸시)
  worktree-prune 병합 끝난 worktree 정리 — 병합됨 · 미커밋 0 · 받은함 미처리 0(전체 공지 제외) 만 · 기본은 판정만, --yes 면 폴더 · 로컬 브랜치 삭제
  worktree-list  병렬 묶음 · worktree 목록
  converge       묶음 병합 — python nova.py converge <묶음> [--verify]
  worktree-sync  worktree 에서 main 따라잡기 — 들어올 변경을 공통부 · 기록 · 다른 묶음으로 나눠 보이고 merge(rebase 아님) [--dry 미리보기만]
  send · inbox · outbox · done · show   worktree 세션끼리 메시지 버스(.collab/) — show <ID> 는 메시지 전문
  upstream       상류(Nova) 판본 받기(복제본) — status | plan <태그> | apply <태그> (scripts/upstream.py)
  issue          이슈 기록 (scripts/issues.py)
  impact         변경 영향 보기 (scripts/impact.py)
  naming         명명 규약 · 개념 원장 — check | lookup <개념…> | entity add | alias add | retire | layer set | --write (scripts/naming.py)
  migrate        DB 마이그레이션 — python nova.py migrate <서비스> status | up | new "<설명>" [--empty] (nova_common.migrate · ADR-011)
  parked         격리 아웃박스 행 재처리 — python nova.py parked <서비스> list | requeue (--id N … | --all) (nova_common.outbox_admin)
  learn          교훈 기록 (scripts/lessons.py)
  usage          최근 N일 명령 · 스킬 · 에이전트 호출 수 — 훅 기록 .claude/state 요약 [--days 7] (.claude/hooks/nova_hooks.py)
                 --record 원장 docs/memo/agent_usage.jsonl 에 집계 한 줄(회차 마감) · --unused 한 번도 안 불린 에이전트
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
# 가상환경은 uv 가 관리한다(pyproject.toml · uv.lock · .python-version). python nova.py install = uv sync
PY = os.environ.get("PY") or (str(VENV_PY) if VENV_PY.exists() else sys.executable)


def uv() -> str:
    exe = shutil.which("uv")
    if not exe:
        print("✗ uv 가 없습니다. 설치: https://docs.astral.sh/uv/  (Windows: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\")")
        raise SystemExit(1)
    return exe
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def sh(cmd: list[str], cwd: Path = ROOT, env: dict | None = None) -> None:
    print(f"\n$ {' '.join(cmd)}" + (f"   (in {cwd.relative_to(ROOT).as_posix()})" if cwd != ROOT else ""), flush=True)
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})})
    if r.returncode != 0:
        print(f"✗ 실패 (종료코드 {r.returncode})")
        raise SystemExit(r.returncode)


def script(name: str, *args: str, required: bool = False) -> None:
    """scripts/<name> 실행. required=True(검사 단계)면 파일이 없을 때 실패 — 검사가 조용히 빠져 통과로 끝나지 않게."""
    path = ROOT / "scripts" / name
    if not path.exists():
        if required:
            print(f"✗ 실패: 검사 스크립트 scripts/{name} 이 없다 — 검사를 건너뛰고 통과로 끝내지 않는다")
            raise SystemExit(1)
        print(f"- 건너뜀: scripts/{name} 아직 없음")
        return
    sh([PY, str(path), *args])


def catalog() -> list[dict]:
    p = ROOT / "packages/common-py/nova_common/services.json"
    return json.loads(p.read_text(encoding="utf-8"))["services"] if p.exists() else []


def cmd_install(_: list[str]) -> None:
    global PY
    sh([uv(), "sync", "--all-packages"])
    PY = str(VENV_PY)


def ensure_env() -> None:
    """가상환경이 없으면 먼저 uv sync."""
    if not VENV_PY.exists() and not os.environ.get("PY"):
        cmd_install([])


def test_groups(args: list[str]) -> list[tuple[str, list[str], Path]]:
    """전체 테스트 묶음 — (이름, 명령, 실행 위치). 묶음마다 임시 폴더를 따로 준다:
    pytest.ini 의 --basetemp 하나를 같이 쓰면 동시에 돈 묶음이 서로의 임시 폴더를 지운다.
    프로세스 번호도 넣는다 — 다른 세션 · 담당이 같은 때 test 를 돌려도 겹치지 않게."""
    (ROOT / ".pytest_tmp").mkdir(exist_ok=True)   # worktree 처럼 아직 없는 곳에서도 basetemp 부모가 있게

    def cmd(name: str, target: str, extra: list[str] | None = None) -> list[str]:
        return [PY, "-m", "pytest", "-q", f"--basetemp={ROOT / '.pytest_tmp' / f't-{os.getpid()}-{name}'}", *(extra or []), *args, target]
    names: list[tuple[str, str, Path]] = []
    if (ROOT / "packages/common-py/tests").exists():
        names.append(("common", "packages/common-py/tests", ROOT))
    for s in catalog():
        d = ROOT / "services" / s["name"] / "tests"
        if d.exists():
            names.append((s["name"], "tests", d.parent))
    if (ROOT / "tests").exists():
        names.append(("repo", "tests", ROOT))
    # xdist 는 시간이 가장 긴 repo 묶음에만 — 묶음마다 붙이면 8코어에 작업 프로세스 수십 개가 떠 시간 측정형 테스트가 깨진다
    parallel = repo_parallel_args(len(names))
    return [(n, cmd(n, t, parallel if n == "repo" else None), cwd) for n, t, cwd in names]


def repo_parallel_args(group_count: int) -> list[str]:
    """repo 묶음의 xdist 인자 — 기본은 끔. NOVA_TEST_WORKERS=N(1 이상)일 때만 켜고, 'auto' 면
    max(1, 코어 - 동시에 도는 다른 묶음 수) 이고 최대 4. loadgroup 은 xdist_group 표시 테스트(new_project)를 한 작업자에 묶는다.
    기본을 끈 이유(2026-11-05 실측 · REQ-261105-10-1): 저장소 테스트는 하위 프로세스를 많이 띄우는 무거운 테스트라
    이 PC(8코어)에서 4작업자 18분 ≈ 직렬, 다른 묶음과 함께면 39분 · common 묶음이 10분으로 밀렸다. 전체 검사는 원격 CI 몫."""
    raw = os.environ.get("NOVA_TEST_WORKERS", "").strip()
    if raw in ("", "0"):
        return []
    n = str(min(4, max(1, (os.cpu_count() or 1) - max(0, group_count - 1)))) if raw == "auto" else raw
    return ["-n", n, "--dist", "loadgroup"]


def cmd_test(args: list[str]) -> None:
    """묶음(common · 서비스별 · 저장소)을 동시에 돌린다(REQ-261104-17). --serial 이면 예전처럼 차례로."""
    ensure_env()
    serial = "--serial" in args or os.environ.get("NOVA_TEST_SERIAL") == "1"
    groups = test_groups([a for a in args if a != "--serial"])
    if serial:
        for _, c, cwd in groups:
            sh(c, cwd=cwd)
        print("\n✓ test 통과")
        return
    failed = []
    for name, code, text in run_both([(n, c, cwd) for n, c, cwd in groups]):
        print(f"\n■ test {name} — {'통과' if code == 0 else f'실패(종료코드 {code})'}")
        print(text.rstrip())
        if code != 0:
            failed.append(name)
    if failed:
        print(f"\n✗ test 실패: {' · '.join(failed)}")
        raise SystemExit(1)
    print("\n✓ test 통과")


def cmd_lint(_: list[str]) -> None:
    ensure_env()
    script("gen_tokens.py", "--check", required=True)
    script("ui_check.py", required=True)                        # 웹 화면 · 부품의 토큰 밖 색 · 인라인 px(예외는 web/ui-check.json, REQ-261104-12-2)
    script("gen_k3s.py", "--check", required=True)
    script("gen_dashboards.py", "--check", required=True)
    script("gen_contract.py", "--check", required=True)        # 화면 상한 · 이메일 형식 = 서버 계약(REQ-261104-12-9)
    script("registry.py", "check", required=True)
    script("ledgers.py", "--check", required=True)
    script("naming.py", "check", required=True)
    script("packs.py", "check", required=True)
    script("docs_index.py", "--check", required=True)
    script("checklist.py", "check", required=True)
    script("warehouse.py", "check", required=True)
    script("validate_infra.py", required=True)
    script("masterplan.py", "check", required=True)
    script("release.py", "check", required=True)
    script("issues.py", "check", required=True)
    script("lessons.py", "check", required=True)
    script("claude_check.py", "--check", required=True)
    script("quick_check.py", "--check-tasks", required=True)   # tasks 가 단계 단위 검사 형식인지(REQ-261104-17)
    script("project_profile.py", "check", required=True)      # 규모 프로파일 선언 · 이유(REQ-261104-17-5)
    print("\n✓ lint 통과")


def run_both(cmds: list[tuple]) -> list[tuple[str, int, str]]:
    """명령들을 동시에 띄우고 각자의 출력(stdout+stderr)을 모은다 — 출력이 섞이지 않게 끝난 뒤 순서대로 낸다.
    항목은 (이름, 명령) 또는 (이름, 명령, 실행 위치)."""
    import tempfile
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    procs = []
    for name, cmd, *where in cmds:
        f = tempfile.TemporaryFile()   # 파이프 대신 파일 — 출력이 많아도 버퍼가 차서 멈추지 않는다
        procs.append((name, subprocess.Popen(cmd, cwd=where[0] if where else ROOT, env=env, stdout=f, stderr=subprocess.STDOUT), f))
    out = []
    for name, p, f in procs:
        code = p.wait()
        f.seek(0)
        out.append((name, code, f.read().decode("utf-8", "replace")))
        f.close()
    return out


def test_summary(text: str) -> str:
    """통과한 테스트 출력에서 요약 줄만 — pytest 의 'N passed' 줄 · 마지막 판정."""
    keep = [ln for ln in text.splitlines() if re.search(r"\d+ (passed|failed|errors?)\b|^✓|^✗", ln.strip())]
    if keep:
        return "\n".join(keep)
    return text.strip().splitlines()[-1] if text.strip() else "(출력 없음)"


def cmd_check(_: list[str]) -> None:
    """test · lint 를 동시에(서로 쓰는 파일이 없다 — lint 는 --check 읽기 전용) 돌려 기다리는 시간을 줄인다."""
    ensure_env()
    me = str(ROOT / "nova.py")
    failed = []
    for name, code, text in run_both([("test", [PY, me, "test"]), ("lint", [PY, me, "lint"])]):
        print(f"\n■ {name} — {'통과' if code == 0 else f'실패(종료코드 {code})'}")
        print(test_summary(text) if name == "test" and code == 0 else text.rstrip())
        if code != 0:
            failed.append(name)
    if failed:
        print(f"\n✗ check 실패: {' · '.join(failed)}")
        raise SystemExit(1)
    print("\n✓ check 통과 (test · lint)")


def cmd_gen(_: list[str]) -> None:
    script("gen_tokens.py")
    script("gen_k3s.py")
    script("gen_dashboards.py")
    script("gen_contract.py")
    script("ledgers.py")
    script("naming.py", "--write")
    script("checklist.py", "build")
    script("checklist.py", "md")
    script("warehouse.py", "out")
    script("claude_check.py", "--write")
    script("registry.py", "sync", "--by", os.environ.get("USER", os.environ.get("USERNAME", "dev")), "--note", "nova.py gen")


def cmd_run(_: list[str]) -> None:
    if os.environ.get("KAFKA_BOOTSTRAP"):
        sh(["bash", "scripts/run_local.sh"])
    else:
        script("dev_server.py")


def cmd_new_service(args: list[str]) -> None:
    script("new_service.py", *args)


def cmd_new_pack(args: list[str]) -> None:
    ensure_env()
    script("packs.py", "new", *args)


def cmd_new_project(args: list[str]) -> None:
    ensure_env()
    script("new_project.py", *args)


def cmd_tokens(_: list[str]) -> None:
    script("gen_tokens.py")


def npm() -> str:
    return shutil.which("npm") or shutil.which("npm.cmd") or "npm"


def cmd_web(_: list[str]) -> None:
    sh([npm(), "install"], cwd=ROOT / "web")
    sh([npm(), "run", "dev"], cwd=ROOT / "web")


def cmd_web_build(_: list[str]) -> None:
    sh([npm(), "install"], cwd=ROOT / "web")
    sh([npm(), "run", "build"], cwd=ROOT / "web")


def cmd_mockups(args: list[str]) -> None:
    ensure_env()
    script("mockup_shots.py", *args)


def _shots() -> dict[str, tuple[int, int]]:
    d = ROOT / "docs" / "screenshots"
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in d.glob("*.png")} if d.exists() else {}


def _after_shots(before: dict) -> None:
    """캡처가 바뀌면 그것을 그림으로 품는 생성물(체크리스트 폼 inbound → 출고본 outbound)을 다시 만든다(T04-9.13).
    그대로 두면 다음 전체 check 에서 생성물 드리프트로 실패한다."""
    changed = sorted(n for n, v in _shots().items() if before.get(n) != v)
    if changed:
        print(f"\n■ 캡처 {len(changed)}장 바뀜 — 체크리스트 폼 · 출고본 다시 만들기")
        script("checklist.py", "build")
        script("warehouse.py", "out")


def cmd_ui_smoke(args: list[str]) -> None:
    ensure_env()
    before = _shots()
    try:
        script("ui_smoke.py", *args)
    finally:
        _after_shots(before)


def cmd_stack(args: list[str]) -> None:
    ensure_env()
    script("stack.py", *args)


def _stack_api() -> list[str]:
    """kmp 명령이 붙을 게이트웨이 — NOVA_API > 실행 중인 stack > 없으면 Gradle 기본값(8080). T05-9.01"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import stack

    ep = stack.endpoints(ROOT)
    if ep["from"] == "기본값":
        return []
    api = ep["api"].replace("localhost", "127.0.0.1")
    print(f"■ 게이트웨이 {api} (주소 출처: {ep['from']})")
    return [f"-Papi={api}"]


def gradlew(*tasks: str) -> None:
    """저장소의 Gradle 래퍼(apps/kmp/gradlew)로 실행. JAVA_HOME 은 JDK 21."""
    if not os.environ.get("JAVA_HOME"):
        print("✗ JAVA_HOME 이 없습니다 — JDK 21 경로를 지정하세요")
        raise SystemExit(1)
    kmp = ROOT / "apps/kmp"
    exe = str(kmp / ("gradlew.bat" if os.name == "nt" else "gradlew"))
    sh([exe, "--console=plain", *tasks], cwd=kmp)


def cmd_kmp_test(_: list[str]) -> None:
    gradlew("-Pnova.skipCompose=true", ":shared:jvmTest")


def cmd_kmp_build(_: list[str]) -> None:
    gradlew(":uikit:compileKotlinDesktop", ":composeApp:compileKotlinDesktop")


def cmd_kmp_smoke(_: list[str]) -> None:
    gradlew("-Pnova.skipCompose=true", ":shared:smoke", *_stack_api())


def cmd_kmp_snapshots(_: list[str]) -> None:
    before = _shots()
    try:
        gradlew(":composeApp:snapshots", f"-Pout={ROOT / 'docs' / 'screenshots'}", *_stack_api())
    finally:
        _after_shots(before)


def cmd_e2e_kafka(_: list[str]) -> None:
    sh(["bash", "scripts/e2e_kafka.sh"])


def cmd_checklist(args: list[str]) -> None:
    """요구 체크리스트 폼 열기 — [저장]이 docs/warehouse/inbound/checklist/ 에 바로 기록된다."""
    script("checklist.py", "serve", *args)


def cmd_checklist_smoke(args: list[str]) -> None:
    script("checklist_smoke.py", *args)


def cmd_exit_check(args: list[str]) -> None:
    script("goals.py", *args)


def cmd_release(args: list[str]) -> None:
    script("release.py", *args)


def cmd_masterplan(args: list[str]) -> None:
    script("masterplan.py", *args)


def cmd_migrate(args: list[str]) -> None:
    """서비스 DB 마이그레이션 — 본체는 nova_common.migrate(복제 프로젝트도 같은 명령을 물려받는다)."""
    ensure_env()
    sh([PY, "-m", "nova_common.migrate", *args])


def _sub(name: str, sub: str):
    return lambda args: script(name, sub, *args)


def cmd_doctor(_: list[str]) -> None:
    tools = {"uv": shutil.which("uv"), "python": PY, "git": shutil.which("git"), "node": shutil.which("node"), "npm": shutil.which("npm"),
             "java": shutil.which("java"), "gradle": shutil.which("gradle"), "docker": shutil.which("docker"),
             "kubectl": shutil.which("kubectl"), "bash": shutil.which("bash")}
    for k, v in tools.items():
        print(f"{'✓' if v else '✗'} {k:8} {v or '(없음)'}")
    print(f"  JAVA_HOME={os.environ.get('JAVA_HOME', '(없음)')}")
    print(superpowers_status())


SUPERPOWERS = "superpowers@claude-plugins-official"


def superpowers_status() -> str:
    """Superpowers 플러그인 — 저장소 설정(.claude/settings.json)에 켜져 있는지 · 이 PC 에 설치됐는지 (docs/conventions/superpowers.md)."""
    def load(p: Path) -> dict:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    enabled = load(ROOT / ".claude" / "settings.json").get("enabledPlugins", {}).get(SUPERPOWERS) is True
    installed = load(Path.home() / ".claude" / "plugins" / "installed_plugins.json").get("plugins", {}).get(SUPERPOWERS) or []
    ver = installed[0].get("version", "?") if installed else ""
    mark = "✓" if enabled and installed else "✗"
    where = f"설치됨 v{ver}" if installed else "설치 안 됨 → Claude Code 에서 /plugin install " + SUPERPOWERS
    return f"{mark} {'superpowers':8} {where} · 저장소 설정 {'켜짐' if enabled else '꺼짐(.claude/settings.json)'}"


COMMANDS = {
    "install": cmd_install, "test": cmd_test, "lint": cmd_lint, "gen": cmd_gen, "run": cmd_run,
    "new-service": cmd_new_service, "new-project": cmd_new_project, "new-pack": cmd_new_pack, "tokens": cmd_tokens, "kit": lambda a: script("kits.py", *a), "web": cmd_web, "web-build": cmd_web_build,
    "mockups": cmd_mockups, "ui-smoke": cmd_ui_smoke, "stack": cmd_stack, "kmp-test": cmd_kmp_test, "kmp-build": cmd_kmp_build, "kmp-smoke": cmd_kmp_smoke, "kmp-snapshots": cmd_kmp_snapshots, "e2e-kafka": cmd_e2e_kafka, "doctor": cmd_doctor,
    "checklist": cmd_checklist, "checklist-smoke": cmd_checklist_smoke,
    "exit-check": cmd_exit_check, "release": cmd_release, "masterplan": cmd_masterplan,
    "parallel-gate": _sub("parallel.py", "gate"), "worktree-new": _sub("parallel.py", "new"),
    "worktree-list": _sub("parallel.py", "list"), "converge": _sub("parallel.py", "converge"),
    "worktree-sync": _sub("parallel.py", "sync"), "worktree-prune": _sub("parallel.py", "prune"),
    "init": lambda a: (ensure_env(), script("template_init.py", *a)), "dispatch": lambda a: script("dispatch.py", *a), "handoff": lambda a: script("handoff.py", *a), "check": cmd_check, "progress": lambda a: script("progress.py", *a),
    "docs-write": lambda a: script("docs_write.py", *a), "upstream": lambda a: script("upstream.py", *a),
    "issue": lambda a: script("issues.py", *a), "impact": lambda a: script("impact.py", *a), "naming": lambda a: script("naming.py", *a), "migrate": cmd_migrate, "parked": lambda a: (ensure_env(), sh([PY, "-m", "nova_common.outbox_admin", *a])), "learn": lambda a: script("lessons.py", *a),
    "send": _sub("collab.py", "send"), "inbox": _sub("collab.py", "inbox"),
    "outbox": _sub("collab.py", "outbox"), "done": _sub("collab.py", "done"), "show": _sub("collab.py", "show"),
    "quick": lambda a: (ensure_env(), _quick(a)), "profile": lambda a: script("project_profile.py", *a),
    "usage": lambda a: sh([sys.executable, str(ROOT / ".claude/hooks/nova_hooks.py"), "usage", *a]),
}


def _quick(args: list[str]) -> None:
    path = ROOT / "scripts" / "quick_check.py"
    r = subprocess.run([PY, str(path), *args], cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8", "PY": PY})
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help") or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 0 if len(sys.argv) < 2 or sys.argv[1] in ("help", "-h", "--help") else 2
    COMMANDS[sys.argv[1]](sys.argv[2:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
