#!/usr/bin/env python3
"""버전 릴리스 — 판본마다 목표 · 종료 조건 · 하지 않는 것을 정하고, 조건이 모두 녹색일 때만 낸다(ADR-008 · 규약 docs/conventions/versioning.md).

  python nova.py release status                       판본 목록(목표일 · 마스터플랜) · 지금 draft
  python nova.py release suggest                      마지막 정식 태그 뒤 커밋 종류로 최소 올림(MAJOR · MINOR · PATCH) 제안
  python nova.py release draft 0.2.0 --goal "<한두 문장>" [--req REQ-…] [--due YYYY-MM-DD] [--masterplan v1.3]
  python nova.py release ship 0.2.0                   종료 조건 실제 판정 → 모두 녹색이면 nova.project.json version · 생성물 재생성 · shipped
                                                      → CHANGELOG → 판본 커밋 → 태그 v0.2.0 (docs/releases/ 밖 변경이 있으면 거부 ·
                                                      원장 판본이 최소 올림보다 낮으면 거부)
  python nova.py release publish 0.2.0 [--dry]        GitHub Release 공개(gh release create — 사람 확인 뒤에만 실행. --dry 는 할 일만 출력)
  python nova.py release changelog                    루트 CHANGELOG.md 다시 만들기(생성물)
  python nova.py release check                        형식 검사 · CHANGELOG 최신(lint)
  python nova.py release checkpoint "<사유>"           되돌릴 지점 — 판정 없이 지금 HEAD 에 주석 태그 checkpoint/YYMMDD-NN · 사건 원장 한 줄(커밋)
                                                      (커밋하지 않은 변경이 하나라도 있으면 거부 · 정식 판본이 아니다 · 원격 푸시는 안내만)
  python nova.py release rollback <태그> [--yes]       그 지점으로 코드 경로만 되돌리는 새 커밋 — 기본은 할 일만 보인다.
                                                      --yes: 지금 HEAD 를 discarded/<YYMMDD>-<태그 끝> 브랜치로 보존 → 되돌림 커밋 → 사건 원장
                                                      (기록 문서 · 원장 · 봉인은 그대로 — RECORD_PATHS · 강제 푸시 없음)

판본 번호: X.Y.Z(정식) · X.Y.Z-rc.N(사전 판본 — 공개하면 prerelease). 규칙은 docs/conventions/versioning.md.
원천: docs/releases/releases.json(상태 — 손으로 고쳐도 된다: 종료 조건 · 하지 않는 것 · 판정 · due · masterplan)
노트: docs/releases/v<버전>.md(사람이 쓴다 — 새로운 것 · 바뀐 것 · 고친 것 · 복제본이 받을 때 · 올리는 법 · 되돌리기). 태그를 원격에 올리는 것은 사람 확인 뒤.
사건 원장: docs/releases/checkpoints.jsonl(추가 전용 JSONL — checkpoint · rolled_back 사건 한 줄씩, ADR-004 · ADR-015)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goals  # noqa: E402
import progress  # noqa: E402
import versions  # noqa: E402
from novalib import ROOT, git, require_main, write  # noqa: E402

REL = ROOT / "docs" / "releases"
LEDGER = REL / "releases.json"
GOAL_MAX = 300
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MASTERPLAN = re.compile(r"^v\d+\.\d+$")
PLACEHOLDER = re.compile(r"^\s*\(.*채운다\s*\)\s*$")  # draft 가 넣는 자리표시 — 그대로면 아직 정하지 않은 것
NOTES_DIR = "docs/releases/"                        # ship 전에 바뀌어 있어도 되는 곳(노트 · 판정 칸) — 판본 커밋에 함께 담는다
CHANGELOG = "CHANGELOG.md"                          # 원장 · 노트의 생성 보기 — ship 이 다시 만들어 판본 커밋에 담는다
# 노트에서 반드시 채울 절 — 자리표시 '(…)' 로 시작하면 아직 쓰지 않은 것
REQUIRED_NOTES = (
    ("복제본이 받을 때", "예상 충돌 · 올리는 법(upstream plan 에서 surface 가 날 곳 · 손 마이그레이션 유무)을 적는다"),
    ("되돌리기", "태그 · 데이터 되돌림 가능 여부 · 확인 지점을 적는다"),
)
# CHANGELOG 로 옮기는 노트 절 → Keep a Changelog 칸
CHANGE_SECTIONS = (("새로운 것", "추가 (Added)"), ("바뀐 것", "변경 (Changed)"), ("고친 것", "수정 (Fixed)"))
CC = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<bang>!)?:")
CHECKPOINTS = "docs/releases/checkpoints.jsonl"     # 체크포인트 · 되돌리기 사건 원장(추가 전용 — 쌓이는 사건은 JSONL, ADR-004)
CHECKPOINT_TAG = "checkpoint/{d}-{n:02d}"
# 되돌리기가 손대지 않는 경로 — 이 밖은 전부 '코드 경로'다(ADR-015). 코드 쪽을 목록으로 적지 않는 것은
# 새 프로젝트가 새 최상위 폴더를 만들어도 빠짐없이 되돌리기 위해서다. 이력은 앞으로만 간다:
#   docs/             번호 기록(요구 · 계획 · task · 이력 · git · ADR) · 마스터플랜 봉인 archive/seals.json · 판본 원장 · 사건 원장
#                     — 되돌리면 번호가 비고 봉인 해시가 어긋나 lint 가 깨진다. 잘못된 변경을 적은 기록도 남아야 한다
#   registry/         생성물 · 명명 · 개념 원장(추가 전용 이력) — 코드와 어긋나면 registry.py sync 로 앞으로 맞춘다
#   .claude/soul/ · SOUL.md · IDENTITY.md   정체성 — 사람이 명시로 지시할 때만 바뀐다(ADR-007)
#   .claude/state/    훅 기록(기계마다 로컬 — 추적하지 않지만 혹시 추적돼도 건드리지 않는다)
#   CHANGELOG.md      docs/releases 의 생성 보기 — 원천(docs)을 두므로 보기도 둔다(release check)
#   nova.project.json 판본 번호 · 표준 판정 · 상류 기록 — 낸 판본(releases.json shipped)과 같이 앞으로만 간다
RECORD_PATHS = ("docs/", "registry/", ".claude/soul/", ".claude/state/", "SOUL.md", "IDENTITY.md", "CHANGELOG.md",
                "nova.project.json")


def is_record(path: str) -> bool:
    """되돌리지 않는 기록 경로인가(RECORD_PATHS) — 아니면 코드 경로."""
    p = path.replace("\\", "/")
    return any(p == k or (k.endswith("/") and p.startswith(k)) for k in RECORD_PATHS)


def load(root: Path = ROOT) -> dict:
    p = root / "docs" / "releases" / "releases.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"releases": []}


def save(d: dict, root: Path = ROOT) -> None:
    write(root / "docs" / "releases" / "releases.json", json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def req_status(req: str, root: Path) -> str:
    idx = (root / "docs" / "requirement" / "requirement_index.md").read_text(encoding="utf-8")
    m = re.search(rf"\[{re.escape(req)}\][^\n]*?\|\s*([^|]+?)\s*\|\s*[^|]*\|\s*$", idx, re.M)
    return m.group(1) if m else "없음"


def check(d: dict, root: Path = ROOT) -> list[str]:
    errs, drafts = [], [r for r in d.get("releases", []) if r.get("status") == "draft"]
    if len(drafts) > 1:
        errs.append(f"draft 판본이 {len(drafts)}개 — 지금 만드는 판본은 하나다")
    seen = set()
    for r in d.get("releases", []):
        v, w = r.get("version", ""), f"releases.json v{r.get('version', '?')}"
        if not versions.valid(v) or v in seen:
            errs.append(f"{w}: 버전은 X.Y.Z(사전 판본은 X.Y.Z-rc.N)이고 겹치지 않는다")
        seen.add(v)
        if r.get("status") not in ("draft", "shipped"):
            errs.append(f"{w}: status 는 draft · shipped")
        g = r.get("goal", "")
        if not g.strip() or len(g) > GOAL_MAX:
            errs.append(f"{w}: 목표(goal)는 1~{GOAL_MAX}자 — 길면 목표 자체가 계속 자란다")
        if r.get("due") and not DATE.match(r["due"]):
            errs.append(f"{w}: 목표일(due)은 YYYY-MM-DD — 비워 두어도 된다")
        if r.get("masterplan") and not MASTERPLAN.match(r["masterplan"]):
            errs.append(f"{w}: masterplan 은 마스터플랜 판본 이름(예: v1.3)")
        if not r.get("not_doing"):
            errs.append(f"{w}: 하지 않는 것(not_doing)을 1개 이상 — 무엇을 안 하는지가 범위를 지킨다")
        elif any(PLACEHOLDER.match(str(x)) for x in r["not_doing"]):
            errs.append(f"{w}: 하지 않는 것(not_doing)이 자리표시 '(… 채운다)' 그대로 — 실제로 안 하는 것을 적는다")
        errs += goals.lint(r.get("exit", []), w)
        if r.get("status") == "shipped":
            notes = root / "docs" / "releases" / f"v{v}.md"
            if not notes.exists():
                errs.append(f"{w}: 릴리스 노트 docs/releases/v{v}.md 가 없다")
    errs += changelog_errors(d, root)
    return errs


def changelog_errors(d: dict, root: Path) -> list[str]:
    p = root / CHANGELOG
    want = changelog(d, root)
    if not p.exists():
        return [f"{CHANGELOG} 이 없다 → python nova.py release changelog"]
    if p.read_text(encoding="utf-8").replace("\r\n", "\n") != want:
        return [f"{CHANGELOG} 이 원장 · 노트와 다르다(생성물 — 손으로 고치지 않는다) → python nova.py release changelog"]
    return []


# ───────────────────────── 노트 · CHANGELOG
def note_sections(text: str) -> dict[str, str]:
    """노트의 '## 제목' → 본문."""
    out = {}
    for m in re.finditer(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.S | re.M):
        out[m.group(1).strip()] = m.group(2)
    return out


def note_errors(text: str) -> list[str]:
    secs = note_sections(text)
    errs = []
    for name, how in REQUIRED_NOTES:
        body = next((b for h, b in secs.items() if h.startswith(name)), None)
        if body is None:
            errs.append(f"릴리스 노트에 '{name}' 절이 없다 — _template.md 의 절을 옮겨 {how}")
        elif body.strip().startswith("("):
            errs.append(f"릴리스 노트의 '{name}' 절이 자리표시 그대로 — {how}")
    return errs


def _bullets(body: str) -> list[str]:
    return [ln.rstrip() for ln in body.splitlines() if re.match(r"^\s*- \S", ln)]


def changelog(d: dict, root: Path = ROOT) -> str:
    """루트 CHANGELOG.md(Keep a Changelog 형식) — 맨 위 Unreleased = draft, 아래로 낸 판본(새것부터)."""
    rels = d.get("releases", [])

    def meta(r: dict) -> str:
        bits = [f"목표일 {r['due']}" if r.get("due") else "", f"마스터플랜 {r['masterplan']}" if r.get("masterplan") else "",
                ("묶인 요구 " + " · ".join(r["reqs"])) if r.get("reqs") else ""]
        return " · ".join(b for b in bits if b)

    def changes(v: str) -> list[str]:
        p = root / "docs" / "releases" / f"v{v}.md"
        if not p.exists():
            return []
        secs, out = note_sections(p.read_text(encoding="utf-8")), []
        for name, head in CHANGE_SECTIONS:
            items = next((_bullets(b) for h, b in secs.items() if h.startswith(name)), [])
            if items:
                out += ["", f"### {head}", *items]
        return out

    lines = ["# 변경 이력 (CHANGELOG)", "",
             "> 생성물 — 원천은 판본 원장 `docs/releases/releases.json` 과 노트 `docs/releases/v<버전>.md`. 손으로 고치지 않는다: `python nova.py release changelog`",
             "> 형식 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) · 번호 규칙 [판본 규약](docs/conventions/versioning.md)", "",
             "## [Unreleased]"]
    drafts = [r for r in rels if r.get("status") == "draft"]
    if not drafts:
        lines += ["", "열린 판본 없음 — `python nova.py release draft <버전> --goal …`"]
    for r in drafts:
        m = meta(r)
        lines += ["", f"다음 판본 v{r['version']}(draft{' · ' + m if m else ''}) — {r.get('goal', '')}", *changes(r["version"])]
    shipped = sorted((r for r in rels if r.get("status") == "shipped"), key=lambda r: versions.key(r["version"]), reverse=True)
    for r in shipped:
        v, m = r["version"], meta(r)
        lines += ["", f"## [{v}](docs/releases/v{v}.md) — {r.get('shipped', '')}{' (사전 판본)' if versions.is_rc(v) else ''}", "",
                  f"목표: {r.get('goal', '')}" + (f" ({m})" if m else ""), *changes(v), "",
                  f"되돌리기: [v{v} 노트 §되돌리기](docs/releases/v{v}.md#되돌리기)"]
    return "\n".join(lines) + "\n"


# ───────────────────────── 번호 제안
def suggest(root: Path = ROOT) -> dict:
    """마지막 정식 태그 뒤 커밋 제목(Conventional Commits)으로 최소 올림. 태그가 없으면 minimum 은 비운다(첫 판본은 자유)."""
    last = versions.latest_formal(versions.local_tags(root))
    res = {"last": last, "commits": 0, "counts": {}, "breaking": 0, "level": "", "minimum": ""}
    if not last:
        return res
    p = subprocess.run(["git", "log", "--no-merges", f"{last}..HEAD", "--format=%s%x1f%b%x1e"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"✗ git log {last}..HEAD 실패: {p.stderr.strip()}")
    level = 0
    for rec in (x.strip("\n") for x in p.stdout.split("\x1e")):
        if not rec.strip():
            continue
        subj, _, body = rec.partition("\x1f")
        m = CC.match(subj.strip())
        t = m.group("type") if m else "기타"
        res["commits"] += 1
        res["counts"][t] = res["counts"].get(t, 0) + 1
        if (m and m.group("bang")) or re.search(r"^BREAKING[ -]CHANGE:", body, re.M):
            res["breaking"] += 1
            level = 2
        elif t == "feat":
            level = max(level, 1)
    res["level"] = versions.LEVELS[level] if res["commits"] else ""
    res["minimum"] = versions.bump(last.removeprefix("v"), res["level"] or "patch")
    return res


def ship(version: str, root: Path = ROOT) -> dict:
    require_main("릴리스", root)
    d = load(root)
    r = next((x for x in d["releases"] if x["version"] == version), None)
    if not r or r["status"] != "draft":
        raise SystemExit(f"✗ draft 판본 v{version} 이 없다")
    errs = check({"releases": [r]}, root)
    errs = [e for e in errs if "릴리스 노트" not in e and CHANGELOG not in e]   # 노트는 아래서 · CHANGELOG 는 ship 이 다시 만든다
    notes = root / "docs" / "releases" / f"v{version}.md"
    if not notes.exists():
        errs.append(f"릴리스 노트 docs/releases/v{version}.md 를 먼저 쓴다(_template.md 복사)")
    else:
        errs += note_errors(notes.read_text(encoding="utf-8"))
    s = suggest(root)
    if s["minimum"] and versions.valid(version) and versions.core(version) < versions.core(s["minimum"]):
        errs.append(f"판본 v{version} 이 커밋 종류로 정한 최소 {s['minimum']} 보다 낮다({s['last']} 뒤 {s['level']} 올림 — "
                    f"feat {s['counts'].get('feat', 0)} · 깨짐 {s['breaking']}). 원장 판본 번호를 올린다(python nova.py release suggest)")
    for req in r.get("reqs", []):
        st = req_status(req, root)
        if not progress.is_done(st):  # 머리말 판정 — '완료(종료 조건 충족 …)' 도 완료다(REQ-261106-02-1)
            errs.append(f"묶인 요구 {req} 상태가 '{st}' — 완료되지 않았다")
    # 판본 커밋에는 이 판본의 것만 담는다 — docs/releases/ 밖 변경이 있으면 먼저 커밋하거나 치운다
    dirty = [p for p in changed_paths(root) if not p.startswith(NOTES_DIR) and p != CHANGELOG]
    if dirty:
        errs.append("docs/releases/ 밖에 커밋하지 않은 변경이 있다 — 먼저 커밋하거나 치운다: " + ", ".join(dirty[:10])
                    + (f" 외 {len(dirty) - 10}개" if len(dirty) > 10 else ""))
    if git("tag", "--list", f"v{version}", cwd=root):
        errs.append(f"태그 v{version} 이 이미 있다 — 판본 번호를 바꾸거나 태그를 확인한다")
    if errs:
        raise SystemExit("✗ 낼 수 없다:\n  " + "\n  ".join(errs))
    print(f"■ v{version} 종료 조건 판정")
    if not goals.report(goals.judge(r["exit"], root=root)):
        raise SystemExit("✗ 종료 조건이 녹색이 아니다 — 낼 수 없다")
    meta_p = root / "nova.project.json"
    before = meta_p.read_text(encoding="utf-8")
    meta = json.loads(before)
    meta["version"] = version
    write(meta_p, json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    # 원장을 shipped 로 쓰기 전에 재생성한다 — 생성기가 실패하면 meta 를 되돌리고 판본은 draft 로 남아 다시 ship 할 수 있다
    try:
        regen_infra(root)
    except SystemExit:
        write(meta_p, before)
        raise
    today = dt.date.today().isoformat()
    r.update(status="shipped", shipped=today, tag=f"v{version}")
    save(d, root)
    write(root / CHANGELOG, changelog(d, root))
    # 순서: 기록 · 재생성 → 커밋 → 태그(P-3) — 태그가 판본 기록 커밋을 가리켜야 되돌리기 지점이 그 판본의 이미지 태그와 맞는다
    try:
        git("add", "-A", cwd=root)
        git("commit", "-q", "-m", f"chore(release): v{version} 판본 기록 · 생성물 재생성", cwd=root)
    except RuntimeError as e:
        raise SystemExit(f"✗ 판본 커밋 실패 — 원장 · meta · 생성물은 기록됐다. 원인을 고치고 직접 커밋 → git tag -a {r['tag']}:\n{e}")
    try:
        git("tag", "-a", r["tag"], "-m", f"릴리스 {r['tag']} — {r['goal'][:80]}", cwd=root)
    except RuntimeError as e:
        raise SystemExit(f"✗ 태그 {r['tag']} 실패 — 판본 커밋은 됐다. 원인을 고치고 git tag -a {r['tag']} -m \"릴리스 {r['tag']}\":\n{e}")
    return r


def publish(version: str, root: Path = ROOT, dry: bool = False) -> list[str]:
    """GitHub Release 공개 — 낸(shipped) 판본만, 로컬 태그 · 노트가 있을 때. --verify-tag 로 원격에 태그가 없으면 gh 가 멈춘다
    (태그 없이 만들면 gh 가 기본 브랜치 끝에 새 태그를 찍는다 — 판본과 다른 커밋이 공개된다)."""
    d = load(root)
    r = next((x for x in d["releases"] if x["version"] == version), None)
    if not r or r.get("status") != "shipped":
        raise SystemExit(f"✗ v{version} 은 shipped 판본이 아니다 — release ship 으로 먼저 낸다")
    tag = r.get("tag") or f"v{version}"
    if not git("tag", "--list", tag, cwd=root):
        raise SystemExit(f"✗ 로컬에 태그 {tag} 이 없다 — release ship 이 만든다")
    notes = f"docs/releases/v{version}.md"
    if not (root / notes).exists():
        raise SystemExit(f"✗ 노트 {notes} 가 없다")
    cmd = ["gh", "release", "create", tag, "--verify-tag", "--title", tag, "--notes-file", notes]
    cmd += ["--prerelease"] if versions.is_rc(version) else ["--latest"]
    print(("■ (--dry) 할 일: " if dry else "■ 실행: ") + " ".join(cmd))
    if versions.is_rc(version):
        print("  사전 판본(prerelease) — release 브랜치(템플릿 기본 브랜치)는 움직이지 않는다")
    else:
        print("  공개되면 워크플로 .github/workflows/release-branch.yml 이 release 브랜치를 이 태그로 앞당긴다 → 템플릿 = 최신 정식본")
    if dry:
        print(f"  먼저: git push origin {tag}(사람 확인 뒤) — 원격에 태그가 없으면 --verify-tag 가 멈춘다")
        return cmd
    if not shutil.which("gh"):
        raise SystemExit("✗ gh(GitHub CLI)가 없다 — 설치 · gh auth login 뒤 다시")
    p = subprocess.run(cmd, cwd=root)
    if p.returncode != 0:
        raise SystemExit(f"✗ gh release create 실패(종료 {p.returncode}) — 원격 태그(git push origin {tag}) · gh auth status 를 확인한다")
    return cmd


# ───────────────────────── 체크포인트 · 되돌리기(ADR-015 · REQ-261106-02)
def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _require_clean(root: Path, what: str) -> None:
    """지점 · 되돌림 커밋에 남의 변경이 섞이지 않게 — docs/releases 안팎을 가리지 않고 하나라도 있으면 거부."""
    dirty = changed_paths(root)
    if dirty:
        raise SystemExit(f"✗ {what}: 커밋하지 않은 변경이 있다 — 먼저 커밋하거나 치운다: " + ", ".join(dirty[:10])
                         + (f" 외 {len(dirty) - 10}개" if len(dirty) > 10 else ""))


def append_event(root: Path, ev: dict) -> None:
    """사건 원장에 한 줄 덧붙인다(추가 전용 — 앞 줄은 고치지 않는다)."""
    p = root / CHECKPOINTS
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def checkpoint(reason: str, root: Path = ROOT, today: dt.date | None = None) -> str:
    """되돌릴 지점 — 종료 조건 판정 없이 지금 HEAD 에 주석 태그를 단다(빠른 지점 · 정식 판본 아님).
    순서: 태그(HEAD) → 사건 원장 한 줄 → 원장만 담은 커밋. 태그는 원장 커밋 앞을 가리킨다 — 지점 = 부른 순간의 상태."""
    require_main("릴리스 체크포인트", root)
    reason = reason.strip()
    if not reason:
        raise SystemExit('✗ 체크포인트 사유를 적는다 — 무엇 직전인지(예: "결제 스키마 마이그레이션 직전")')
    _require_clean(root, "체크포인트")
    d = (today or dt.date.today()).strftime("%y%m%d")
    nums = [int(m.group(1)) for t in git("tag", "--list", f"checkpoint/{d}-*", cwd=root).split()
            if (m := re.fullmatch(rf"checkpoint/{d}-(\d+)", t))]
    tag = CHECKPOINT_TAG.format(d=d, n=max(nums, default=0) + 1)
    head = git("rev-parse", "HEAD", cwd=root)
    git("tag", "-a", tag, "-m", f"체크포인트 {tag} — {reason}", head, cwd=root)
    append_event(root, {"event": "checkpoint", "at": _now(), "tag": tag, "commit": head, "reason": reason})
    try:
        git("add", "--", CHECKPOINTS, cwd=root)
        git("commit", "-q", "-m", f"chore(release): 체크포인트 {tag} — {reason[:60]}", cwd=root)
    except RuntimeError as e:
        raise SystemExit(f"✗ 사건 원장 커밋 실패 — 태그 {tag} 는 만들었다. 원인을 고친 뒤 {CHECKPOINTS} 를 직접 커밋한다:\n{e}")
    print(f"✓ 체크포인트 {tag} → {head[:7]} · 사건 원장 {CHECKPOINTS}(커밋)")
    print(f"  원격 보존은 사람 확인 뒤: git push origin {tag}  (main 커밋도 함께 올리려면 git push origin main {tag})")
    print(f"  잘못되면: python nova.py release rollback {tag}  (먼저 할 일을 보고 --yes)")
    return tag


def _diff(root: Path, a: str, b: str) -> list[tuple[str, str]]:
    """a → b 사이 바뀐 파일(상태, 경로). -z 로 읽어 한글 · 공백 경로가 따옴표로 바뀌지 않게, 이름 바꾸기는 삭제 + 추가로 본다."""
    p = subprocess.run(["git", "diff", "--name-status", "-z", "--no-renames", a, b], cwd=root,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"✗ git diff 실패: {p.stderr.strip()}")
    f = [x for x in p.stdout.split("\0") if x]
    return [(f[i][0], f[i + 1]) for i in range(0, len(f) - 1, 2)]


def _chunks(xs: list[str], n: int = 100):
    """Windows 명령줄 길이(약 32K) 안에 들도록 나눠 넘긴다."""
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def rollback(tag: str, root: Path = ROOT, yes: bool = False, today: dt.date | None = None) -> dict:
    """그 지점으로 코드 경로만 되돌리는 새 커밋(revert 방식 — 이력은 앞으로만 간다). 기본은 할 일만 보인다.
    --yes: ① 지금 HEAD 를 discarded/<YYMMDD>-<태그 끝> 으로 보존 ② 코드 경로를 지점 상태로(지점 뒤 새로 생긴 코드 파일은 삭제)
    ③ 사건 원장에 rolled_back ④ 한 커밋. 기록 경로(RECORD_PATHS)는 그대로 둔다. 원격 푸시 · 강제 푸시는 하지 않는다."""
    require_main("릴리스 되돌리기", root)
    p = subprocess.run(["git", "rev-parse", "--verify", "-q", f"refs/tags/{tag}^{{commit}}"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"✗ 태그 {tag} 가 없다 — 지점 목록: git tag --list \"checkpoint/*\" \"v*\"")
    point, head = p.stdout.strip(), git("rev-parse", "HEAD", cwd=root)
    if subprocess.run(["git", "merge-base", "--is-ancestor", point, head], cwd=root, capture_output=True).returncode != 0:
        raise SystemExit(f"✗ {tag} 는 지금 HEAD 의 조상이 아니다 — 이 갈래가 지나온 지점으로만 되돌린다")
    restore, delete, kept = [], [], []
    for st, path in _diff(root, point, head):
        if is_record(path):
            kept.append(path)
        elif st == "A":            # 지점 뒤에 새로 생긴 코드 파일 — 지운다
            delete.append(path)
        else:                      # 고쳤거나(M · T) 지웠다(D) — 지점 내용으로 되살린다
            restore.append(path)
    plan = {"tag": tag, "point": point, "head": head, "restore": restore, "delete": delete, "kept": kept}
    print(f"■ 되돌리기 {tag}({point[:7]}) ← 지금 HEAD {head[:7]}")
    print(f"  코드 경로 되돌림 {len(restore)} · 새 코드 파일 삭제 {len(delete)} · 그대로 둘 기록 경로 {len(kept)}")
    for label, xs in (("되돌림", restore), ("삭제", delete), ("그대로", kept)):
        for x in xs[:20]:
            print(f"    {label}  {x}")
        if len(xs) > 20:
            print(f"    {label}  … 외 {len(xs) - 20}개")
    if not (restore or delete):
        print("✓ 코드 경로가 이미 지점과 같다 — 할 일 없음")
        return plan
    d = (today or dt.date.today()).strftime("%y%m%d")
    branch = f"discarded/{d}-{tag.split('/')[-1]}"
    n = 2
    while git("branch", "--list", branch, cwd=root):    # 같은 날 같은 지점으로 두 번 — 앞 보존을 덮지 않는다
        branch = f"discarded/{d}-{tag.split('/')[-1]}-{n}"
        n += 1
    if not yes:
        print(f"  할 일만 보였다 — 실제로 하려면: python nova.py release rollback {tag} --yes")
        print(f"    (지금 HEAD 를 {branch} 로 보존 → 되돌림 커밋 → 사건 원장 {CHECKPOINTS})")
        return plan
    _require_clean(root, "되돌리기")
    ledger_existed = (root / CHECKPOINTS).exists()
    git("branch", branch, head, cwd=root)
    try:
        for c in _chunks(restore):
            git("checkout", point, "--", *c, cwd=root)
        for c in _chunks(delete):
            git("rm", "-q", "--", *c, cwd=root)
        append_event(root, {"event": "rolled_back", "at": _now(), "tag": tag, "point": point, "head_before": head,
                            "discarded": branch, "restored": restore, "deleted": delete})
        git("add", "--", CHECKPOINTS, cwd=root)
        git("commit", "-q", "-m", f"chore(release): 코드 경로를 {tag} 지점으로 되돌림 — 되돌림 {len(restore)} · 삭제 {len(delete)}"
            f" (폐기 보존 {branch})", cwd=root)
    except RuntimeError as e:
        # 시작할 때 작업 트리가 깨끗했으므로(_require_clean) 이 reset 이 지우는 것은 방금 한 되돌림뿐이다
        git("reset", "-q", "--hard", "HEAD", cwd=root)
        if not ledger_existed:
            (root / CHECKPOINTS).unlink(missing_ok=True)
        raise SystemExit(f"✗ 되돌리기 실패 — 작업 트리는 원래대로, 폐기 브랜치 {branch} 만 남았다(지워도 된다):\n{e}")
    plan["discarded"] = branch
    print(f"✓ 되돌림 커밋 {git('rev-parse', '--short', 'HEAD', cwd=root)} · 폐기 보존 {branch} → {head[:7]} · 사건 원장 rolled_back")
    print("  다음:")
    print("    python nova.py gen    — 되돌린 코드와 그대로 둔 원천 · 원장이 어긋날 수 있다(생성물 다시 만들기)")
    print("    python nova.py check  — 기록 문서가 지운 코드를 가리키면 docs_index · registry 가 잡는다 → 앞으로 고친다")
    print(f"    원격은 사람 확인 뒤: git push origin main  · 폐기 브랜치도 남기려면 git push origin {branch}")
    return plan


def changed_paths(root: Path) -> list[str]:
    """커밋하지 않은 변경(추적 안 하는 파일 포함) 경로.
    novalib.git 은 출력을 strip 해서 첫 줄의 상태 칸 공백(' M')이 사라진다 — -z 로 직접 읽는다."""
    p = subprocess.run(["git", "status", "--porcelain", "-z", "-uall"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit(f"✗ git status 실패: {p.stderr.strip()}")
    out, items = p.stdout.split("\0"), []
    i = 0
    while i < len(out):
        e = out[i]
        if len(e) > 3:
            items.append(e[3:])
            if e[0] in "RC":  # 이름 바꾸기 · 복사는 다음 칸이 옛 이름 — 건너뛴다
                i += 1
        i += 1
    return items


def regen_infra(root: Path = ROOT) -> None:
    """meta version 이 바뀌면 운영 이미지 태그 · Helm 판본이 바뀐다 — 생성물을 다시 만들어 판본과 태그를 한 커밋에 묶는다."""
    import os

    gen = root / "scripts" / "gen_k3s.py"
    if not gen.exists():  # 생성기가 없는 저장소(시험용 최소 저장소 등)는 다시 만들 것이 없다
        return
    p = subprocess.run([sys.executable, str(gen)], cwd=root, capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if p.returncode != 0:
        raise SystemExit(f"✗ 인프라 생성물 재생성(scripts/gen_k3s.py) 실패 — 판본은 draft 그대로:\n{(p.stderr or p.stdout).strip()}")
    print(p.stdout.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("status", "check", "suggest", "changelog"):
        sub.add_parser(n)
    dr = sub.add_parser("draft")
    dr.add_argument("version")
    dr.add_argument("--goal", required=True)
    dr.add_argument("--req", action="append", default=[])
    dr.add_argument("--due", default="", help="목표일 YYYY-MM-DD(선택 — 넘기면 남은 범위를 다음 판본으로)")
    dr.add_argument("--masterplan", default="", help="이 판본이 담는 마스터플랜 판본(예: v1.3)")
    sh = sub.add_parser("ship")
    sh.add_argument("version")
    pb = sub.add_parser("publish")
    pb.add_argument("version")
    pb.add_argument("--dry", action="store_true", help="할 일만 출력하고 gh 를 부르지 않는다")
    cp = sub.add_parser("checkpoint", help="되돌릴 지점 — 주석 태그 checkpoint/YYMMDD-NN · 사건 원장")
    cp.add_argument("reason", help="무엇 직전인지(예: 결제 스키마 마이그레이션 직전)")
    rb = sub.add_parser("rollback", help="지점으로 코드 경로만 되돌리는 새 커밋 — 기본은 할 일만")
    rb.add_argument("tag", help="체크포인트 또는 판본 태그(예: checkpoint/261106-01 · v0.1.0)")
    rb.add_argument("--yes", action="store_true", help="실제로 한다(폐기 브랜치 보존 → 되돌림 커밋 → 사건 원장)")
    a = ap.parse_args(argv)
    root = ROOT
    if a.cmd == "checkpoint":
        checkpoint(a.reason, root)
        return 0
    if a.cmd == "rollback":
        rollback(a.tag, root, yes=a.yes)
        return 0
    d = load(root)
    if a.cmd == "check":
        errs = check(d, root)
        for e in errs:
            print("✗", e)
        if not errs:
            print("✓ 릴리스 원장 정상 · CHANGELOG 최신")
        return 1 if errs else 0
    if a.cmd == "changelog":
        write(root / CHANGELOG, changelog(d, root))
        print(f"✓ {CHANGELOG} — 판본 {len(d['releases'])}개(원장 · 노트에서 생성)")
        return 0
    if a.cmd == "suggest":
        s = suggest(root)
        if not s["last"]:
            print("■ 정식 태그가 없다 — 첫 판본 번호는 자유(보통 0.1.0)")
            return 0
        kinds = " · ".join(f"{k} {n}" for k, n in sorted(s["counts"].items(), key=lambda x: -x[1])) or "없음"
        print(f"■ {s['last']} 뒤 커밋 {s['commits']}개 — {kinds} · 깨짐(! · BREAKING CHANGE) {s['breaking']}")
        print(f"  최소 올림: {s['level'] or '없음(커밋 없음)'} → 다음 판본은 {s['minimum']} 이상"
              + ("  (0.x 동안은 깨짐도 0.y 올림 — 규약 docs/conventions/versioning.md)" if s["level"] == "major" and s["last"].startswith("v0.") else ""))
        draft = next((r for r in d["releases"] if r["status"] == "draft"), None)
        if draft:
            low = versions.core(draft["version"]) < versions.core(s["minimum"])
            print(f"  원장 draft v{draft['version']} — " + ("✗ 최소보다 낮다(ship 이 거부한다)" if low else "✓ 충분하다"))
        return 0
    if a.cmd == "status":
        for r in d["releases"]:
            extra = " · ".join(x for x in (f"목표일 {r['due']}" if r.get("due") else "",
                                           f"마스터플랜 {r['masterplan']}" if r.get("masterplan") else "") if x)
            print(f"  v{r['version']} · {r['status']} · {r.get('shipped') or r.get('drafted', '')}"
                  + (f" · {extra}" if extra else "") + f" · {r['goal'][:60]}")
        if not d["releases"]:
            print("  판본 없음 — python nova.py release draft 0.1.0 --goal …")
        return 0
    if a.cmd == "draft":
        require_main("릴리스 draft")
        if any(r["version"] == a.version for r in d["releases"]):
            raise SystemExit(f"✗ v{a.version} 이 이미 있다")
        row = {"version": a.version, "status": "draft", "goal": a.goal, "reqs": a.req,
               "exit": [{"id": "E1", "check": "python nova.py test", "expect": "통과", "how": "명령", "judged": ""},
                        {"id": "E2", "check": "python nova.py lint", "expect": "통과", "how": "명령", "judged": ""}],
               "not_doing": ["(이 판본에서 하지 않는 것 — 채운다)"], "drafted": dt.date.today().isoformat(),
               "shipped": "", "tag": ""}
        row.update({k: v for k, v in (("due", a.due), ("masterplan", a.masterplan)) if v})
        d["releases"].append(row)
        save(d)
        write(root / CHANGELOG, changelog(d, root))
        print(f"✓ v{a.version} draft — docs/releases/releases.json 에서 종료 조건 · 하지 않는 것을 채우고, 노트 docs/releases/v{a.version}.md 를 쓴다")
        return 0
    if a.cmd == "publish":
        publish(a.version, root, dry=a.dry)
        return 0
    r = ship(a.version)  # 기록 · 재생성 → 커밋 → 태그. 어느 단계든 실패하면 SystemExit(종료 1)
    print(f"✓ v{a.version} shipped · 판본 커밋 · 태그 {r['tag']}"
          f"\n  다음: git 기록(git_record.py) → 확인 뒤 git push origin main {r['tag']} → release publish {a.version}(GitHub Release)"
          " · 다음 판본 draft 를 연다(release draft …)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
