#!/usr/bin/env python3
"""문서 인덱스 검사 — 모든 문서가 인덱스에 있고, 인덱스 링크가 모두 실제 파일을 가리키는지.

  uv run python scripts/docs_index.py --check     (lint 에서 실행, 틀리면 종료코드 1)
  uv run python scripts/docs_index.py             (상태 출력)
검사: requirement · interviews · plans(plan_REQ ↔ tasks 짝) · history · git · session · reviews · verification · adr
     + 새 문서(261105 이후 · ADR-013 · plan_REQ_06 이후) 머리 표의 추적 칸 원천 · 연결(REQ-261105-04)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, read  # noqa: E402

DOCS = ROOT / "docs"
LINK = re.compile(r"\]\(([^)#\s]+\.md)\)")
HANGUL = re.compile(r"[가-힣]")

# (폴더, 인덱스, 문서 파일 정규식)
INDEXES = [
    ("requirement", "requirement_index.md", r"requirement_\d{6}_\d{2}\.md"),
    ("requirement/interviews", "interview_index.md", r"interview_\d{6}_\d{2}\.md"),
    ("plans", "plan_index.md", r"plan_REQ_\d+\.md"),
    ("history", "history_index.md", r"history_\d{6}_\d{2}\.md"),
    ("git", "git_index.md", r"git_\d{6}_\d{2}\.md"),
    ("session", "session_index.md", r"session_\d{6}_\d{2}\.md"),
    ("reviews", "review_index.md", r"review_\d{6}_\d{2}\.md"),
    ("verification", "verification_index.md", r"verify_\d{6}_\d{2}\.md"),
    ("adr", "README.md", r"ADR-\d{3}-.+\.md"),
]


INTENT_KEYS = ("문제", "결과", "영향", "제약", "미해결")


def check_intent() -> list[str]:
    """요구 문서의 '의도(INTENT)' 표 — 다섯 칸이 모두 채워졌는가(자리표시 그대로 · 빈칸 금지, 미해결은 '없음'도 답)."""
    errs = []
    for md in sorted((DOCS / "requirement").glob("requirement_*.md")):
        text = read(md)
        m = re.search(r"^## 의도 \(INTENT[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        if not m:
            continue   # 이 절이 생기기 전 문서는 검사하지 않는다
        rows = dict(re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$", m.group(1), re.M))
        for k in INTENT_KEYS:
            v = rows.get(k, "")
            if not v or (v.startswith("(") and v.endswith(")")):
                errs.append(f"의도(INTENT) 비어 있음: docs/requirement/{md.name} '{k}' — 해법 전에 곤란함을 적는다(미해결은 없으면 \"없음\")")
    return errs


# 추적 칸(REQ-261105-04) — 이 기준 이후에 만든 문서만 검사한다(기존 문서는 소급하지 않는다).
# 날짜가 이름에 있는 기록은 날짜로, 날짜가 없는 ADR · plan 은 이 규칙이 생긴 때의 번호로 가른다.
TRACE_SINCE_DAY = 261105
TRACE_SINCE_ADR = 13
TRACE_SINCE_PLAN = 6
TRACE_KEYS = {
    "원천": "이 문서가 무엇에서 나왔는지(사용자 원문 · REQ · 리뷰 · 세션 · 커밋)",
    "연결": "상위 · 하위 · 관련 문서 링크",
}
TRACE_DAILY = re.compile(r"(?:requirement|interview|history|session|review|verify|git)_(\d{6})_\d{2}\.md")


def trace_in_scope(path: Path) -> bool:
    """추적 칸 검사 대상인가 — 파일 이름만 본다(날짜 261105 이상 · ADR-013 이상 · plan_REQ_06 이상)."""
    name = path.name
    if m := TRACE_DAILY.fullmatch(name):
        return int(m.group(1)) >= TRACE_SINCE_DAY
    if m := re.fullmatch(r"ADR-(\d{3})-.+\.md", name):
        return int(m.group(1)) >= TRACE_SINCE_ADR
    if m := re.fullmatch(r"plan_REQ_(\d+)\.md", name):
        return int(m.group(1)) >= TRACE_SINCE_PLAN
    return False


def check_trace() -> list[str]:
    """새 기록 문서의 머리 표 사람 칸(원천 · 연결) — 줄이 있고 자리표시 그대로 · 빈칸이 아닌가.
    자동 칸(문서 ID · 생성 · 위치)은 docs_new · git_record 가 채우므로 검사하지 않는다."""
    errs = []
    for folder, _index, pattern in INDEXES:
        base = DOCS / folder
        if not base.exists():
            continue
        for md in sorted(base.iterdir()):
            if not re.fullmatch(pattern, md.name) or not trace_in_scope(md):
                continue
            head = re.split(r"^## ", read(md), maxsplit=1, flags=re.M)[0]   # 첫 절 앞 = 머리 표
            rows = dict(re.findall(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$", head, re.M))
            for k, what in TRACE_KEYS.items():
                v = rows.get(k)
                rel = f"docs/{folder}/{md.name}"
                if v is None:
                    errs.append(f"추적 칸 없음: {rel} '{k}' — 머리 표에 '| {k} | … |' 줄을 넣고 {what}를 적는다")
                elif not v or (v.startswith("(") and v.endswith(")")) or "{{" in v:
                    errs.append(f"추적 칸 비어 있음: {rel} '{k}' — 자리표시를 지우고 {what}를 적는다")
    return errs


def check_exit() -> list[str]:
    """요구 문서의 '종료 조건 (exit)' 표 형식 — 1~7개 · 방식 · 소진형 금지(ADR-008, scripts/goals.py)."""
    import goals
    errs = []
    for md in sorted((DOCS / "requirement").glob("requirement_*.md")):
        items = goals.parse_table(read(md))
        if items is not None:   # 이 절이 생기기 전 문서는 검사하지 않는다
            errs += [f"종료 조건: docs/requirement/{e}" for e in goals.lint(items, md.name)]
    return errs


def check_standards() -> list[str]:
    """표준(STD) 판정 의무 — docs/std/STD-*.md 마다 nova.project.json standards 에 적용/면제 + 이유."""
    import json

    meta_f = ROOT / "nova.project.json"
    std_dir = DOCS / "std"
    if not std_dir.exists() or not meta_f.exists():
        return []
    decisions = json.loads(meta_f.read_text(encoding="utf-8")).get("standards", {})
    errs = []
    for f in sorted(std_dir.glob("STD-*.md")):
        sid = re.match(r"(STD-[A-Z-]+-\d{3})", f.name)
        if not sid:
            continue
        d = decisions.get(sid.group(1))
        if not d:
            errs.append(f"표준 판정 없음: {sid.group(1)} — nova.project.json standards 에 적용/면제와 이유를 남긴다(docs/std/README.md)")
        elif d.get("decision") not in ("적용", "면제") or not str(d.get("reason", "")).strip():
            errs.append(f"표준 판정 형식: {sid.group(1)} — decision 은 적용|면제, reason 은 비우지 않는다")
    for sid in decisions:
        if not list(std_dir.glob(f"{sid}*.md")):
            errs.append(f"없는 표준을 판정함: {sid}")
    return errs


def check() -> list[str]:
    errors: list[str] = []
    for folder, index, pattern in INDEXES:
        base = DOCS / folder
        idx = base / index
        if not idx.exists():
            errors.append(f"인덱스 없음: docs/{folder}/{index}")
            continue
        text = read(idx)
        linked = {l for l in LINK.findall(text) if "/" not in l}
        files = {p.name for p in base.iterdir() if re.fullmatch(pattern, p.name)}
        for f in sorted(files - linked):
            errors.append(f"인덱스에 빠짐: docs/{folder}/{f} → {index} 에 한 줄 추가")
        for l in sorted(linked):
            if re.fullmatch(pattern, l) and not (base / l).exists():
                errors.append(f"없는 파일을 가리킴: docs/{folder}/{index} → {l}")
    # 한국어 기록 규칙 (REQ-261103-05) — 한글이 한 글자도 없는 문서는 실패
    for md in DOCS.rglob("*.md"):
        if not HANGUL.search(read(md)):
            errors.append(f"한국어 아님: {md.relative_to(ROOT).as_posix()} — 기록은 한국어로 쓴다(CLAUDE.md 규칙 0)")
    errors += check_standards()
    errors += check_intent()
    errors += check_trace()
    errors += check_exit()
    # plan ↔ tasks 짝
    plans = DOCS / "plans"
    for p in plans.glob("plan_REQ_*.md"):
        nn = p.stem.removeprefix("plan_REQ_")
        if not (plans / "tasks" / f"tasks_REQ_{nn}.md").exists():
            errors.append(f"task 파일 없음: docs/plans/tasks/tasks_REQ_{nn}.md ({p.name} 의 짝)")
    # 문서 안의 상대 링크 깨짐 (docs 전체)
    # drafts/ · archive/ 는 링크를 정식 위치(docs/plans/) 기준으로 쓰므로 제외 (plans/README §1)
    for md in DOCS.rglob("*.md"):
        if md.name.startswith("_template") or {"drafts", "archive"} & set(md.relative_to(DOCS).parts[:-1]):
            continue
        for l in LINK.findall(read(md)):
            if l.startswith(("http:", "https:")):
                continue
            target = (md.parent / l).resolve()
            if (ROOT / ".claude") in target.parents:
                # docs 만 복사해 검사하는 곳(테스트 · 일부 도구)에서 깨진다 — 두 번 겪은 함정(교훈 원장)
                errors.append(f"docs → .claude 링크 금지: {md.relative_to(ROOT).as_posix()} → {l} — 코드 표기(`{l.split('.claude/')[-1] and '.claude/' + l.split('.claude/')[-1]}`)로 쓴다")
                continue
            if not target.exists():
                errors.append(f"깨진 링크: {md.relative_to(ROOT).as_posix()} → {l}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    errors = check()
    for e in errors:
        print("✗", e)
    if not errors:
        print("✓ 문서 인덱스 · 링크 정상")
    return 1 if (errors and a.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
