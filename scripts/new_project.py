#!/usr/bin/env python3
"""새 프로젝트 만들기 — Nova 공통개발플랫폼을 복사해 같은 구조 · 규칙 · 도구로 시작한다.

  python scripts/new_project.py <대상 폴더> --name "<프로젝트 이름>" --slug <영문-소문자> [옵션]
  예) python scripts/new_project.py F:/project-nuri/shop --name "쇼핑몰" --slug shop --remote https://github.com/me/shop

옵션:
  --owner 이름              요구사항 요청자(기본: nova.project.json 의 owner)
  --remote URL              git 원격(origin). 없으면 원격 없이 git init 만
  --registry 주소            컨테이너 이미지 레지스트리(기본 ghcr.io/<계정>/<slug>)
  --domain 도메인            인그레스 도메인(기본 <slug>.local)
  --app-id 패키지            모바일 앱 ID(기본 kr.<slug>.app)
  --no-git                  git init 하지 않음
  --setup                   만든 뒤 uv sync · npm install 까지
  --ref 태그|HEAD            만들 판본(기본: 최신 정식 태그 vX.Y.Z — rc 제외 · 태그가 없으면 경고하고 작업 트리). HEAD 는 작업 트리(경고)

바뀌는 것(프로젝트 고유): nova.project.json · 웹/모바일 앱 브랜드 · 앱 ID · 레지스트리 · 도메인 · CLAUDE.md/README 머리 · 문서 기록(비움)
                       · 개념 원장 registry/entities.json(l)(이력을 비우고 플랫폼 · 샘플 개념만 — 명명 규약 naming.json 은 그대로)
그대로인 것(플랫폼): nova_common · @nova/* · kr.nova.uikit · 메트릭 접두어 nova_ · 규약 · ADR-001~ · 스크립트 · 템플릿
→ 플랫폼 개선은 Nova 에서 하고 프로젝트로 가져온다(프레임워크 버전을 올리듯).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, project, write  # noqa: E402

import naming  # noqa: E402
import upstream  # noqa: E402
import versions  # noqa: E402

SLUG = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
# 복사하지 않는 것 — 실행 상태 · 빌드 산출물 · 의존성
SKIP_DIRS = {".git", ".venv", "node_modules", ".next", "build", ".gradle", ".kotlin", ".pytest_tmp", ".pytest_cache",
             "__pycache__", "data", ".run", ".idea", ".vscode", ".superpowers", ".worktrees"}
# 비우는 기록 폴더(템플릿 · 인덱스 머리만 남김)
RESET_DOCS = {
    "requirement": ("requirement_index.md", r"requirement_\d{6}_\d{2}\.md"),
    "requirement/interviews": ("interview_index.md", r"interview_\d{6}_\d{2}\.md"),
    "history": ("history_index.md", r"history_\d{6}_\d{2}\.md"),
    "git": ("git_index.md", r"git_\d{6}_\d{2}\.md"),
    "session": ("session_index.md", r"session_\d{6}_\d{2}\.md|LATEST\.md"),
    "reviews": ("review_index.md", r"review_\d{6}_\d{2}\.md"),
    "verification": ("verification_index.md", r"verify_\d{6}_\d{2}\.md"),
}


def git_ignored(root: Path) -> set[str]:
    """root 저장소에서 git 이 무시하는 경로(폴더는 폴더 하나로) — .env · .collab/ · settings.local.json 같은 비밀값 · 로컬 상태.

    root 가 git 저장소의 맨 위가 아니거나 git 이 없으면 빈 집합(SKIP_DIRS 만으로 복사). 상위 저장소의 규칙을 잘못 빌리지 않게 맨 위를 확인한다."""
    def run(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8")
    try:
        top = run("rev-parse", "--show-toplevel")
        if top.returncode != 0 or Path(top.stdout.strip()).resolve() != Path(root).resolve():
            return set()
        r = run("ls-files", "-oi", "--exclude-standard", "--directory", "-z")
    except OSError:
        return set()
    if r.returncode != 0:
        return set()
    return {x.rstrip("/") for x in r.stdout.split("\0") if x.strip()}


_ignored_cache: set[str] | None = None


def _ignored() -> set[str]:
    global _ignored_cache
    if _ignored_cache is None:
        _ignored_cache = git_ignored(ROOT)
    return _ignored_cache


def ignore(dirpath: str, names: list[str]) -> set[str]:
    rel = Path(dirpath).resolve().relative_to(ROOT).as_posix()
    out = {n for n in names if n in SKIP_DIRS or n.endswith((".pyc", ".tsbuildinfo")) or n.startswith(".pytest_tmp")}
    # git 무시 파일은 옮기지 않는다(T04-9.06) — 추적 전 새 파일(작업 중인 공통부)은 옮긴다. upstream.py 의 '-co --exclude-standard' 와 같은 경계
    ign = _ignored()
    out |= {n for n in names if (n if rel == "." else f"{rel}/{n}") in ign}
    if rel == ".claude":
        out |= {"worktrees"}  # 에이전트 격리 작업 폴더(Claude Code) — 물려주지 않는다
    if rel == "docs":
        out |= {"screenshots"}  # 플랫폼 화면 캡처는 가져오지 않는다
    if rel == "docs/plans/mockups":
        out |= {n for n in names if n != "_shell.json" and not n.startswith(".")}
    if rel == "docs/plans/archive" or rel == "docs/plans/drafts":
        out |= {n for n in names if n != ".gitkeep"}
    return out


def table_head(text: str) -> str:
    """인덱스 문서에서 표 머리(구분줄)까지만 남긴다."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.match(r"^\|[-| ]+\|$", ln.strip()):
            return "\n".join(lines[: i + 1]) + "\n"
    return text


def reset_docs(dest: Path) -> None:
    docs = dest / "docs"
    for folder, (index, pattern) in RESET_DOCS.items():
        base = docs / folder
        for p in base.iterdir():
            if re.fullmatch(pattern, p.name):
                p.unlink()
        write(base / index, table_head((base / index).read_text(encoding="utf-8")))
    plans = docs / "plans"
    for p in [*plans.glob("plan_REQ_*.md"), *(plans / "tasks").glob("tasks_REQ_*.md")]:
        p.unlink()
    write(plans / "plan_index.md", table_head((plans / "plan_index.md").read_text(encoding="utf-8")))
    for p in (dest / "registry").glob("*"):
        if p.name in ("events.jsonl", "registry.json"):
            p.unlink()
    (docs / "registry" / "README.md").unlink(missing_ok=True)
    # 개념 원장 — 명명 규약(naming.json)은 물려주고, 원장은 이력을 비워 플랫폼 · 샘플 개념만으로 다시 시작한다
    # (샘플 표가 남아 있으니 미등재 실패가 나지 않게 · 코어 개념의 금지 별칭은 비워 새 도메인어가 걸리지 않게)
    if (dest / naming.ENTITY_LOG).exists():
        naming.reset_for_project(dest)
    # 제품 정본(intake · prd · spec)과 창고 자료 — 프로젝트마다 새로. README · 빈 틀(_template_*)은 남긴다
    product = docs / "product"
    if product.exists():
        for p in product.iterdir():
            if p.is_file() and p.name != "README.md" and not p.name.startswith("_template"):
                p.unlink()
    for side in ("inbound", "outbound"):
        base = docs / "warehouse" / side
        if base.exists():
            for p in sorted(base.rglob("*"), reverse=True):
                if p.is_file() and p.name != "README.md":
                    p.unlink()


def first_documents(dest: Path, name: str, owner: str, today: dt.date) -> None:
    """새 프로젝트의 첫 요구 · 마스터플랜 v0.1 · 변경 이력 · PROJECT(북극성 · 판정 — 플랫폼 것을 물려받지 않는다)."""
    tpl = dest / "docs" / "_template_PROJECT.md"
    if tpl.exists():
        write(dest / "docs" / "PROJECT.md", tpl.read_text(encoding="utf-8").replace("{{NAME}}", name).replace("{{DATE}}", today.isoformat()))
    day = today.strftime("%y%m%d")
    rid = f"REQ-{day}-01"
    req = dest / "docs" / "requirement" / f"requirement_{day}_01.md"
    write(req, f"""# {rid} · {name} 프로젝트 시작

| 항목 | 내용 |
|---|---|
| 문서 ID | {rid} |
| 생성 | {today.isoformat()} · `new_project.py`(Nova 에서 생성) |
| 위치 | `docs/requirement/requirement_{day}_01.md` |
| 원천 | Nova 공통개발플랫폼의 새 프로젝트 생성 — 첫 요구 자리(원문을 채우면 이 칸도 사용자 원문으로 바꾼다) |
| 연결 | [master_plan](../plans/master_plan.md) · [PROJECT](../PROJECT.md) |
| 요청일 | {today.isoformat()} |
| 요청자 | {owner} |
| 원문 | "(이 프로젝트로 만들려는 것을 사용자 말 그대로 적는다)" |
| 상태 | 진행 중 |
| 계획 | [master_plan](../plans/master_plan.md) |

## 확인한 결정 (사용자 답변)
| 질문 | 결정 |
|---|---|
| 기반 | Nova 공통개발플랫폼에서 생성(`scripts/new_project.py`) — 문서 프로세스 · 백엔드 공통 · 인프라 생성기 · 디자인 시스템 · 웹/모바일 골격 |

## 요구사항 분해
| ID | 요구 | 수용 기준 | 관련 계획 |
|---|---|---|---|
| {rid}-1 | (첫 기능) | (확인 가능한 기준) | (plan_REQ_01) |

## 적용 · 결과
""")
    idx = dest / "docs" / "requirement" / "requirement_index.md"
    write(idx, idx.read_text(encoding="utf-8") + f"| [{rid}](requirement_{day}_01.md) | {today.isoformat()} | {name} 프로젝트 시작 | 진행 중 | [master_plan](../plans/master_plan.md) |\n")
    plans = dest / "docs" / "plans"
    write(plans / "master_plan.md", f"""# 마스터플랜 — {name}

| 항목 | 값 |
|---|---|
| 버전 | **v0.1** |
| 상태 | 초안(첫 요구를 정리한 뒤 v1.0 으로 채택) |
| 채택일 | - |
| 이전 정식 | - |
| 이력 | [master_plan_changelog.md](master_plan_changelog.md) |

## 1. 목표
(무엇을 누구를 위해 만드는가 — [{rid}](../requirement/requirement_{day}_01.md))

## 2. 범위
| 포함 | 제외 |
|---|---|

## 3. 구조
Nova 플랫폼 구조를 따른다(README · CLAUDE.md). 서비스 목록은 `packages/common-py/nova_common/services.json` — 새 서비스는 `python nova.py new-service`.
샘플(`services/sample` · `web/apps/app` 의 항목 화면 · KMP 항목 화면)은 첫 업무 서비스가 생기면 지운다.

## 4. 기술 스택
플랫폼 기준(ADR-001 · 002 · 003). 바꾸는 결정은 새 ADR 로.

## 5. 세부 계획
| 순서 | 계획 | 내용 | 선행 | 요구 |
|---|---|---|---|---|

## 6. 원칙
CLAUDE.md · docs/conventions/* 를 따른다.

## 7. 품질 게이트
- [ ] `python nova.py test` 통과
- [ ] `python nova.py lint` 통과
- [ ] 화면은 `python nova.py ui-smoke` 와 UX 점검(계획서 §4.1)

## 8. 위험
| 위험 | 대응 |
|---|---|

## 종료 조건 (exit)
이 판본이 끝나는 조건(1~7개 · 한 번 돌리거나 한 번 보고 답이 나오는 것). 모두 녹색이면 판본을 닫고(릴리스), 새로 보인 것은 다음 판본으로 — docs/plans/README.md §5.
| ID | 확인 | 기대 | 방식 | 판정 |
|---|---|---|---|---|
| E1 | python nova.py test | 통과 | 명령 | |
| E2 | python nova.py lint | 통과 | 명령 | |

## 하지 않는 것 (이 판본)
- (이번 판본에서 의도적으로 하지 않는 것 — 채운다)

## 공통 영역 완료 선언
모든 개발이 같은 것을 쓰게 하는 표준 · 공통 모듈. 전부 완료(또는 미해당)이고 증거가 있어야 worktree 로 갈라진다(`python nova.py parallel-gate`) — 먼저 갈라지면 묶음마다 화면 구성 · 부품 · 이름이 달라진다. 이 항목들은 판본 검사가 필수로 본다.
| 항목 | 상태 | 증거 |
|---|---|---|
| CI — test · lint 녹색 | 진행 | |
| DB · 마이그레이션 | 진행 | |
| 인증 · 권한 한 경로 | 진행 | |
| 화면 틀 · 공통 UI 부품 · 템플릿 · 디자인 토큰 | 진행 | |
| 서비스 사이 계약(API · 이벤트) | 진행 | |
| 공통 컴포넌트(라이브러리) — nova_common · @nova/sdk · kr.nova.shared | 진행 | |
| 공통 명명 규약 · 개념 원장 | 진행 | |

## 병렬 묶음
묶음 하나 = worktree 하나(`python nova.py worktree-new <묶음>`). 묶음끼리 경로가 겹치면 안 된다.
| 묶음 | 경로 | 담당 REQ | 선행 묶음 |
|---|---|---|---|
""")
    # 릴리스 원장은 비운 채 시작한다 — 플랫폼의 판본 · 종료 조건을 물려받지 않는다(첫 판본은 release draft 로)
    write(dest / "docs" / "releases" / "releases.json", '{\n  "releases": []\n}\n')
    write(plans / "master_plan_changelog.md", f"""# 마스터플랜 버전 이력

| 버전 | 상태 | 날짜 | 바뀐 것 | 근거 | 원본 |
|---|---|---|---|---|---|
| v0.1 | 초안 | {today.isoformat()} | Nova 에서 생성 | [{rid}](../requirement/requirement_{day}_01.md) | [master_plan.md](master_plan.md) |
""")


def sub_file(path: Path, pattern: str, repl: str, *, flags: int = 0) -> None:
    """정규식 치환 — 원본 브랜드가 무엇이든(Nova 또는 이미 생성된 프로젝트) 같은 자리를 바꾼다. 못 찾으면 실패."""
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(pattern, lambda _m: repl, text, count=1, flags=flags)
    if n == 0:
        raise SystemExit(f"치환 자리 없음: {path} — {pattern}")
    write(path, new)


def personalize(dest: Path, meta: dict, app_id: str) -> None:
    name, slug = meta["name"], meta["slug"]
    q = json.dumps(name, ensure_ascii=False)
    write(dest / "nova.project.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    # 웹 앱 브랜드
    app = dest / "web" / "apps" / "app" / "lib" / "app.ts"
    sub_file(app, r'brand: "[^"]*"', f"brand: {q}")
    sub_file(app, r'product: "[^"]*"', 'product: ""')
    sub_file(app, r'footer: "[^"]*"', f"footer: {q}")
    sub_file(dest / "web" / "apps" / "app" / "app" / "layout.tsx", r'Metadata = \{ title: "[^"]*"', f"Metadata = {{ title: {q}")
    shell = dest / "docs" / "plans" / "mockups" / "_shell.json"
    d = json.loads(shell.read_text(encoding="utf-8"))
    d["brand"] = name
    for a in d["apps"].values():
        a["product"] = ""
    write(shell, json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    # 모바일 앱 이름 · ID
    kmp = dest / "apps" / "kmp"
    sub_file(kmp / "settings.gradle.kts", r'rootProject\.name = "[^"]*"', f'rootProject.name = "{slug}-kmp"')
    cab = kmp / "composeApp" / "build.gradle.kts"
    sub_file(cab, r'"setNamespace"\("[^"]*"\)', f'"setNamespace"("{app_id}")')
    sub_file(cab, r'"setApplicationId"\("[^"]*"\)', f'"setApplicationId"("{app_id}")')
    sub_file(cab, r'packageName = "[^"]*"', f'packageName = "{re.sub(r"[^A-Za-z0-9]", "", slug.title()) or "App"}"')
    sub_file(kmp / "composeApp" / "src" / "desktopMain" / "kotlin" / "kr" / "nova" / "app" / "Main.kt", r'title = "[^"]*"', f"title = {q}")
    # 작업 규칙 머리 — 첫 줄(제목)과 첫 문단을 바꾼다
    claude = dest / "CLAUDE.md"
    lines = claude.read_text(encoding="utf-8").split("\n")
    lines[0] = f"# {name} — 저장소 작업 규칙 (Nova 공통개발플랫폼 기반)"
    first = next(i for i in range(1, len(lines)) if lines[i].strip())
    lines[first] = (f"{name} 은(는) Nova 공통개발플랫폼에서 생성한 프로젝트다. 구조 · 규칙 · 도구는 플랫폼을 따르고, 업무는 요구 → 계획 → task 로 쌓는다. "
                    "계획: [`docs/plans/master_plan.md`](docs/plans/master_plan.md). 프로젝트 메타: [`nova.project.json`](nova.project.json).")
    write(claude, "\n".join(lines))
    write(dest / "README.md", f"""# {name}

> Nova 공통개발플랫폼에서 생성한 프로젝트. 작업 규칙은 [CLAUDE.md](CLAUDE.md), 계획은 [master_plan](docs/plans/master_plan.md).

## 빠른 시작
```bash
python nova.py doctor      # 도구 점검 (uv · git · node · JDK 21)
python nova.py install     # uv sync → .venv
python nova.py test        # 전체 테스트
python nova.py lint        # 생성물 · 문서 · 원장 검사
python nova.py run         # 게이트웨이 http://localhost:8080/v1
python nova.py web         # 웹 앱
```

## 일하는 방식
요청 → `/req-new` → `/plan-new`(§4 화면 미리보기 + UX 점검) → 구현 · 테스트 → `/history-new` → 커밋 · `git_record.py` → `/session-end`

## 문서 지도
| 경로 | 내용 |
|---|---|
| [docs/requirement](docs/requirement/requirement_index.md) | 요구사항 |
| [docs/plans](docs/plans/README.md) | 계획 규칙 · 마스터플랜 · 세부 계획 · task |
| [docs/conventions](docs/conventions/) | UI · UX(닐슨 휴리스틱) · 백엔드 · Git 규약 |
| [docs/adr](docs/adr/README.md) | 구조 결정(플랫폼 결정 ADR-001~ 포함) |
""")


LINK = re.compile(r"\]\(([^)#\s]+\.md)(#[^)]*)?\)")


def relink_platform_docs(dest: Path, source: str) -> int:
    """물려받은 문서(ADR · 규약 등)가 비워진 플랫폼 기록(요구 · 계획 · 이력)을 가리키면 Nova 원본 저장소 주소로 바꾼다.
    근거를 끝까지 따라갈 수 있게(링크가 깨지지 않게). 바꾼 링크 수를 돌려준다."""
    if not source:
        return 0
    base = source.rstrip("/") + "/blob/main/"
    n = 0
    for md in [*dest.glob("*.md"), *(dest / "docs").rglob("*.md"), *(dest / ".claude").rglob("*.md")]:
        text = md.read_text(encoding="utf-8")

        def fix(m: re.Match) -> str:
            nonlocal n
            target, anchor = m.group(1), m.group(2) or ""
            if target.startswith(("http:", "https:")) or (md.parent / target).resolve().exists():
                return m.group(0)
            orig = (ROOT / md.parent.relative_to(dest) / target).resolve()
            if not orig.exists():
                return m.group(0)
            n += 1
            return f"]({base}{orig.relative_to(ROOT).as_posix()}{anchor})"

        new = LINK.sub(fix, text)
        if new != text:
            write(md, new)
    return n


def regenerate(dest: Path) -> None:
    """새 프로젝트 기준으로 생성물 · 원장 — 그 프로젝트의 nova_common 을 쓴다(PYTHONPATH)."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": os.pathsep.join([str(dest / "packages" / "common-py"), str(dest / "scripts")])}
    by = project().get("owner", "nova")
    for script, args in (("gen_tokens.py", []), ("gen_k3s.py", []), ("gen_dashboards.py", []),
                         ("registry.py", ["sync", "--by", by, "--note", "Nova 에서 생성 — 초기 등록"]), ("ledgers.py", []),
                         ("checklist.py", ["build"]), ("warehouse.py", ["out"]), ("release.py", ["changelog"])):
        r = subprocess.run([sys.executable, str(dest / "scripts" / script), *args], cwd=dest, env=env,
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise SystemExit(f"{script} 실패:\n{r.stdout}\n{r.stderr}")


def _git_out(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    except OSError:          # git 이 설치되지 않은 PC — 빈 값(호출부가 기준선 없이 만들고 upstream plan 이 경고한다)
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def upstream_meta(*, tag: str = "", base: str | None = None, root: Path = ROOT) -> dict:
    """새 프로젝트가 판본을 받을 상류 — url 은 Nova 원격(없으면 이 저장소 경로), base 는 받은 판본의 커밋(기본: 지금 HEAD),
    tag 는 받은 판본 이름(태그에서 만들었을 때). `python nova.py upstream plan <태그>` 가 base 를 3-way 의 기준선으로 쓴다."""
    url = _git_out(root, "config", "--get", "remote.origin.url") or (project().get("git_remote", "") if root == ROOT else "") or root.as_posix()
    out = {"url": url, "base": _git_out(root, "rev-parse", "HEAD") if base is None else base}
    if tag:
        out["tag"] = tag
    return out


def pick_ref(ref: str | None, root: Path = ROOT) -> str:
    """어느 판본에서 만들까 — 주면 그대로, 없으면 최신 정식 태그(rc 제외), 태그가 하나도 없으면 경고하고 HEAD(작업 트리)."""
    if ref:
        return ref
    latest = versions.latest_formal(versions.local_tags(root))
    if not latest:
        print("⚠ 정식 태그가 없다 — 작업 트리(HEAD)에서 만든다. 판본을 낸 뒤에는 최신 정식 태그에서 만든다(release ship)")
        return "HEAD"
    return latest


def dirty_common(root: Path = ROOT) -> list[str]:
    """커밋하지 않은 공통부 변경(추적 안 하는 새 파일 포함). 작업 트리에서 만들면 이것들이 판본 아닌 내용으로 실린다(T07-4.09).
    root 가 저장소 맨 위가 아니면 빈 목록 — 상위 저장소의 변경을 잘못 빌리지 않는다."""
    if not versions.is_toplevel(root):
        return []
    r = subprocess.run(["git", "status", "--porcelain", "-z", "-uall"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        return []
    items, parts, i = [], r.stdout.split("\0"), 0
    while i < len(parts):
        e = parts[i]
        if len(e) > 3:
            items.append(e[3:])
            if e[0] in "RC":   # 이름 바꾸기 · 복사는 다음 칸이 옛 이름
                i += 1
        i += 1
    return sorted(p for p in items if upstream.in_scope(p))


def add_upstream_remote(dest: Path, url: str) -> None:
    """복제본에 상류 git 원격 'upstream' 을 단다 — upstream tags · plan 이 이 주소로 판본을 본다. 이미 있으면 그대로."""
    if not url or _git_out(dest, "remote", "get-url", "upstream"):
        return
    subprocess.run(["git", "remote", "add", "upstream", url], cwd=dest, check=True, capture_output=True)


def export_ref(root: Path, ref: str, out: Path) -> None:
    """ref(태그 · 커밋)의 추적 파일 내용만 out 에 푼다(git archive — worktree 를 만들지 않는다)."""
    import io
    import tarfile
    r = subprocess.run(["git", "archive", "--format=tar", ref], cwd=root, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"✗ git archive {ref} 실패: {r.stderr.decode('utf-8', 'replace').strip()}")
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        tar.extractall(out, filter="data")


def create_from_ref(dest: Path, ref: str, *, root: Path = ROOT, name: str, slug: str, owner: str | None = None,
                    remote: str | None = None, registry: str | None = None, domain: str | None = None,
                    app_id: str | None = None, git: bool = True, tag: str | None = None, url: str | None = None) -> Path:
    """판본(ref)의 내용으로 새 프로젝트를 만든다 — 그 판본의 생성기(scripts/new_project.py)를 그 판본의 파일 위에서 돌린다.
    지금 생성기로 옛 판본 파일을 다루면 판본마다 다른 파일 구성에서 깨진다(생성기와 내용은 같은 판본이어야 한다).
    끝나면 upstream 을 {url, base: 판본 커밋, tag} 로 바로잡는다(옛 생성기는 임시 폴더를 상류로 적는다)."""
    dest = dest.resolve()
    commit = _git_out(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    if not commit:
        raise SystemExit(f"✗ 판본 {ref} 을(를) 찾지 못했다 — git tag --list 로 확인한다")
    label = tag if tag is not None else (ref if not re.fullmatch(r"[0-9a-f]{7,64}", ref) else "")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nova-src-", dir=dest.parent) as tmp:
        src = Path(tmp) / "nova"
        export_ref(root, commit, src)
        gen = src / "scripts" / "new_project.py"
        if not gen.exists():
            raise SystemExit(f"✗ 판본 {ref} 에 scripts/new_project.py 가 없다")
        args = [str(dest), "--name", name, "--slug", slug, "--no-git"]
        for flag, v in (("--owner", owner), ("--remote", remote), ("--registry", registry), ("--domain", domain), ("--app-id", app_id)):
            if v:
                args += [flag, v]
        if "--ref" in gen.read_text(encoding="utf-8"):
            args += ["--ref", "HEAD"]   # 풀어 놓은 폴더 자신에서 만든다(그 생성기가 다시 태그를 찾지 않게)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        p = subprocess.run([sys.executable, str(gen), *args], cwd=src, env=env, capture_output=True, text=True, encoding="utf-8")
        if p.returncode != 0:
            raise SystemExit(f"✗ 판본 {ref} 의 생성기가 실패했다:\n{p.stdout}\n{p.stderr}")
    meta_p = dest / "nova.project.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    u = upstream_meta(tag=label, base=commit, root=root)
    if url:
        u["url"] = url
    meta["upstream"] = u
    write(meta_p, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    if git:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=True)
        if remote:
            subprocess.run(["git", "remote", "add", "origin", remote], cwd=dest, check=True)
        add_upstream_remote(dest, u["url"])
    return dest


def create(dest: Path, name: str, slug: str, *, owner: str | None = None, remote: str | None = None, registry: str | None = None,
           domain: str | None = None, app_id: str | None = None, git: bool = True, today: dt.date | None = None,
           ref: str | None = None) -> Path:
    """ref: 만들 판본 — 없으면 최신 정식 태그(규약 versioning.md §6), "HEAD" 면 지금 작업 트리(경고)."""
    if not SLUG.match(slug):
        raise SystemExit(f"slug 는 영문 소문자 · 숫자 · 하이픈 2~31자(예: shop): {slug}")
    dest = dest.resolve()
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"대상 폴더가 비어 있지 않습니다: {dest}")
    if ROOT == dest or ROOT in dest.parents:
        first = dest.relative_to(ROOT).parts[0]
        if not (first in SKIP_DIRS or first.startswith(".pytest_tmp")):  # 복사에서 빠지는 폴더(테스트 임시 등) 안은 허용
            raise SystemExit("대상 폴더는 Nova 저장소 밖이어야 합니다")
    explicit = ref
    ref = pick_ref(ref)
    if ref != "HEAD":
        print(f"■ 판본 {ref} 에서 만든다(작업 트리가 아니라 그 판본의 내용) — 작업 트리에서 만들려면 --ref HEAD")
        return create_from_ref(dest, ref, name=name, slug=slug, owner=owner, remote=remote, registry=registry, domain=domain,
                               app_id=app_id, git=git)
    if explicit == "HEAD":
        print("⚠ --ref HEAD — 정식 판본이 아니라 지금 작업 트리에서 만든다(upstream.tag 가 비고 base 는 HEAD 커밋)")
    dirty = dirty_common()
    if dirty:
        print(f"⚠ 커밋하지 않은 공통부 변경 {len(dirty)}개가 복제본에 실린다 — base(HEAD)와 내용이 달라 upstream plan 에서 surface 로 잡힌다:")
        for p in dirty[:20]:
            print(f"    {p}")
        if len(dirty) > 20:
            print(f"    외 {len(dirty) - 20}개 (nova.project.json upstream.uncommitted 에 전부 기록)")
    today = today or dt.date.today()
    base = project()
    platform_source = (base.get("platform") or {}).get("source") or base.get("git_remote", "")
    account = "example"
    m = re.search(r"github\.com[/:]([^/]+)/", remote or base.get("git_remote", ""))
    if m:
        account = m.group(1)
    meta = {**base, "name": name, "slug": slug, "description": f"{name} — Nova 공통개발플랫폼 기반",
            "owner": owner or base.get("owner", ""), "git_remote": remote or "",
            "image_registry": registry or f"ghcr.io/{account}/{slug}", "domain": domain or f"{slug}.local",
            "label_domain": f"{slug}.dev",
            # 판본은 새 프로젝트의 것 — Nova 판본을 물려받으면 첫 운영 이미지 태그가 남의 번호가 된다(REQ-261104-10-6)
            "version": "0.1.0",
            # 표준 판정은 플랫폼 기본값을 물려받되 '다시 판정할 것'으로 표시(docs/std/README.md)
            "standards": {k: {**v, "by": "platform-default", "date": today.isoformat(),
                              "reason": f"Nova 기본 판정을 물려받음 — 첫 계획에서 다시 판정: {v.get('reason', '')}"}
                          for k, v in base.get("standards", {}).items()},
            "packs": [],
            # 디자인 킷은 기본 nova 로 시작한다 — 원본이 다른 킷을 골랐어도 물려받지 않는다(체크리스트 · /foundation 에서 다시 고른다,
            # REQ-261106-04). 생성물은 아래 regenerate 가 이 값으로 다시 만든다
            "design": {"kit": "nova", "date": today.isoformat(), "by": "platform-default", "source": "default"},
            # 규모 프로파일 — 복제본은 product 로 시작한다. 작으면 첫 계획에서 lite 로 내린다(REQ-261104-17-5)
            "profile": {"value": "product", "why": "Nova 복제본 기본 — 첫 계획에서 python nova.py profile suggest 로 다시 판정",
                        "date": today.isoformat(), "history": []},
            # 플랫폼 원본 — 생성된 프로젝트에서 다시 만들어도 Nova 원본 저장소를 가리킨다
            "platform": {"name": "Nova", "source": platform_source, "created": today.isoformat()},
            # 상류 판본 받기(scripts/upstream.py)의 기준선 — 복제본에서 다시 만들면 그 복제본이 상류가 된다
            "upstream": {**upstream_meta(), **({"uncommitted": dirty} if dirty else {})}}
    shutil.copytree(ROOT, dest, ignore=ignore, dirs_exist_ok=True)
    reset_docs(dest)
    personalize(dest, meta, app_id or f"kr.{re.sub(r'[^a-z0-9]', '', slug)}.app")
    first_documents(dest, name, meta["owner"], today)
    relink_platform_docs(dest, platform_source)
    regenerate(dest)
    if git:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=True)
        if remote:
            subprocess.run(["git", "remote", "add", "origin", remote], cwd=dest, check=True)
        add_upstream_remote(dest, meta["upstream"]["url"])
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dest")
    ap.add_argument("--name", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--owner")
    ap.add_argument("--remote")
    ap.add_argument("--registry")
    ap.add_argument("--domain")
    ap.add_argument("--app-id")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--ref", help="만들 판본(태그 · HEAD) — 없으면 최신 정식 태그, HEAD 는 지금 작업 트리(경고)")
    a = ap.parse_args(argv)
    dest = create(Path(a.dest), a.name, a.slug, owner=a.owner, remote=a.remote, registry=a.registry, domain=a.domain,
                  app_id=a.app_id, git=not a.no_git, ref=a.ref)
    if a.setup:
        subprocess.run(["uv", "sync", "--all-packages"], cwd=dest, check=True)
        subprocess.run([shutil.which("npm") or "npm", "install"], cwd=dest / "web", check=True)
    print(f"✓ {a.name} 프로젝트를 만들었습니다: {dest}")
    print("다음:")
    print(f"  cd {dest}")
    print("  python nova.py install && python nova.py test && python nova.py lint")
    print("  docs/requirement 의 첫 요구 원문을 채우고 /plan-new 로 첫 계획을 만든다")
    if a.remote:
        print("  첫 커밋 후 git push -u origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
