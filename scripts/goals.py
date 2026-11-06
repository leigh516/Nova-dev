#!/usr/bin/env python3
"""종료 조건(exit) — 목표를 정하고, 조건이 모두 녹색이면 끝낸다(무한히 넓어지지 않게 · ADR-008).

  python nova.py exit-check REQ-YYMMDD-NN     요구 문서의 '## 종료 조건 (exit)' 표를 실제로 판정
  (릴리스는 scripts/release.py 가 같은 형식 · 같은 판정을 쓴다)

표 형식(요구 문서 · 계획서 · 릴리스 공통):
  | ID | 확인 | 기대 | 방식 | 판정 |
  | E1 | python nova.py test | 통과 | 명령 |  |            ← 명령: 실제로 돌려 종료 코드 0 이면 충족
  | E2 | 체크리스트 폼에서 색 견본을 눌러 미리보기가 바뀐다 | 바뀐다 | 사람 | 충족 2026-11-04 |   ← 사람: 한 번 보고 판정을 적는다
명령 시간 제한: 기본 1200초 · 환경 변수 NOVA_EXIT_TIMEOUT(초)으로 늘린다. 사람 판정 칸은 '충족 YYYY-MM-DD' 로 시작해야 녹색이다.
규칙: 1~7개 · 한 번 보거나 한 번 돌려 답이 나오는 것만(재현형). "전부 찾는다 · 없음을 증명" 같은 소진형은 받지 않는다.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT  # noqa: E402

HOW = ("명령", "사람")
EXHAUSTIVE = ("전부 찾", "전수", "모두 찾", "없음을 증명", "하나도 없", "빠짐없이 모든", "완벽")
HEADING = "## 종료 조건 (exit)"


def parse_table(text: str) -> list[dict] | None:
    """'## 종료 조건 (exit)' 절의 표. 절이 없으면 None."""
    m = re.search(r"^## 종료 조건 \(exit\)[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return None
    rows = [ln for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    out = []
    for ln in rows[2:]:
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        c += [""] * (5 - len(c))
        if any(c[:4]):
            out.append({"id": c[0], "check": c[1].strip("`"), "expect": c[2], "how": c[3], "judged": c[4]})
    return out


def lint(items: list[dict], where: str) -> list[str]:
    """형식 검사 — 개수 · 방식 · 소진형 · 자리표시."""
    errs = []
    if not 1 <= len(items) <= 7:
        errs.append(f"{where}: 종료 조건은 1~7개(지금 {len(items)}개) — 많으면 목표가 너무 넓다")
    for it in items:
        w = f"{where} {it.get('id') or '?'}"
        if not it.get("check") or (it["check"].startswith("(") and it["check"].endswith(")")):
            errs.append(f"{w}: '확인' 이 비었다(자리표시 그대로)")
        if it.get("how") not in HOW:
            errs.append(f"{w}: 방식은 명령 · 사람 중 하나")
        text = f"{it.get('check', '')} {it.get('expect', '')}"
        if any(x in text for x in EXHAUSTIVE):
            errs.append(f"{w}: 소진형 조건('{text[:40]}…') — 끝이 없는 조건은 종료 조건이 될 수 없다. 한 번 보거나 한 번 돌려 답이 나오는 형태로")
    return errs


def judge(items: list[dict], *, root: Path = ROOT, run: bool = True, timeout: int | None = None) -> list[tuple[dict, bool, str]]:
    """[(항목, 충족?, 사유)] — 명령은 실제로 돌리고, 사람은 판정 칸을 읽는다.
    명령 시간 제한은 기본 1200초 — 느린 PC 에서 전체 test 가 넘으면 NOVA_EXIT_TIMEOUT(초)으로 늘린다(판정 의미는 같다)."""
    if timeout is None:
        timeout = int(os.environ.get("NOVA_EXIT_TIMEOUT") or 1200)
    out = []
    for it in items:
        if it["how"] == "명령":
            if not run:
                out.append((it, False, "실행 안 함(--dry)"))
                continue
            try:
                r = subprocess.run(it["check"], cwd=root, shell=True, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout)
                tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
                out.append((it, r.returncode == 0, f"종료 코드 {r.returncode} · {tail[0][:100]}"))
            except subprocess.TimeoutExpired:
                out.append((it, False, f"{timeout}초 넘음"))
        else:
            # '충족 안 됨' · '충족 못함' 을 충족으로 읽지 않는다 — 판정 칸은 '충족 YYYY-MM-DD …' 형식만 인정
            ok = bool(re.match(r"^충족\s+\d{4}-\d{2}-\d{2}", it.get("judged", "").strip()))
            out.append((it, ok, it.get("judged") or "판정 칸이 비었다 — 사람이 보고 '충족 YYYY-MM-DD' 를 적는다"))
    return out


def req_doc(req: str, root: Path = ROOT) -> Path:
    m = re.fullmatch(r"REQ-(\d{6})-(\d{2})", req)
    if not m:
        raise SystemExit(f"✗ 요구 ID 형식: {req} (예: REQ-261104-09)")
    return root / "docs" / "requirement" / f"requirement_{m.group(1)}_{m.group(2)}.md"


def report(results: list[tuple[dict, bool, str]]) -> bool:
    for it, ok, why in results:
        print(f"  {'✓' if ok else '✗'} {it['id']} [{it['how']}] {it['check'][:70]} — {why}")
    ok = all(r[1] for r in results)
    print("✓ 종료 조건 모두 충족 — 이 일은 끝이다(새로 보인 것은 다음 요구 · 릴리스 backlog 로)" if ok
          else "✗ 아직 끝나지 않았다 — 위의 ✗ 만 한다(범위를 넓히지 않는다)")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("req")
    ap.add_argument("--dry", action="store_true", help="명령을 돌리지 않고 형식만")
    a = ap.parse_args(argv)
    p = req_doc(a.req)
    items = parse_table(p.read_text(encoding="utf-8")) if p.exists() else None
    if items is None:
        print(f"✗ {p.name} 에 '{HEADING}' 절이 없다 — 요구 템플릿의 표를 채운다")
        return 1
    errs = lint(items, p.name)
    for e in errs:
        print("✗", e)
    if errs:
        return 1
    print(f"■ {a.req} 종료 조건 {len(items)}개")
    if a.dry:
        print("✓ 형식 정상(--dry — 판정은 하지 않았다)")
        return 0
    return 0 if report(judge(items)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
