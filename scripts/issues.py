#!/usr/bin/env python3
"""결함 · 변경요청 원장 — 재현 · 기대 · 실제 · 환경 4요소를 갖춘 것만 받고, 종결 · 승인은 근거가 있을 때만 통과시킨다.

  python nova.py issue add --kind defect|change --grade P0..P3 --title "…" --repro "…" --expected "…" --actual "…" --env "…"
  python nova.py issue set <ID> --status open|triaged|in_progress|verifying|closed|deferred
                           [--repro-test 경로::이름] [--postmortem 경로] [--impact "…"] [--level L1|L2|L3]
                           [--adr 경로] [--approved-by 이름]
  python nova.py issue list [--open] [--kind defect|change]
  python nova.py issue show <ID>
  python nova.py issue check      원장 형식 · 게이트 · 보기 일치(lint 용 — 원장이 없으면 정상)
  python nova.py issue render     보기 docs/issues/README.md 의 표 절을 다시 만든다

원천: docs/issues/issues.json(상태 — ADR-004 선언/상태 JSON). 보기: docs/issues/README.md(표 절은 생성물).
게이트(기계 거부):
  · 4요소 중 하나라도 비거나 공백뿐이면 접수 거부
  · P0 결함을 closed 로 하려면 --repro-test(파일 실재)와 --postmortem(파일 실재) 둘 다
  · P0 결함을 deferred 로 하려면 --approved-by(보류를 정한 사람) — 보류로 종결 게이트를 건너뛰지 못하게
  · change 를 in_progress 이상으로 올리려면(=승인) --impact · --level · --approved-by, L3 면 --adr(파일 실재)
쓰기(add · set · render)는 본 작업 트리(main)만 — 단일 기록자(ADR-008).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, require_main, write  # noqa: E402

KINDS = ("defect", "change")
GRADES = ("P0", "P1", "P2", "P3")
STATUSES = ("open", "triaged", "in_progress", "verifying", "closed", "deferred")
APPROVED = ("in_progress", "verifying", "closed")  # change 는 이 상태부터 '승인됨'
LEVELS = ("L1", "L2", "L3")
FOUR = ("repro", "expected", "actual", "env")
ID_RE = re.compile(r"^ISS-(\d{6})-(\d{2})$")
SIMILAR = 0.5  # 질의 제목 토큰 중 이 비율 이상이 열린 항목 제목에 있으면 중복 의심
KIND_KO = {"defect": "결함", "change": "변경요청"}
STATUS_KO = {"open": "접수", "triaged": "분류", "in_progress": "진행", "verifying": "확인 중",
             "closed": "종결", "deferred": "보류"}

VIEW_START = "<!-- 생성 시작: scripts/issues.py render — 이 아래부터 '생성 끝' 까지는 손으로 고치지 않는다 -->"
VIEW_END = "<!-- 생성 끝 -->"
VIEW_HEAD = """# 결함 · 변경요청 원장

원천은 `issues.json` 이다. 이 문서의 표 절은 `python nova.py issue render` 가 만든다.

"""


def ledger(root: Path = ROOT) -> Path:
    return root / "docs" / "issues" / "issues.json"


def view_path(root: Path = ROOT) -> Path:
    return root / "docs" / "issues" / "README.md"


def load(root: Path = ROOT) -> dict:
    p = ledger(root)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"issues": []}


def save(d: dict, root: Path = ROOT) -> None:
    write(ledger(root), json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def blank(v) -> bool:
    return v is None or not str(v).strip()


def tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^\w]+", text.lower()) if t}


def overlap(q: set[str], c: set[str]) -> float:
    """질의 쪽 분모 — 짧은 새 제목이 이미 있는 제목 안에 들어 있는가(완전 일치 · 2글자 이상 부분 포함)."""
    if not q or not c:
        return 0.0
    total = 0.0
    for a in q:
        best = 0.0
        for b in c:
            if a == b:
                best = 1.0
                break
            short, long_ = (a, b) if len(a) <= len(b) else (b, a)
            if len(short) >= 2 and short in long_:
                best = max(best, len(short) / len(long_))
        total += best
    return total / len(q)


def next_id(d: dict, today: dt.date) -> str:
    ymd = today.strftime("%y%m%d")
    nums = [int(m.group(2)) for i in d.get("issues", []) if (m := ID_RE.match(i.get("id", ""))) and m.group(1) == ymd]
    return f"ISS-{ymd}-{max(nums, default=0) + 1:02d}"


def _date(today: str | dt.date | None) -> dt.date:
    if today is None:
        return dt.date.today()
    return today if isinstance(today, dt.date) else dt.date.fromisoformat(today)


def add(root: Path = ROOT, *, kind: str, grade: str, title: str, repro: str, expected: str, actual: str, env: str,
        today: str | dt.date | None = None) -> tuple[dict, list[str]]:
    """접수 — (항목, 경고). 4요소 · 등급 · 종류가 틀리면 SystemExit."""
    errs = []
    if kind not in KINDS:
        errs.append(f"--kind 는 {' · '.join(KINDS)} 중 하나(받은 값 '{kind}')")
    if grade not in GRADES:
        errs.append(f"--grade 는 {' · '.join(GRADES)} 중 하나(받은 값 '{grade}') — 변형 등급은 집계에서 빠진다")
    if blank(title):
        errs.append("--title 이 비었다")
    vals = dict(repro=repro, expected=expected, actual=actual, env=env)
    for k in FOUR:
        if blank(vals[k]):
            errs.append(f"--{k} 가 비었다(공백만도 빈 값) — 4요소(재현 · 기대 · 실제 · 환경)가 없으면 재현할 수 없다. 추측으로 채우지 말고 묻는다")
    if errs:
        raise SystemExit("✗ 접수 거부:\n  " + "\n  ".join(errs))
    d = load(root)
    day = _date(today)
    q = tokens(title)
    warns = []
    for o in d["issues"]:
        if o.get("status") in ("closed", "deferred"):
            continue
        s = overlap(q, tokens(o.get("title", "")))
        if s >= SIMILAR:
            warns.append(f"{o['id']} '{o.get('title', '')}' 와 제목이 {s:.0%} 겹친다 — 같은 건이면 이번 것을 deferred 로 돌리고 그쪽에 잇는다")
    it = {"id": next_id(d, day), "kind": kind, "grade": grade, "status": "open", "title": title.strip(),
          **{k: vals[k].strip() for k in FOUR}, "created": day.isoformat(), "updated": day.isoformat()}
    d["issues"].append(it)
    save(d, root)
    return it, warns


def _exists(root: Path, rel: str) -> bool:
    return (root / rel).is_file()


def gates(it: dict, root: Path) -> list[str]:
    """한 항목의 상태 게이트 — set 과 check 가 같은 판정을 쓴다."""
    errs, w = [], it.get("id", "?")
    st = it.get("status")
    if it.get("kind") == "defect" and it.get("grade") == "P0" and st == "closed":
        rt = it.get("repro_test") or ""
        if blank(rt):
            errs.append(f"{w}: P0 종결에는 --repro-test(경로::테스트이름)가 필요하다 — 재현 테스트 없이 닫으면 다시 났는지 알 수 없다")
        else:
            path, _, name = rt.partition("::")
            if blank(path) or blank(name):
                errs.append(f"{w}: --repro-test 형식은 '경로::테스트이름'(받은 값 '{rt}')")
            elif not _exists(root, path):
                errs.append(f"{w}: --repro-test 파일 {path} 가 없다")
        pm = it.get("postmortem") or ""
        if blank(pm):
            errs.append(f"{w}: P0 종결에는 --postmortem(사후기록 경로)이 필요하다 — /postmortem 으로 먼저 쓴다")
        elif not _exists(root, pm):
            errs.append(f"{w}: --postmortem 파일 {pm} 가 없다")
    if it.get("kind") == "defect" and it.get("grade") == "P0" and st == "deferred" and blank(it.get("approved_by")):
        # deferred 도 '닫힘'이다(목록 · 열린 수에서 빠진다) — 근거 없이 허용하면 위 종결 게이트를 옆문으로 건너뛴다
        errs.append(f"{w}: P0 결함의 보류(deferred)에는 --approved-by(보류를 정한 사람)가 필요하다 — "
                    "재현 불가 · 중복이어도 서비스 중단급을 내려놓는 것은 사람 결정이다(아니면 /hotfix 로 닫는다)")
    if it.get("kind") == "change" and st in APPROVED:
        if blank(it.get("impact")):
            errs.append(f"{w}: 변경요청 승인({st})에는 --impact(영향 5줄 — python nova.py impact …)가 필요하다 — 영향분석 없이 승인 없다")
        if it.get("level") not in LEVELS:
            errs.append(f"{w}: 변경요청 승인에는 --level L1|L2|L3 이 필요하다")
        if blank(it.get("approved_by")):
            errs.append(f"{w}: 변경요청 승인에는 --approved-by(승인한 사람)가 필요하다 — 승인은 사람 결정")
        if it.get("level") == "L3":
            adr = it.get("adr") or ""
            if blank(adr) or not _exists(root, adr):
                errs.append(f"{w}: L3(의미 변경 · 삭제)는 실재하는 ADR 경로(--adr)가 필요하다(받은 값 '{adr}') — Expand→Migrate→Contract 계획 포함")
    return errs


def set_status(root: Path = ROOT, iid: str = "", status: str = "", *, repro_test: str | None = None,
               postmortem: str | None = None, impact: str | None = None, level: str | None = None,
               adr: str | None = None, approved_by: str | None = None, today: str | dt.date | None = None) -> dict:
    if status not in STATUSES:
        raise SystemExit(f"✗ --status 는 {' · '.join(STATUSES)} 중 하나(받은 값 '{status}')")
    if level is not None and level not in LEVELS:
        raise SystemExit(f"✗ --level 은 {' · '.join(LEVELS)} 중 하나(받은 값 '{level}')")
    d = load(root)
    idx = next((n for n, i in enumerate(d["issues"]) if i.get("id") == iid), None)
    if idx is None:
        raise SystemExit(f"✗ {iid} 가 원장에 없다 — python nova.py issue list")
    it = dict(d["issues"][idx])
    for k, v in (("repro_test", repro_test), ("postmortem", postmortem), ("impact", impact),
                 ("level", level), ("adr", adr), ("approved_by", approved_by)):
        if v is not None:
            it[k] = v.strip()
    it["status"] = status
    errs = gates(it, root)
    if errs:
        raise SystemExit("✗ 상태를 바꿀 수 없다:\n  " + "\n  ".join(errs))
    day = _date(today).isoformat()
    it["updated"] = day
    if approved_by is not None and (status in APPROVED or status == "deferred"):
        it["approved_at"] = day
    d["issues"][idx] = it
    save(d, root)
    return it


def check(d: dict, root: Path = ROOT, view: bool = True) -> list[str]:
    """원장 형식 · 게이트 · 보기 일치. 원장 파일이 없으면 검사할 것이 없다."""
    if not ledger(root).exists() and not d.get("issues"):
        return []
    errs, seen = [], set()
    if not isinstance(d.get("issues"), list):
        return ["issues.json: 최상위는 {\"issues\": [...]}"]
    for it in d["issues"]:
        w = it.get("id", "?")
        if not ID_RE.match(w):
            errs.append(f"{w}: ID 형식은 ISS-YYMMDD-NN")
        if w in seen:
            errs.append(f"{w}: ID 가 겹친다")
        seen.add(w)
        if it.get("kind") not in KINDS:
            errs.append(f"{w}: kind 는 {' · '.join(KINDS)}")
        if it.get("grade") not in GRADES:
            errs.append(f"{w}: grade '{it.get('grade')}' — {' · '.join(GRADES)} 중 하나")
        if it.get("status") not in STATUSES:
            errs.append(f"{w}: status '{it.get('status')}' — {' · '.join(STATUSES)} 중 하나")
        if blank(it.get("title")):
            errs.append(f"{w}: title 이 비었다")
        for k in FOUR:
            if blank(it.get(k)):
                errs.append(f"{w}: {k} 가 비었다(4요소)")
        if it.get("level") not in (None, "", *LEVELS):
            errs.append(f"{w}: level '{it.get('level')}' — L1 · L2 · L3")
        errs += gates(it, root)
    if view:
        vp = view_path(root)
        cur = vp.read_text(encoding="utf-8").replace("\r\n", "\n") if vp.exists() else ""
        if section(d) not in cur:
            errs.append("docs/issues/README.md 의 표가 원장과 다르다 — python nova.py issue render (손으로 고치지 않는다)")
    return errs


def _cell(v) -> str:
    return str(v or "—").replace("|", "\\|").replace("\n", " ")


def section(d: dict) -> str:
    """보기의 생성 절 — 표시 · 표. 최신이 위."""
    rows = sorted(d.get("issues", []), key=lambda i: i.get("id", ""), reverse=True)
    out = [VIEW_START, "", "> 생성물 — scripts/issues.py render · 원천 `docs/issues/issues.json`. 고치려면 `python nova.py issue set …`", ""]
    open_n = sum(1 for i in rows if i.get("status") not in ("closed", "deferred"))
    out.append(f"열린 항목 {open_n}개 · 전체 {len(rows)}개")
    out.append("")
    out.append("| ID | 종류 | 등급 | 상태 | 제목 | 근거 · 영향 | 접수 |")
    out.append("|---|---|---|---|---|---|---|")
    if not rows:
        out.append("| — | — | — | — | (아직 없다) | — | — |")
    for i in rows:
        ev = []
        if i.get("repro_test"):
            ev.append(f"재현 `{i['repro_test']}`")
        if i.get("postmortem"):
            ev.append(f"사후 `{i['postmortem']}`")
        if i.get("level"):
            ev.append(i["level"])
        if i.get("adr"):
            ev.append(f"ADR `{i['adr']}`")
        if i.get("approved_by"):
            ev.append(f"승인 {i['approved_by']}")
        out.append(f"| {i.get('id')} | {KIND_KO.get(i.get('kind'), _cell(i.get('kind')))} | {_cell(i.get('grade'))} | "
                   f"{STATUS_KO.get(i.get('status'), _cell(i.get('status')))} | {_cell(i.get('title'))} | "
                   f"{_cell(' · '.join(ev))} | {_cell(i.get('created'))} |")
    out += ["", VIEW_END]
    return "\n".join(out) + "\n"


def render(root: Path = ROOT) -> Path:
    """보기의 생성 절만 바꾼다(설명 절은 사람이 쓴 그대로 둔다)."""
    vp = view_path(root)
    cur = vp.read_text(encoding="utf-8").replace("\r\n", "\n") if vp.exists() else VIEW_HEAD
    sec = section(load(root))
    if VIEW_START in cur and VIEW_END in cur:
        head, rest = cur.split(VIEW_START, 1)
        tail = rest.split(VIEW_END, 1)[1].lstrip("\n")
        text = head + sec + (("\n" + tail) if tail else "")
    else:
        text = cur.rstrip("\n") + "\n\n" + sec
    write(vp, text)
    return vp


def _line(i: dict) -> str:
    return (f"{i.get('id')} [{i.get('grade')} · {KIND_KO.get(i.get('kind'), i.get('kind'))} · "
            f"{STATUS_KO.get(i.get('status'), i.get('status'))}] {i.get('title')}")


NEXT = {"P0": "/hotfix — 재현 테스트(RED) 먼저", "P1": "/req-new → /plan-new(24시간 안 착수)",
        "P2": "/req-new → /plan-new(다음 릴리스)", "P3": "백로그 — 분기 정리"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("add", help="접수(4요소 필수)")
    a_.add_argument("--kind", required=True, choices=KINDS)
    a_.add_argument("--grade", required=True, choices=GRADES)
    for k in ("title", *FOUR):
        a_.add_argument(f"--{k}", required=True)
    s_ = sub.add_parser("set", help="상태 바꾸기(게이트 검사)")
    s_.add_argument("id")
    s_.add_argument("--status", required=True, choices=STATUSES)
    s_.add_argument("--repro-test")
    s_.add_argument("--postmortem")
    s_.add_argument("--impact")
    s_.add_argument("--level", choices=LEVELS)
    s_.add_argument("--adr")
    s_.add_argument("--approved-by")
    l_ = sub.add_parser("list", help="목록")
    l_.add_argument("--open", action="store_true", help="열린 것만(closed · deferred 제외)")
    l_.add_argument("--kind", choices=KINDS)
    sh = sub.add_parser("show", help="한 건 자세히")
    sh.add_argument("id")
    sub.add_parser("check", help="형식 · 게이트 · 보기 일치(lint)")
    sub.add_parser("render", help="보기 표 다시 만들기")
    a = ap.parse_args(argv)
    root = ROOT

    if a.cmd == "check":
        errs = check(load(root), root)
        for e in errs:
            print("✗", e)
        if not errs:
            print(f"✓ 결함 · 변경요청 원장 정상({len(load(root)['issues'])}건)")
        return 1 if errs else 0
    if a.cmd == "list":
        rows = [i for i in load(root)["issues"]
                if (not a.open or i.get("status") not in ("closed", "deferred")) and (not a.kind or i.get("kind") == a.kind)]
        for i in rows:
            print(" ", _line(i))
        print(f"■ {len(rows)}건")
        return 0
    if a.cmd == "show":
        it = next((i for i in load(root)["issues"] if i.get("id") == a.id), None)
        if not it:
            print(f"✗ {a.id} 가 원장에 없다")
            return 1
        print(json.dumps(it, ensure_ascii=False, indent=2))
        return 0

    require_main(f"issue {a.cmd}", root)
    if a.cmd == "add":
        it, warns = add(root, kind=a.kind, grade=a.grade, title=a.title, repro=a.repro,
                        expected=a.expected, actual=a.actual, env=a.env)
        render(root)
        for w in warns:
            print("⚠", w)
        print(f"✓ 접수 {_line(it)}")
        print(f"  다음: {'영향 조회 python nova.py impact … → 등급 · 승인(/change)' if it['kind'] == 'change' else NEXT[it['grade']]}")
        return 0
    if a.cmd == "set":
        it = set_status(root, a.id, a.status, repro_test=a.repro_test, postmortem=a.postmortem, impact=a.impact,
                        level=a.level, adr=a.adr, approved_by=a.approved_by)
        render(root)
        print(f"✓ {_line(it)}")
        return 0
    if a.cmd == "render":
        print(f"✓ 보기 다시 만듦: {render(root).relative_to(root).as_posix()}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
