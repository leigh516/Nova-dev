#!/usr/bin/env python3
"""기록 분량 정하기(/docs-write · /round-close) — 바뀐 파일로 등급을 제안하고, tasks 의 남은 칸을 3갈래로 대조하게 한다. 읽기 전용.

  python nova.py docs-write grade [범위]          등급(작은 일 · 보통 일 · 큰 일) + 신호 + 기록 하한
  python nova.py docs-write tasks [tasks_REQ_NN]  남은 `- [ ]` 나열 + 했음 · 넘김 · 기각 대조 안내
  python nova.py docs-write facts [범위]          회차 사실 한 장(커밋 · 등급 · 남은 task 수) — /round-close 0단계
  …  --json                                       기계용

범위 기본값: git 기록(docs/git/git_index.md 마지막 행 문서의 '## 커밋' 마지막 해시)..HEAD + 작업 트리 변경(커밋 전 · 새 파일).
범위를 주면(`A..B` · `HEAD~3..HEAD`) 그 범위의 커밋만 본다.

등급 — 사람이 저작한 파일 수로 정한다. 생성물(audit_scope 의 생성물 판정)과 번호 붙는 기록(history · git · session · 요구 · 검토 · 검증 · 메모)은
세지 않는다 — 기계가 찍은 파일은 새 판단이 아니고, 기록이 기록을 불러 등급을 올리는 자기 참조를 끊어야 한다.
  작은 일 < 3 ≤ 보통 일 ≤ 4 < 큰 일(5 이상)
신호(ADR · DB 모델 · 계약)는 저작분에서만 보고 **올리기만** 한다(큰 일로). 등급은 제안이고 판정은 사람이다 — 애매하면 한 등급 위로.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_scope import GENERATED_GLOBS, MARKERS  # noqa: E402
from novalib import ROOT  # noqa: E402

GRADES = ("작은 일", "보통 일", "큰 일")
# 번호 붙는 기록 · 기록 보기 — 등급의 분모에서 뺀다(무엇을 만들었나가 아니라 무엇을 적었나)
RECORD_PREFIXES = ("docs/history/", "docs/git/", "docs/session/", "docs/requirement/", "docs/reviews/",
                   "docs/verification/", "docs/memo/")
FLOOR = {
    "작은 일": ["커밋", "git 기록(uv run python scripts/git_record.py \"<요약>\")"],
    "보통 일": ["커밋", "git 기록(git_record.py)", "/history-new(한 일 · 발견 · 검증 숫자)"],
    "큰 일": ["커밋", "git 기록(git_record.py)", "/history-new", "요구(REQ) 갱신 — 수용 기준 · 상태 · 종료 조건 판정",
             "되돌리기 어려운 구조 결정이면 ADR(docs_new.py adr)"],
}
CONTRACT_FILES = {"packages/common-py/nova_common/services.json", "infra/k3s/base/kafka-topics.txt"}
ROUTE = re.compile(r"APIRouter\(|@router\.(get|post|put|patch|delete)\(|@app\.(get|post|put|patch|delete)\(")
BOX = re.compile(r"^(\s*)- \[([ xX])\]\s*(.*)$")


# ------------------------------------------------------------------ git
def git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"✗ git {' '.join(args)} 실패: {r.stderr.strip()}")
    return r.stdout


def record_base(root: Path) -> str | None:
    """git 기록 인덱스 마지막 행 → 그 문서 '## 커밋' 마지막 해시(git 이 아는 것만). git_record.default_range 와 같은 규칙, root 를 받는다."""
    gdir = root / "docs" / "git"
    idx = gdir / "git_index.md"
    if not idx.exists():
        return None
    links = re.findall(r"^\|\s*\[[^\]]+\]\(([^)]+\.md)\)", idx.read_text(encoding="utf-8"), re.M)
    if not links or not (gdir / links[-1]).exists():
        return None
    body = (gdir / links[-1]).read_text(encoding="utf-8")
    sec = re.search(r"^## 커밋\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    shas = re.findall(r"^- `([0-9a-f]{7,40})`", sec.group(1) if sec else "", re.M)
    if not shas:
        return None
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{shas[-1]}^{{commit}}"], cwd=root, capture_output=True, text=True)
    return shas[-1] if r.returncode == 0 else None


def _z(out: str) -> list[str]:
    return [x for x in out.split("\0") if x]


def worktree_changes(root: Path) -> list[str]:
    """커밋 전 변경 · 새 파일(지운 파일도 '바뀐 것'으로 센다). 이름 바꾸기는 새 이름만."""
    parts, out, i = _z(git(root, "status", "--porcelain=v1", "-z", "-uall")), [], 0
    while i < len(parts):
        ent = parts[i]
        code, path = ent[:2], ent[3:]
        out.append(path)
        i += 2 if "R" in code or "C" in code else 1   # -z 에서 이름 바꾸기는 다음 칸에 옛 이름이 온다
    return out


def changed_files(root: Path, rng: str | None = None) -> tuple[list[str], str]:
    """(바뀐 파일, 범위 설명). 범위를 주면 그 커밋 범위만, 안 주면 기록 기준..HEAD + 작업 트리."""
    if rng:
        files = _z(git(root, "diff", "--name-only", "-z", rng if ".." in rng else f"{rng}..HEAD"))
        return sorted(set(files)), rng
    base = record_base(root)
    files: set[str] = set()
    has_head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=root, capture_output=True).returncode == 0
    if base and has_head:
        files |= set(_z(git(root, "diff", "--name-only", "-z", f"{base}..HEAD")))
    files |= set(worktree_changes(root))
    desc = (f"{base[:7]}..HEAD" if base else "기록 기준 없음") + " + 작업 트리"
    return sorted(files), desc


def commits(root: Path, rng: str | None) -> list[str]:
    if not rng:
        base = record_base(root)
        if not base:
            return []
        rng = f"{base}..HEAD"
    elif ".." not in rng:
        rng = f"{rng}..HEAD"
    return [ln for ln in git(root, "log", "--oneline", rng).splitlines() if ln.strip()]


# ------------------------------------------------------------------ 분류
def generated_reason(root: Path, rel: str) -> str:
    """audit_scope 의 생성물 판정(경로 무늬 · 머리 표시)을 root 기준으로. k3s 생성물은 머리 표시로 잡힌다."""
    p = Path(rel)
    for g, why in GENERATED_GLOBS.items():
        if p.match(g):
            return why
    if p.parts and p.parts[0] == "scripts":   # 생성기 · 템플릿 자신은 원천이다
        return ""
    if p.suffix in (".css", ".kt", ".yaml", ".yml", ".md", ".html", ".sql", ".json", ".txt"):
        try:
            head = (root / p).read_text(encoding="utf-8", errors="ignore")[:800]
        except OSError:
            return ""
        if any(m in head for m in MARKERS):
            return "머리 표시(생성물)"
    return ""


def is_record(rel: str) -> bool:
    return rel.startswith(RECORD_PREFIXES)


def signals(root: Path, authored: list[str]) -> dict[str, list[str]]:
    def route(rel: str) -> bool:
        if not rel.endswith(".py") or "/tests/" in f"/{rel}" or not rel.startswith(("services/", "packages/")):
            return False
        try:
            return bool(ROUTE.search((root / rel).read_text(encoding="utf-8", errors="ignore")))
        except OSError:   # 지운 파일 — 내용을 못 보니 라우트인지 모른다(경로 규칙만 남는다)
            return False
    return {
        "ADR": [f for f in authored if re.match(r"docs/adr/ADR-\d+", f)],
        "DB 모델": [f for f in authored if Path(f).name == "models.py" or "/migrations/" in f"/{f}" or "/alembic/" in f"/{f}"
                  or f.endswith(".sql")],
        "계약": [f for f in authored if f in CONTRACT_FILES or Path(f).name == "rbac.json" or route(f)],
    }


def grade(root: Path = ROOT, rng: str | None = None, files: list[str] | None = None) -> dict:
    """등급 제안. files 를 주면 git 을 보지 않는다(시험용)."""
    desc = "주어진 목록"
    if files is None:
        files, desc = changed_files(root, rng)
    records = [f for f in files if is_record(f)]
    gen = {f: generated_reason(root, f) for f in files if not is_record(f)}
    generated = [f for f, why in gen.items() if why]
    authored = [f for f, why in gen.items() if not why]
    n = len(authored)
    g = "큰 일" if n >= 5 else "보통 일" if n >= 3 else "작은 일"
    reasons = [f"저작 파일 {n}개(" + ("5 이상" if n >= 5 else "3~4" if n >= 3 else "3 미만") + ")"]
    if generated:
        reasons.append(f"생성물 {len(generated)}개 제외")
    if records:
        reasons.append(f"기록 {len(records)}개 제외")
    sig = signals(root, authored)
    for name, hits in sig.items():
        if hits:   # 신호는 올리기만 한다 — 파일이 적어도 계약을 바꾸면 큰 일
            g = "큰 일"
            reasons.append(f"{name} 신호({len(hits)})")
    return {"grade": g, "range": desc, "files": len(files), "authored": authored, "generated": generated,
            "records": records, "signals": sig, "reasons": reasons, "floor": FLOOR[g]}


# ------------------------------------------------------------------ tasks
def task_files(root: Path, name: str | None) -> list[Path]:
    tdir = root / "docs" / "plans" / "tasks"
    if not name:
        return sorted(tdir.glob("tasks_REQ_*.md"))
    stem = Path(name).name.removesuffix(".md")
    p = tdir / f"{stem}.md"
    if not p.exists():
        raise SystemExit(f"✗ {p.relative_to(root).as_posix()} 가 없다 — 목록: {', '.join(x.stem for x in sorted(tdir.glob('tasks_REQ_*.md')))}")
    return [p]


def open_tasks(root: Path = ROOT, name: str | None = None) -> dict:
    """남은 `- [ ]` — 취소선(기각 표시)이 이미 붙은 것은 따로 센다. 체크는 하지 않는다(읽기 전용)."""
    out = {}
    for p in task_files(root, name):
        items = []
        for no, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = BOX.match(ln)
            if not m or m.group(2) != " ":
                continue
            text = m.group(3)
            kind = "기각 표시" if "~~" in text else "넘김 표시(🆕)" if "🆕" in text else "미판정"
            items.append({"line": no, "text": text, "kind": kind, "sub": bool(m.group(1))})
        out[p.relative_to(root).as_posix()] = items
    return out


GUIDE = [
    "세 갈래로 하나씩 대조한다 — 일괄 체크 금지:",
    "  ① 했음   → 코드 · 테스트(명령 출력)로 확인한 것만 `- [x]`",
    "  ② 넘김   → 체크하지 않는다. 🆕 표시 + 다음 요구(REQ) · 이유를 같은 줄에",
    "  ③ 기각   → 체크하지 않는다. `~~취소선~~ — 이유`(지우지 않는다 — plans README)",
]


# ------------------------------------------------------------------ 출력
def render_grade(r: dict) -> str:
    lines = [f"■ 등급 제안: {r['grade']}  (근거: {' · '.join(r['reasons'])})", f"  범위: {r['range']} · 바뀐 파일 {r['files']}개"]
    for name, hits in r["signals"].items():
        if hits:
            lines.append(f"  신호 {name}: {', '.join(hits[:5])}" + (" …" if len(hits) > 5 else ""))
    lines.append("  기록 하한: " + " · ".join(r["floor"]))
    lines.append("  소비자가 느낄 변화(명령 · 화면 · API · 토큰)가 있으면 열린 판본 노트 docs/releases/v<버전>.md 에 한 줄")
    lines.append("  ⚠ 등급은 제안이다 — 파일 수 · 경로만 본다. 계약을 바꾸는지 · 결정을 남기는지는 사람이 안다. 애매하면 한 등급 위로")
    return "\n".join(lines)


def render_tasks(t: dict) -> str:
    lines, total = [], 0
    for f, items in t.items():
        if not items:
            continue
        total += len(items)
        lines.append(f"■ {f} — 남은 칸 {len(items)}개")
        for it in items:
            lines.append(f"  {f}:{it['line']}  [{it['kind']}] {'  ' if it['sub'] else ''}{it['text']}")
    if not total:
        return "✓ 남은 `- [ ]` 없음"
    return "\n".join(lines + ["", *GUIDE])


def facts(root: Path = ROOT, rng: str | None = None) -> dict:
    t = open_tasks(root)
    return {"commits": commits(root, rng), "grade": grade(root, rng),
            "open_tasks": {f: sum(1 for i in v if i["kind"] == "미판정") for f, v in t.items() if v}}


def render_facts(f: dict) -> str:
    lines = [f"■ 커밋 {len(f['commits'])}개(기록 기준 이후)"] + [f"  {c}" for c in f["commits"][:20]]
    lines += ["", render_grade(f["grade"]), "", "■ 미판정 task(3갈래 대조 대상)"]
    lines += [f"  {k}: {v}" for k, v in f["open_tasks"].items() if v] or ["  없음"]
    lines += ["", "다음 사실은 각 명령 출력을 그대로 쓴다(숫자를 지어내지 않는다): python nova.py progress · release status · issue list --open · exit-check REQ-…"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="docs-write", description="기록 분량 정하기 — 등급 · task 대조 · 회차 사실(읽기 전용)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("grade", "facts"):
        s = sub.add_parser(name)
        s.add_argument("range", nargs="?", help="커밋 범위(A..B). 없으면 git 기록 기준..HEAD + 작업 트리")
        s.add_argument("--json", action="store_true")
    s = sub.add_parser("tasks")
    s.add_argument("name", nargs="?", help="tasks_REQ_NN(없으면 전부)")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "grade":
        r = grade(ROOT, a.range)
        print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else render_grade(r))
    elif a.cmd == "tasks":
        t = open_tasks(ROOT, a.name)
        print(json.dumps(t, ensure_ascii=False, indent=2) if a.json else render_tasks(t))
    else:
        f = facts(ROOT, a.range)
        print(json.dumps(f, ensure_ascii=False, indent=2) if a.json else render_facts(f))
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:  # 재설정을 못 하는 스트림(파이프 대체 등)은 그대로 둔다
            pass
    raise SystemExit(main())
