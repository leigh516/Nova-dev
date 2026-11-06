"""규모 프로파일 — 프로젝트 크기에 맞춘 절차 기본값 (REQ-261104-17-5 · superpowers.md §4.1).

`nova.project.json` 의 `profile` = {value, why, date, history[]}. 값은 셋:
  lite      소형(2주 이하 · 서비스 1 · 화면 몇 개) — 착수 절차(체크리스트 · PRD · SPEC · 마스터플랜) 건너뜀 · /sdd light · 병렬 없음
  product   제품(복제본 기본) — 전체 착수 · 공통 영역 뒤 병렬 · /sdd full
  platform  플랫폼(Nova 자신) — 전체 + 마스터플랜 봉인 · 이력 하한 '보통 일'
승인 관문 · 안전 검사(비밀값 · 토큰 대비 · 생성물 --check · 표준 판정 · 한국어) · 기록 하한(커밋 + git 기록)은
어느 프로파일에서도 빼지 않는다 — 프로파일은 '얼마나 많이 하나'만 정하고 '지킬 것'은 정하지 않는다.

  python nova.py profile get
  python nova.py profile set <lite|product|platform> --why "<이유>"
  python nova.py profile check          # lint 단계
  python nova.py profile suggest        # 저장소를 세어 추천(바꾸지는 않는다)
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META = "nova.project.json"
VALUES = ("lite", "product", "platform")

# 프로파일별 기본값 — 안전 축(approval_gate · safety_checks · record_floor)은 모두 True 로 고정
RULES = {
    "lite": {"kickoff": "생략 — /req-new → /plan-new 짧은 판", "sdd": "light", "parallel": False,
             "history_floor": "작은 일", "masterplan_seal": False},
    "product": {"kickoff": "전체 — /kickoff → /checklist → /intake → /prd → /foundation → /spec", "sdd": "full", "parallel": True,
                "history_floor": "작은 일", "masterplan_seal": True},
    "platform": {"kickoff": "전체", "sdd": "full", "parallel": True, "history_floor": "보통 일", "masterplan_seal": True},
}
SAFETY = {"approval_gate": True, "safety_checks": True, "record_floor": True}


def rules(value: str) -> dict:
    if value not in RULES:
        raise SystemExit(f"✗ 프로파일 값은 {' · '.join(VALUES)} 중 하나다: {value}")
    return {**RULES[value], **SAFETY}


def load_meta(root: Path | None = None) -> dict:
    p = (root or ROOT) / META
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def current(root: Path | None = None) -> str | None:
    """선언된 값 — 없거나 틀리면 None(부르는 쪽이 기본 동작을 고른다)."""
    v = (load_meta(root).get("profile") or {}).get("value")
    return v if v in VALUES else None


def _is_date(s: object) -> bool:
    return isinstance(s, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


def check(meta: dict) -> list[str]:
    p = meta.get("profile")
    if not isinstance(p, dict):
        return [f"{META} 에 profile 이 없다 — python nova.py profile set <{'|'.join(VALUES)}> --why \"<이유>\""]
    errs = []
    if p.get("value") not in VALUES:
        errs.append(f"profile.value '{p.get('value')}' — lite · product · platform 중 하나")
    if not str(p.get("why", "")).strip():
        errs.append("profile.why 이유가 비어 있다 — 왜 이 규모인지 한 줄(판정 없는 선언은 선언이 아니다)")
    if not _is_date(p.get("date")):
        errs.append(f"profile.date '{p.get('date')}' — 날짜 YYYY-MM-DD")
    for i, h in enumerate(p.get("history", []) or []):
        if not (isinstance(h, dict) and h.get("value") in VALUES and str(h.get("why", "")).strip() and _is_date(h.get("date"))):
            errs.append(f"profile.history[{i}] — value · why · date 를 갖춘 지난 선언이어야 한다")
    return errs


def set_profile(meta: dict, value: str, why: str, today: dt.date) -> dict:
    rules(value)
    if not why.strip():
        raise SystemExit("✗ 프로파일을 바꿀 때는 이유(--why)를 적는다")
    out = copy.deepcopy(meta)
    old = out.get("profile")
    hist = list((old or {}).get("history", []) or [])
    if isinstance(old, dict) and old.get("value") in VALUES:
        hist.append({"value": old["value"], "why": old.get("why", ""), "date": old.get("date", today.isoformat())})
    out["profile"] = {"value": value, "why": why.strip(), "date": today.isoformat(), "history": hist}
    return out


def suggest(backend_services: int, web_apps: int, packs: int, is_platform: bool) -> tuple[str, list[str]]:
    """세어 본 숫자로 추천 — 문턱값은 시작값(실측으로 고친다, REQ-261104-17 미해결)."""
    if is_platform:
        return "platform", ["상류 원본(platform 블록 없음) — 다른 프로젝트가 물려받는 규칙 · 코드를 만든다"]
    if backend_services <= 1 and web_apps <= 1 and packs == 0:
        return "lite", [f"업무 서비스 {backend_services} · 웹 앱 {web_apps} · 팩 {packs} — 착수 절차 없이 /req-new → /plan-new 로 충분"]
    return "product", [f"업무 서비스 {backend_services} · 웹 앱 {web_apps} · 팩 {packs} — 전체 착수 · 공통 영역 뒤 병렬"]


def _count(root: Path) -> dict:
    meta = load_meta(root)
    cat = root / "packages/common-py/nova_common/services.json"
    svcs = json.loads(cat.read_text(encoding="utf-8")).get("services", []) if cat.exists() else []
    business = [s for s in svcs if s.get("group") != "gateway" and s.get("name") not in ("gateway", "sample")]
    return {"backend_services": len(business), "web_apps": len(meta.get("web_apps", [])),
            "packs": len(meta.get("packs", [])), "is_platform": "platform" not in meta}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="규모 프로파일 — lite · product · platform")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("get")
    s = sub.add_parser("set")
    s.add_argument("value", choices=VALUES)
    s.add_argument("--why", required=True)
    sub.add_parser("check")
    sub.add_parser("suggest")
    a = ap.parse_args(argv)
    meta = load_meta()
    if a.cmd == "get":
        p = meta.get("profile") or {}
        print(f"프로파일: {p.get('value', '(없음)')} — {p.get('why', '')} ({p.get('date', '')})")
        if p.get("value") in VALUES:
            for k, v in rules(p["value"]).items():
                print(f"  · {k}: {v}")
        return 0
    if a.cmd == "set":
        new = set_profile(meta, a.value, a.why, dt.date.today())
        (ROOT / META).write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"✓ 프로파일 {a.value} — 이력 {len(new['profile']['history'])}건")
        return 0
    if a.cmd == "check":
        errs = check(meta)
        for e in errs:
            print(f"  ✗ {e}")
        if errs:
            print("✗ 프로파일 판정 실패")
            return 1
        print(f"✓ 프로파일 정상: {meta['profile']['value']}")
        return 0
    value, reasons = suggest(**_count(ROOT))
    now = (meta.get("profile") or {}).get("value")
    print(f"추천: {value}" + ("" if now == value else f" (지금 {now or '없음'} — 바꾸려면 python nova.py profile set {value} --why …)"))
    for r in reasons:
        print(f"  · {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
