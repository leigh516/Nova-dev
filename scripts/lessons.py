#!/usr/bin/env python3
"""교훈 원장 — 교정 · 테스트 실패 · 사후기록에서 얻은 것을 '트리거 → 규칙' 한 줄로 남긴다(같은 실수 반복 방지).

  python nova.py learn add "<트리거>" "<규칙>" --ref <근거 ID>    한 줄 추가(같은 트리거가 이미 있으면 '(승급 후보)' 표시)
  python nova.py learn check                                      형식 · 근거 식별자 · 승급 후보 표시 검사(lint 용)
  python nova.py learn find <낱말>                                 찾기

원장: docs/memo/lessons.md 의 '## 교훈' 절. 한 줄 형식:
  - [YYYY-MM-DD] <트리거> → **<규칙>.** (근거: <ID> · …)
근거에는 강한 식별자가 하나 이상: REQ-YYMMDD-NN · ISS-YYMMDD-NN · history_YYMMDD_NN · review_YYMMDD_NN · ADR-NNN.
날짜 · 산문만으로는 나중에 어느 사건인지 찾을 수 없다.
승급(SOUL · STYLE · CLAUDE.md · 게이트로 옮기기)은 이 스크립트가 하지 않는다 — /soul-review 와 사람 승인.
쓰기(add)는 본 작업 트리(main)만 — 단일 기록자(ADR-008).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, require_main, write  # noqa: E402

SECTION = "## 교훈"
PROMO = "(승급 후보)"
LINE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\] (.+?) → \*\*(.+?)\*\* \(근거: ([^)]+)\)( \(승급 후보\))?$")
REF = re.compile(r"\b(REQ-\d{6}-\d{2}(?:-\d+)?|ISS-\d{6}-\d{2}|history_\d{6}_\d{2}|review_\d{6}_\d{2}|ADR-\d{3})\b")


def path(root: Path = ROOT) -> Path:
    return root / "docs" / "memo" / "lessons.md"


def entries(root: Path = ROOT) -> list[tuple[int, str]]:
    """'## 교훈' 절 안의 목록 줄 — (줄 번호, 내용). 머리말의 설명 목록은 세지 않는다."""
    p = path(root)
    if not p.exists():
        return []
    out, inside = [], False
    for n, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if ln.startswith("## "):
            inside = ln.strip() == SECTION
            continue
        if inside and ln.startswith("- "):
            out.append((n, ln.rstrip()))
    return out


def _key(trigger: str) -> str:
    return " ".join(trigger.lower().split())


def check(root: Path = ROOT) -> list[str]:
    p = path(root)
    if not p.exists():
        return []
    if SECTION not in p.read_text(encoding="utf-8"):
        return [f"docs/memo/lessons.md: '{SECTION}' 절이 없다"]
    errs, seen = [], {}
    for n, ln in entries(root):
        m = LINE.match(ln)
        if not m:
            errs.append(f"lessons.md:{n}: 형식은 '- [YYYY-MM-DD] <트리거> → **<규칙>.** (근거: <ID>)' — {ln[:60]}")
            continue
        if not REF.search(m.group(4)):
            errs.append(f"lessons.md:{n}: 근거에 식별자(REQ- · ISS- · history_ · review_ · ADR-)가 없다 — '{m.group(4)[:40]}'")
        seen.setdefault(_key(m.group(2)), []).append((n, bool(m.group(5))))
    for k, rows in seen.items():
        if len(rows) >= 2 and not rows[-1][1]:
            errs.append(f"lessons.md:{rows[-1][0]}: 같은 트리거 '{k[:30]}' 가 {len(rows)}번 — 마지막 줄 끝에 '{PROMO}' 를 붙인다(/soul-review 입력)")
    return errs


def add(root: Path = ROOT, trigger: str = "", rule: str = "", *, ref: str, today: str | None = None) -> str:
    errs = []
    if not trigger.strip():
        errs.append("트리거가 비었다 — 어떤 상황에서 생긴 일인가")
    if not rule.strip():
        errs.append("규칙이 비었다 — 다음에 무엇을 다르게 하나")
    if "→" in trigger or "**" in trigger + rule:
        errs.append("트리거 · 규칙에 '→' · '**' 를 쓰지 않는다(형식 구분자)")
    if not REF.search(ref or ""):
        errs.append(f"--ref 에 근거 식별자(REQ-YYMMDD-NN · ISS-YYMMDD-NN · history_YYMMDD_NN · review_YYMMDD_NN · ADR-NNN)가 필요하다(받은 값 '{ref}')")
    p = path(root)
    if not p.exists():
        errs.append("docs/memo/lessons.md 가 없다")
    if errs:
        raise SystemExit("✗ 교훈을 남길 수 없다:\n  " + "\n  ".join(errs))
    rule = rule.strip().rstrip(".") + "."  # 형식은 '**규칙.**' — 마침표 하나로 맞춘다
    day = today or dt.date.today().isoformat()
    dup = any((m := LINE.match(ln)) and _key(m.group(2)) == _key(trigger) for _, ln in entries(root))
    line = f"- [{day}] {trigger.strip()} → **{rule}** (근거: {ref.strip()})" + (f" {PROMO}" if dup else "")
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    if SECTION not in text:
        text = text.rstrip("\n") + f"\n\n{SECTION}\n"
    write(p, text.rstrip("\n") + "\n" + line + "\n")
    return line


def find(root: Path = ROOT, word: str = "") -> list[tuple[int, str]]:
    w = word.lower()
    return [(n, ln) for n, ln in entries(root) if w in ln.lower()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("add", help="교훈 한 줄 추가")
    a_.add_argument("trigger")
    a_.add_argument("rule")
    a_.add_argument("--ref", required=True, help="근거 식별자(REQ- · ISS- · history_ · review_ · ADR-)")
    sub.add_parser("check", help="형식 검사(lint)")
    f_ = sub.add_parser("find", help="찾기")
    f_.add_argument("word")
    a = ap.parse_args(argv)
    root = ROOT
    if a.cmd == "check":
        errs = check(root)
        for e in errs:
            print("✗", e)
        if not errs:
            print(f"✓ 교훈 원장 정상({len(entries(root))}줄)")
        return 1 if errs else 0
    if a.cmd == "find":
        rows = find(root, a.word)
        for n, ln in rows:
            print(f"  lessons.md:{n}  {ln}")
        print(f"■ {len(rows)}줄")
        return 0
    require_main("learn add", root)
    print("✓", add(root, a.trigger, a.rule, ref=a.ref))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
