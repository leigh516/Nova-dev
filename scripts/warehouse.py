#!/usr/bin/env python3
"""자료 창고(docs/warehouse) — 입고 지문 · 부족 항목 · PRD/SPEC 정본 검사 · 출고 파생본.

  uv run python scripts/warehouse.py scan [--write]   입고 파일 지문 비교(새로 · 바뀜 · 사라짐), --write 면 intake.json 에 반영
  uv run python scripts/warehouse.py gaps             PRD 영역별 근거가 없는 것 + 열린 부족 항목(인터뷰 질문 재료)
  uv run python scripts/warehouse.py out [--check]    정본(docs/product/*.json) → 보기 md + outbound 파생본(md · html · json · sql)
  uv run python scripts/warehouse.py check            스키마 · 참조 · 입고/출고 대칭 · 드리프트 검사 (lint)

정본: docs/product/intake.json · prd.json · spec.json (형식 ADR-004 — 선언/상태는 JSON, 보기는 생성 MD). 규약: docs/product/README.md
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, project  # noqa: E402

DOCS = ROOT / "docs"
WH = DOCS / "warehouse"
PRODUCT = DOCS / "product"
MARK = "생성물: scripts/warehouse.py"

# 입고 읽는 순서 = 분류 목록 (입고 · 출고 같은 이름)
CATEGORIES = ["checklist", "prd", "spec", "db-sql", "html-mockup", "screenshot", "claude-code-handoff", "etc"]
# PRD 가 채워야 할 영역 — 근거(입고 발견 · 인터뷰)가 없는 영역이 인터뷰 질문의 재료가 된다
AREAS = ["목적 · 배경", "사용자 · 역할", "범위(목표 · 비목표)", "기능", "화면", "데이터", "외부 연동",
         "비기능", "운영", "일정 · 예산 · 제약", "표준(테넌트 · 업종 · AI)", "성공 지표"]
FILE_STATUS = ["미분석", "분석됨", "재분석 필요", "삭제됨"]
FINDING_KINDS = ["요구", "화면", "데이터", "API", "제약", "사실", "질문"]
GAP_STATUS = ["열림", "인터뷰 중", "답함", "해당 없음"]
DOC_STATUS = ["초안", "승인"]
PRIORITY = ["필수", "중요", "선택"]
ARCH = ["모듈러 모놀리스", "MSA", "모놀리식"]
CROSS_DECISION = ["내장 채택", "직접 구현", "미사용"]
# 횡단관심사 — /foundation 4단계. 내장 채택 시 Nova 자산을 쓴다(재발명 금지)
CROSSCUT = {
    "인증": "nova_common.auth(JWT) + 게이트웨이 로그인 · 개발 로그인",
    "인가 · 권한": "게이트웨이 권한 <모듈>.<행위> + services/gateway/gateway/rbac.json(역할 표)",
    "화면 셸 · 메뉴": "@nova/ui AppShell · services/gateway/gateway/menu.json · 기능 플래그",
    "디자인 시스템": "design/tokens/brand.tokens.json → @nova/ui · kr.nova.uikit (WCAG 검사)",
    "오류 표준": "{error:{code,message}} 봉투 · @nova/ui ErrorState · useAction",
    "로깅 · 감사": "nova.events 로거 · 이벤트 봉투(actor_type · tenant)",
    "관측성": "nova_ 메트릭 · Prometheus · Alertmanager · Grafana 생성기",
    "이벤트 · 메시징": "아웃박스 · 멱등 소비 · DLQ · Kafka(개발은 메모리 버스)",
    "목록 · 검색 · 페이지": "nova_common.paging 목록 계약 · DataTable · ListPage · useQueryState",
    "다국어(i18n)": "(내장 없음 — 한국어 기본) 필요하면 직접 구현",
    "파일 · 첨부": "(내장 없음) 필요하면 직접 구현",
}
COLTYPE = re.compile(r"^(string\(\d+\)|text|int|bigint|decimal\(\d+,\d+\)|bool|date|datetime|json|ref)$")
SQLTYPE = {"text": "TEXT", "int": "INT", "bigint": "BIGINT", "bool": "BOOLEAN", "date": "DATE",
           "datetime": "DATETIME(6)", "json": "JSON", "ref": "CHAR(36)"}


# ───────────────────────── 공통
def load(name: str) -> dict | None:
    p = PRODUCT / f"{name}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def dump(name: str, data: dict) -> None:
    (PRODUCT / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def generated(p: Path) -> bool:
    """우리 도구가 만든 파일(체크리스트 폼 · md 보기)은 입고 자료가 아니다 — 분석 대상에서 뺀다."""
    if p.suffix not in (".html", ".md", ".sql"):
        return False
    return "생성물: scripts/" in p.read_text(encoding="utf-8", errors="ignore")[:800]


def inbound_files() -> dict[str, Path]:
    out = {}
    base = WH / "inbound"
    if not base.exists():
        return out
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.name != "README.md" and not p.name.startswith(".") and not generated(p):
            out[p.relative_to(base).as_posix()] = p
    return out


def cell(v) -> str:
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v)
    return str(v if v not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")


def table(head: list[str], rows: list[list]) -> str:
    if not rows:
        return "(없음)\n"
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def mark_md(src: str) -> str:
    return f"<!-- {MARK} — 원천 {src} · 손으로 고치지 않는다(정본을 고치고 warehouse.py out) -->\n"


# ───────────────────────── scan · gaps
def scan(write: bool = False) -> dict[str, list[str]]:
    intake = load("intake") or {"version": 1, "files": [], "gaps": []}
    known = {f["path"]: f for f in intake["files"]}
    disk = inbound_files()
    res = {"새로": [], "바뀜": [], "사라짐": []}
    for rel, p in disk.items():
        h = sha256(p)
        f = known.get(rel)
        if f is None:
            res["새로"].append(rel)
            if write:
                intake["files"].append({"path": rel, "category": rel.split("/")[0], "sha256": h, "size": p.stat().st_size,
                                        "status": "미분석", "analyzed": "", "summary": "", "findings": []})
        elif f["sha256"] != h or f.get("status") == "삭제됨":
            res["바뀜"].append(rel)
            if write:
                f.update(sha256=h, size=p.stat().st_size, status="재분석 필요")
    for rel, f in known.items():
        if rel not in disk and f.get("status") != "삭제됨":
            res["사라짐"].append(rel)
            if write:
                f["status"] = "삭제됨"
    if write and (any(res.values()) or not (PRODUCT / "intake.json").exists()):
        PRODUCT.mkdir(parents=True, exist_ok=True)
        intake["files"].sort(key=lambda f: (CATEGORIES.index(f["category"]) if f["category"] in CATEGORIES else 99, f["path"]))
        dump("intake", intake)
    return res


def coverage(intake: dict) -> dict[str, int]:
    cov = {a: 0 for a in AREAS}
    for f in intake.get("files", []):
        if f.get("status") == "삭제됨":
            continue
        for e in f.get("findings", []):
            if e.get("area") in cov:
                cov[e["area"]] += 1
    for g in intake.get("gaps", []):  # 인터뷰로 답한 항목도 그 영역의 근거다
        if g.get("status") == "답함" and g.get("area") in cov:
            cov[g["area"]] += 1
    return cov


def gaps(intake: dict) -> tuple[list[str], list[dict]]:
    """(근거가 없는 영역, 열린 부족 항목)"""
    cov = coverage(intake)
    empty = [a for a, n in cov.items() if n == 0]
    open_ = [g for g in intake.get("gaps", []) if g.get("status") in ("열림", "인터뷰 중")]
    return empty, open_


# ───────────────────────── 검사
def _ids(items: list, key: str, pattern: str, where: str, errs: list[str]) -> set[str]:
    seen: set[str] = set()
    for it in items:
        i = it.get(key, "")
        if not re.fullmatch(pattern, i or ""):
            errs.append(f"{where}: ID 형식 {i!r} (형식 {pattern})")
        if i in seen:
            errs.append(f"{where}: ID 중복 {i}")
        seen.add(i)
    return seen


def check_intake(d: dict) -> list[str]:
    errs: list[str] = []
    ids: set[str] = set()
    for f in d.get("files", []):
        w = f"intake.json {f.get('path')}"
        if f.get("category") not in CATEGORIES:
            errs.append(f"{w}: 분류 {f.get('category')!r} — {CATEGORIES} 중 하나")
        if f.get("status") not in FILE_STATUS:
            errs.append(f"{w}: 상태 {f.get('status')!r} — {FILE_STATUS}")
        if f.get("status") == "분석됨" and not (f.get("summary") and f.get("analyzed")):
            errs.append(f"{w}: 분석됨인데 summary · analyzed 가 비었다")
        for e in f.get("findings", []):
            if not re.fullmatch(r"E-\d{3,}", e.get("id", "")) or e["id"] in ids:
                errs.append(f"{w}: 발견 ID {e.get('id')!r} 형식(E-001) 또는 중복")
            ids.add(e.get("id", ""))
            if e.get("area") not in AREAS:
                errs.append(f"{w} {e.get('id')}: 영역 {e.get('area')!r} — {AREAS}")
            if e.get("kind") not in FINDING_KINDS:
                errs.append(f"{w} {e.get('id')}: 종류 {e.get('kind')!r} — {FINDING_KINDS}")
            if not e.get("text"):
                errs.append(f"{w} {e.get('id')}: text 비었음")
    _ids(d.get("gaps", []), "id", r"G-\d{3,}", "intake.json gaps", errs)
    for g in d.get("gaps", []):
        if g.get("area") not in AREAS:
            errs.append(f"intake.json {g.get('id')}: 영역 {g.get('area')!r}")
        if g.get("status") not in GAP_STATUS:
            errs.append(f"intake.json {g.get('id')}: 상태 {g.get('status')!r} — {GAP_STATUS}")
        if g.get("status") == "답함" and not g.get("answer"):
            errs.append(f"intake.json {g.get('id')}: 답함인데 answer 가 비었다")
    return errs


def check_prd(d: dict) -> list[str]:
    errs: list[str] = []
    if d.get("status") not in DOC_STATUS:
        errs.append(f"prd.json: status {d.get('status')!r} — {DOC_STATUS}")
    if d.get("status") == "승인" and not (d.get("approved", {}).get("by") and d.get("approved", {}).get("date")):
        errs.append("prd.json: 승인인데 approved.by · approved.date 가 없다(승인 관문 — superpowers.md §4)")
    if not d.get("product", {}).get("name") or not d.get("product", {}).get("one_liner"):
        errs.append("prd.json: product.name · product.one_liner 필수")
    users = _ids(d.get("users", []), "id", r"U-\d{2,}", "prd.json users", errs)
    feats = d.get("features", [])
    if not feats:
        errs.append("prd.json: features 가 비었다")
    _ids(feats, "id", r"F-\d{3,}", "prd.json features", errs)
    for f in feats:
        if f.get("priority") not in PRIORITY:
            errs.append(f"prd.json {f.get('id')}: priority {f.get('priority')!r} — {PRIORITY}")
        for u in f.get("users", []):
            if u not in users:
                errs.append(f"prd.json {f.get('id')}: 없는 사용자 {u}")
        acs = f.get("acceptance", [])
        if not acs:
            errs.append(f"prd.json {f.get('id')}: 수용 기준(acceptance)이 없다 — 요구마다 확인 가능한 기준")
        _ids(acs, "id", re.escape(f.get("id", "")) + r"-AC\d+", f"prd.json {f.get('id')} acceptance", errs)
        if not f.get("sources"):
            errs.append(f"prd.json {f.get('id')}: sources(근거 — 입고 파일 · INT · REQ)가 없다")
    _ids(d.get("nfr", []), "id", r"N-\d{2,}", "prd.json nfr", errs)
    _ids(d.get("success_metrics", []), "id", r"M-\d{2,}", "prd.json success_metrics", errs)
    _ids(d.get("open_questions", []), "id", r"Q-\d{2,}", "prd.json open_questions", errs)
    return errs


def prd_index(prd: dict | None) -> tuple[set[str], set[str]]:
    if not prd:
        return set(), set()
    feats = {f["id"] for f in prd.get("features", [])}
    acs = {a["id"] for f in prd.get("features", []) for a in f.get("acceptance", [])}
    return feats, acs


def check_spec(d: dict, prd: dict | None) -> list[str]:
    errs: list[str] = []
    if d.get("status") not in DOC_STATUS:
        errs.append(f"spec.json: status {d.get('status')!r} — {DOC_STATUS}")
    if d.get("status") == "승인" and not (d.get("approved", {}).get("by") and d.get("approved", {}).get("date")):
        errs.append("spec.json: 승인인데 approved.by · approved.date 가 없다")
    if prd is None:
        errs.append("spec.json: 근거 PRD(docs/product/prd.json)가 없다 — /prd 먼저")
    elif d.get("prd_version") != prd.get("version"):
        errs.append(f"spec.json: prd_version {d.get('prd_version')!r} ≠ prd.json version {prd.get('version')!r} — PRD 가 바뀌었으면 SPEC 을 다시 맞춘다")
    feats, acs = prd_index(prd)
    fd = d.get("foundation", {})
    for k in ("frontend", "backend", "mobile"):
        v = fd.get("stack", {}).get(k)
        if not v or not v.get("choice") or not v.get("reason"):
            errs.append(f"spec.json foundation.stack.{k}: choice · reason 필수(/foundation 1단계 — 쓰지 않으면 choice '없음' + 이유)")
    arch = fd.get("architecture", {})
    if arch.get("style") not in ARCH or not arch.get("deploy") or not arch.get("reason"):
        errs.append(f"spec.json foundation.architecture: style({ARCH}) · deploy · reason 필수(/foundation 2단계)")
    db = fd.get("database", {})
    if not db.get("engine") or not db.get("migration") or not db.get("reason"):
        errs.append("spec.json foundation.database: engine · migration · reason 필수(/foundation 3단계)")
    cc = {c.get("concern"): c for c in fd.get("crosscutting", [])}
    for name in CROSSCUT:
        c = cc.get(name)
        if not c:
            errs.append(f"spec.json foundation.crosscutting: '{name}' 판정 없음(/foundation 4단계 — {CROSS_DECISION})")
        elif c.get("decision") not in CROSS_DECISION:
            errs.append(f"spec.json crosscutting '{name}': decision {c.get('decision')!r} — {CROSS_DECISION}")
        elif c["decision"] != "내장 채택" and not c.get("reason"):
            errs.append(f"spec.json crosscutting '{name}': {c['decision']} 은 reason 필수")
    services = {s.get("name") for s in d.get("services", [])}
    for s in d.get("services", []):
        for f in s.get("features", []):
            if f not in feats:
                errs.append(f"spec.json services {s.get('name')}: 없는 기능 {f}")
    for e in d.get("data_model", []):
        w = f"spec.json data_model {e.get('entity')}"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", e.get("entity", "")):
            errs.append(f"{w}: entity 는 영문 소문자 snake_case")
        if e.get("service") not in services:
            errs.append(f"{w}: 없는 서비스 {e.get('service')!r}")
        if not e.get("description"):
            errs.append(f"{w}: description(표의 의미) 필수 — DB 사전")
        for c in e.get("columns", []):
            if c.get("name") in ("id", "tenant_id"):
                errs.append(f"{w}.{c.get('name')}: id · tenant_id 는 자동(UUIDv7 · STD-TENANCY) — 쓰지 않는다")
            if not COLTYPE.match(str(c.get("type", ""))):
                errs.append(f"{w}.{c.get('name')}: type {c.get('type')!r} — string(N)|text|int|bigint|decimal(p,s)|bool|date|datetime|json|ref")
            if not c.get("comment"):
                errs.append(f"{w}.{c.get('name')}: comment(의미) 필수 — 대장 규칙")
    _ids(d.get("api", []), "id", r"API-\d{2,}", "spec.json api", errs)
    for a in d.get("api", []):
        if a.get("service") not in services:
            errs.append(f"spec.json {a.get('id')}: 없는 서비스 {a.get('service')!r}")
        if a.get("method") not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            errs.append(f"spec.json {a.get('id')}: method {a.get('method')!r}")
        if not re.fullmatch(r"[a-z][a-z0-9_-]*\.[a-z][a-z0-9_-]*", a.get("permission", "")):
            errs.append(f"spec.json {a.get('id')}: permission 은 <모듈>.<행위> (backend.md)")
        for f in a.get("features", []):
            if f not in feats:
                errs.append(f"spec.json {a.get('id')}: 없는 기능 {f}")
    for ev in d.get("events", []):
        if ev.get("producer") not in services:
            errs.append(f"spec.json events {ev.get('topic')}: 없는 발행 서비스 {ev.get('producer')!r}")
    _ids(d.get("screens", []), "id", r"S-\d{2,}", "spec.json screens", errs)
    for s in d.get("screens", []):
        for f in s.get("features", []):
            if f not in feats:
                errs.append(f"spec.json {s.get('id')}: 없는 기능 {f}")
    for t in d.get("test_map", []):
        if t.get("acceptance") not in acs:
            errs.append(f"spec.json test_map: 없는 수용 기준 {t.get('acceptance')!r}")
    covered = {f for x in d.get("api", []) + d.get("screens", []) for f in x.get("features", [])}
    if prd and d.get("status") == "승인":
        for f in sorted(feats - covered):
            errs.append(f"spec.json: PRD 기능 {f} 를 맡은 API · 화면이 없다")
        missing = sorted(acs - {t.get("acceptance") for t in d.get("test_map", [])})
        if missing:
            errs.append(f"spec.json: 테스트 맵에 없는 수용 기준 {missing}")
    return errs


def check_symmetry() -> list[str]:
    errs = []
    for side in ("inbound", "outbound"):
        base = WH / side
        if not base.exists():
            errs.append(f"docs/warehouse/{side} 없음")
            continue
        names = {p.name for p in base.iterdir() if p.is_dir()}
        for c in CATEGORIES:
            if c not in names:
                errs.append(f"docs/warehouse/{side}/{c} 없음 — 입고 · 출고는 같은 분류로 대칭")
        for n in sorted(names - set(CATEGORIES)):
            errs.append(f"docs/warehouse/{side}/{n}: 분류 목록(warehouse.py CATEGORIES)에 없는 폴더 — 추가하면 양쪽 · 목록을 함께")
    return errs


# ───────────────────────── 보기 · 출고 생성
def view_intake(d: dict) -> str:
    cov = coverage(d)
    empty, open_ = gaps(d)
    s = [mark_md("docs/product/intake.json"), "# 입고 분석 (intake)\n",
         "입고 자료(`docs/warehouse/inbound/`)를 분석한 결과. 파일 지문 · 요약 · 발견 · 부족 항목. 규약: `docs/product/README.md`\n",
         "## 1. 파일\n",
         table(["분류", "파일", "상태", "분석일", "요약"],
               [[f["category"], f["path"], f["status"], f.get("analyzed"), f.get("summary")] for f in d.get("files", [])]),
         "\n## 2. PRD 영역별 근거 수\n",
         table(["영역", "근거"], [[a, n if n else "0 — 인터뷰 필요"] for a, n in cov.items()]),
         "\n## 3. 발견\n",
         table(["ID", "영역", "종류", "내용", "원문 인용", "파일"],
               [[e["id"], e.get("area"), e.get("kind"), e.get("text"), e.get("quote"), f["path"]]
                for f in d.get("files", []) for e in f.get("findings", [])]),
         "\n## 4. 부족 항목 (인터뷰 재료)\n",
         f"근거가 없는 영역: {', '.join(empty) if empty else '없음'}\n\n",
         table(["ID", "영역", "질문", "왜 필요한가", "상태", "답", "인터뷰"],
               [[g["id"], g.get("area"), g.get("question"), g.get("why"), g.get("status"), g.get("answer"), g.get("interview")]
                for g in d.get("gaps", [])]),
         f"\n열린 항목 {len(open_)}건 → `/req-interview`\n"]
    return "".join(s)


def view_prd(d: dict) -> str:
    p = d.get("product", {})
    ap = d.get("approved") or {}
    s = [mark_md("docs/product/prd.json"), f"# PRD · {p.get('name', '')} v{d.get('version', '')}\n\n",
         f"> {p.get('one_liner', '')}\n\n",
         table(["항목", "값"], [["상태", d.get("status")], ["승인", f"{ap.get('by', '-')} · {ap.get('date', '-')}"],
                              ["근거", ", ".join(d.get("sources", []))]]),
         "\n## 1. 배경 · 왜 지금\n", f"{p.get('background', '-')}\n\n{p.get('why_now', '')}\n",
         "\n## 2. 목표 · 비목표 · 반목표\n",
         table(["구분", "내용"], [["목표", x] for x in d.get("goals", [])] + [["비목표", x] for x in d.get("non_goals", [])]
               + [["반목표(돌아가도 실패)", x] for x in d.get("anti_goals", [])]),
         "\n## 3. 성공 지표\n", table(["ID", "지표", "목표"], [[m["id"], m.get("metric"), m.get("target")] for m in d.get("success_metrics", [])]),
         "\n## 4. 사용자 · 역할\n", table(["ID", "역할", "설명", "기기 · 장소"],
                                       [[u["id"], u.get("role"), u.get("description"), u.get("devices")] for u in d.get("users", [])]),
         "\n## 5. 기능 요구\n"]
    s.append(table(["ID", "기능", "우선순위", "사용자", "근거"],
                   [[f["id"], f.get("title"), f.get("priority"), f.get("users"), f.get("sources")] for f in d.get("features", [])]))
    for f in d.get("features", []):
        s.append(f"\n### {f['id']} · {f.get('title', '')}\n{f.get('description', '')}\n\n")
        s.append(table(["수용 기준", "내용", "확인 방법"], [[a["id"], a.get("criterion"), a.get("test")] for a in f.get("acceptance", [])]))
    s += ["\n## 6. 비기능 요구\n", table(["ID", "분류", "요구", "수용 기준"],
                                    [[n["id"], n.get("category"), n.get("requirement"), n.get("acceptance")] for n in d.get("nfr", [])]),
          "\n## 7. 제약\n", "".join(f"- {c}\n" for c in d.get("constraints", [])) or "(없음)\n",
          "\n## 8. 가정 (Claude 판단 포함)\n", table(["가정", "정한 사람"], [[a.get("text"), a.get("by")] for a in d.get("assumptions", [])]),
          "\n## 9. 미결 질문\n", table(["ID", "질문", "누구 몫", "기한", "답"],
                                   [[q["id"], q.get("question"), q.get("owner"), q.get("due"), q.get("answer")] for q in d.get("open_questions", [])])]
    return "".join(s)


def tenancy_applied() -> bool:
    return project().get("standards", {}).get("STD-TENANCY-001", {}).get("decision") == "적용"


def view_spec(d: dict) -> str:
    fd = d.get("foundation", {})
    st = fd.get("stack", {})
    ap = d.get("approved") or {}
    stds = project().get("standards", {})
    s = [mark_md("docs/product/spec.json"), f"# SPEC v{d.get('version', '')} (PRD v{d.get('prd_version', '')} 기준)\n\n",
         table(["항목", "값"], [["상태", d.get("status")], ["승인", f"{ap.get('by', '-')} · {ap.get('date', '-')}"],
                              ["기반 결정 ADR", fd.get("adr", [])]]),
         "\n## 1. 기반 (/foundation)\n### 1.1 언어 · 프레임워크\n",
         table(["층", "선택", "이유"], [[k, st.get(k, {}).get("choice"), st.get(k, {}).get("reason")] for k in ("frontend", "backend", "mobile")]),
         "\n### 1.2 아키텍처 · 배포\n",
         table(["스타일", "배포", "이유"], [[fd.get("architecture", {}).get(k) for k in ("style", "deploy", "reason")]]),
         "\n### 1.3 DB · 영속성\n",
         table(["엔진", "마이그레이션", "이유"], [[fd.get("database", {}).get(k) for k in ("engine", "migration", "reason")]]),
         "\n### 1.4 횡단관심사 채택\n",
         table(["관심사", "판정", "Nova 자산 · 구현", "이유"],
               [[c.get("concern"), c.get("decision"), c.get("asset") or CROSSCUT.get(c.get("concern"), ""), c.get("reason")]
                for c in fd.get("crosscutting", [])]),
         "\n### 1.5 표준 판정 (정본 `nova.project.json` standards)\n",
         table(["표준", "판정", "이유"], [[k, v.get("decision"), v.get("reason")] for k, v in stds.items()]),
         "\n## 2. 서비스\n", table(["서비스", "그룹", "책임", "기능"],
                                [[x.get("name"), x.get("group"), x.get("responsibility"), x.get("features")] for x in d.get("services", [])]),
         "\n## 3. 데이터 모델\n기본키 `id` 는 UUIDv7(CHAR(36), ADR-003)"
         + (", 업무 표에는 `tenant_id`(STD-TENANCY-001)" if tenancy_applied() else "") + " — 자동으로 붙는다.\n"]
    for e in d.get("data_model", []):
        s.append(f"\n### {e['entity']} ({e.get('service')}) — {e.get('description', '')}\n")
        s.append(table(["칸", "형식", "비어도 됨", "의미", "참조"],
                       [[c.get("name"), c.get("type"), "예" if c.get("nullable") else "아니오", c.get("comment"), c.get("ref")]
                        for c in e.get("columns", [])]))
    s += ["\n## 4. API\n", table(["ID", "메서드", "경로", "서비스", "권한", "기능", "요청", "응답", "오류"],
                              [[a["id"], a.get("method"), a.get("path"), a.get("service"), a.get("permission"), a.get("features"),
                                a.get("request"), a.get("response"), a.get("errors")] for a in d.get("api", [])]),
          "\n## 5. 이벤트\n", table(["토픽", "발행", "구독", "내용"],
                                [[e.get("topic"), e.get("producer"), e.get("consumers"), e.get("payload")] for e in d.get("events", [])]),
          "\n## 6. 화면\n", table(["ID", "이름", "앱", "경로", "템플릿", "기능"],
                               [[x["id"], x.get("name"), x.get("app"), x.get("route"), x.get("template"), x.get("features")] for x in d.get("screens", [])]),
          "\n## 7. 테스트 맵 (수용 기준 ↔ 테스트)\n", table(["수용 기준", "테스트"], [[t.get("acceptance"), t.get("test")] for t in d.get("test_map", [])]),
          "\n## 8. 미결 질문\n", table(["ID", "질문", "누구 몫", "답"],
                                   [[q.get("id"), q.get("question"), q.get("owner"), q.get("answer")] for q in d.get("open_questions", [])])]
    return "".join(s)


def sql_type(t: str) -> str:
    if t.startswith("string("):
        return "VARCHAR" + t[len("string"):]
    if t.startswith("decimal("):
        return "DECIMAL" + t[len("decimal"):]
    return SQLTYPE[t]


def q(s) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def ddl(d: dict) -> tuple[str, str]:
    slug = project().get("slug", "nova")
    head = f"-- {MARK} — 원천 docs/product/spec.json data_model · 손으로 고치지 않는다\n" \
           "-- 🔴 초안이다: 실행 DB 적용은 사람 승인 후 건별로(docs/warehouse/inbound/db-sql 규칙). 운영 전환은 Alembic 마이그레이션\n"
    up, down = [head + "-- 스키마 초안 (MariaDB)\n"], [head + "-- 되돌림 — schema.sql 의 역순\n"]
    by_svc: dict[str, list] = {}
    for e in d.get("data_model", []):
        by_svc.setdefault(e.get("service", ""), []).append(e)
    for svc, ents in by_svc.items():
        db = f"{slug}_{svc}".replace("-", "_")
        up.append(f"\n-- 서비스 {svc} — 자기 DB 만 쓴다(backend.md)\nCREATE DATABASE IF NOT EXISTS `{db}` DEFAULT CHARACTER SET utf8mb4;\nUSE `{db}`;\n")
        for e in ents:
            cols = ["  `id` CHAR(36) NOT NULL COMMENT 'UUIDv7 기본키(ADR-003)'"]
            if tenancy_applied():
                cols.append("  `tenant_id` VARCHAR(40) NULL COMMENT '테넌트(STD-TENANCY-001)'")
            for c in e.get("columns", []):
                null = "NULL" if c.get("nullable") else "NOT NULL"
                cols.append(f"  `{c['name']}` {sql_type(c['type'])} {null} COMMENT {q(c.get('comment', ''))}")
            cols.append("  PRIMARY KEY (`id`)")
            if tenancy_applied():
                cols.append("  KEY `ix_tenant` (`tenant_id`)")
            cols += [f"  KEY `ix_{c['name']}` (`{c['name']}`)" for c in e.get("columns", []) if c["type"] == "ref"]
            up.append(f"CREATE TABLE IF NOT EXISTS `{e['entity']}` (\n" + ",\n".join(cols)
                      + f"\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT={q(e.get('description', ''))};\n")
        down.append(f"\nUSE `{db}`;\n" + "".join(f"DROP TABLE IF EXISTS `{e['entity']}`;\n" for e in reversed(ents)))
    return "".join(up), "".join(down)


def view_acceptance(prd: dict) -> str:
    rows = [[a["id"], f.get("title"), a.get("criterion"), a.get("test"), "☐", ""] for f in prd.get("features", []) for a in f.get("acceptance", [])]
    rows += [[n["id"], n.get("category"), n.get("acceptance") or n.get("requirement"), "", "☐", ""] for n in prd.get("nfr", [])]
    return (mark_md("docs/product/prd.json") + f"# 인수 점검표 · {prd.get('product', {}).get('name', '')} (PRD v{prd.get('version', '')})\n\n"
            "납품물이 PRD 수용 기준을 충족하는지 하나씩 확인한다. 확인 칸에 ☑ 와 확인자 · 날짜를 적는다.\n\n"
            + table(["기준", "기능 · 분류", "내용", "확인 방법", "확인", "확인자 · 날짜"], rows))


def view_gaps(intake: dict, prd: dict | None) -> str:
    empty, open_ = gaps(intake)
    s = [mark_md("docs/product/intake.json"), "# 부족한 것 질문표\n\n",
         "받은 자료만으로는 알 수 없는 것들입니다. 아는 만큼 답 칸에 적어 돌려주시면 됩니다(모르면 \"모름\"도 답입니다).\n\n",
         "## 1. 아직 자료가 없는 영역\n", "".join(f"- {a}\n" for a in empty) or "(없음)\n",
         "\n## 2. 질문\n", table(["번호", "영역", "질문", "왜 묻나", "답"],
                               [[g["id"], g.get("area"), g.get("question"), g.get("why"), ""] for g in open_])]
    if prd:
        oq = [x for x in prd.get("open_questions", []) if not x.get("answer")]
        s += ["\n## 3. PRD 미결 질문\n", table(["번호", "질문", "누구 몫", "기한", "답"],
                                          [[x["id"], x.get("question"), x.get("owner"), x.get("due"), ""] for x in oq])]
    return "".join(s)


def view_category(intake: dict, cat: str) -> str:
    files = [f for f in intake.get("files", []) if f["category"] == cat and f.get("status") != "삭제됨"]
    s = [mark_md("docs/product/intake.json"), f"# 입고 분석 · {cat}\n\n",
         f"`docs/warehouse/inbound/{cat}/` 자료의 분석 결과. 전체 보고는 `outbound/etc/intake_report.md`.\n\n"]
    if not files:
        s.append("(이 분류에 받은 자료가 없다)\n")
    for f in files:
        s.append(f"## {f['path']} — {f.get('status')}\n{f.get('summary') or '(아직 분석하지 않았다 — /intake)'}\n\n")
        s.append(table(["ID", "영역", "종류", "내용", "원문 인용"],
                       [[e["id"], e.get("area"), e.get("kind"), e.get("text"), e.get("quote")] for e in f.get("findings", [])]))
        s.append("\n")
    return "".join(s)


# md → html (파일 하나로 열리는 보기 — 외부 스크립트 없음)
# 색은 디자인 토큰 원천(design/tokens/brand.tokens.json)에서 — 출고본에 hex 사본을 두지 않는다(plan_REQ_04 T04-5.08 · R15).
# 토큰 값이 바뀌면 출고본도 달라지므로 warehouse check 의 드리프트로 잡힌다. 외부 파일 없이 열리게 :root 에 값을 풀어 넣는다
CSS_COLORS = ("bg.surface", "bg.subtle", "text.primary", "text.muted", "text.brand", "border.subtle")
CSS_RULES = """body{margin:0;background:var(--color-bg-surface);color:var(--color-text-primary);font:15px/1.6 system-ui,"Malgun Gothic","Apple SD Gothic Neo",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1,h2,h3{line-height:1.3}h2{border-bottom:1px solid var(--color-border-subtle);padding-bottom:4px;margin-top:32px}
table{border-collapse:collapse;width:100%;margin:8px 0;display:block;overflow-x:auto}th,td{border:1px solid var(--color-border-subtle);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--color-bg-subtle)}code{background:var(--color-bg-subtle);padding:1px 4px;border-radius:4px}blockquote{margin:0;padding:4px 12px;border-left:3px solid var(--color-text-brand);color:var(--color-text-muted)}
pre{background:var(--color-bg-subtle);padding:12px;overflow-x:auto}"""


def css() -> str:
    """출고 HTML 의 <style> — :root 에 --color-*(라이트, 다크는 prefers-color-scheme) + 규칙 본문(var(--color-…) 만)."""
    import gen_tokens as gt
    tree = gt.load()

    def decl(mode: str) -> str:
        out = []
        for name in CSS_COLORS:
            node = tree["semantic"]["color"]
            for part in name.split("."):
                node = node[part]
            out.append(f"--color-{gt.kebab(tuple(name.split('.')))}:{gt.value_of(tree, node, mode)}")
        return ";".join(out)
    return f":root{{{decl('light')}}}\n@media (prefers-color-scheme:dark){{:root{{{decl('dark')}}}}}\n{CSS_RULES}"


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)


def md_to_html(md: str, title: str) -> str:
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("<!--"):
            out.append(ln)
        elif ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(lines[i + 1:j])) + "</pre>")
            i = j
        elif m := re.match(r"^(#{1,4}) (.*)", ln):
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            i -= 1
            cells = [[c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", r.strip())[1:-1]] for r in rows]
            body = [c for k, c in enumerate(cells) if k != 1 or not all(re.fullmatch(r"-+", x) for x in c)]
            h = "".join(f"<th>{inline(x)}</th>" for x in body[0])
            b = "".join("<tr>" + "".join(f"<td>{inline(x)}</td>" for x in r) + "</tr>" for r in body[1:])
            out.append(f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            i -= 1
            out.append("<ul>" + "".join(items) + "</ul>")
        elif ln.startswith("> "):
            out.append(f"<blockquote>{inline(ln[2:])}</blockquote>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return (f"<!doctype html>\n<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title><style>{css()}</style></head><body><main>\n" + "\n".join(out) + "\n</main></body></html>\n")


def expected() -> dict[Path, str]:
    """만들어야 할 파생본 전부 {경로: 내용}. 정본이 없으면 그 파생본은 없다."""
    intake, prd, spec = load("intake"), load("prd"), load("spec")
    o = WH / "outbound"
    files: dict[Path, str] = {}

    def js(d):
        return json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    if intake is not None:
        rep = view_intake(intake)
        files[PRODUCT / "intake.md"] = rep
        files[o / "etc" / "intake_report.md"] = rep
        files[o / "checklist" / "gaps.md"] = view_gaps(intake, prd)
        for c in CATEGORIES:
            files[o / c / f"analysis_{c}.md"] = view_category(intake, c)
    form = WH / "inbound" / "checklist" / "checklist.html"
    if form.exists():  # 고객에게 건네는 요구 체크리스트(자료에서 채운 판) — 원본은 inbound 쪽(checklist.py build)
        files[o / "checklist" / "checklist.html"] = form.read_text(encoding="utf-8")
    if prd is not None:
        v = view_prd(prd)
        files[PRODUCT / "prd.md"] = v
        files[o / "prd" / "prd.md"] = v
        files[o / "prd" / "prd.html"] = md_to_html(v, f"PRD · {prd.get('product', {}).get('name', '')}")
        files[o / "prd" / "prd.json"] = js(prd)
        files[o / "checklist" / "acceptance.md"] = view_acceptance(prd)
    if spec is not None:
        v = view_spec(spec)
        files[PRODUCT / "spec.md"] = v
        files[o / "spec" / "spec.md"] = v
        files[o / "spec" / "spec.html"] = md_to_html(v, "SPEC")
        files[o / "spec" / "spec.json"] = js(spec)
        if spec.get("data_model"):
            up, down = ddl(spec)
            files[o / "db-sql" / "schema.sql"] = up
            files[o / "db-sql" / "rollback.sql"] = down
    return files


def generated_on_disk() -> set[Path]:
    """표시(MARK)가 있거나 파생 json 이름인 기존 파일 — 원천이 사라지면 지워야 할 것."""
    found = set()
    for base in (PRODUCT, WH / "outbound"):
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.name == "README.md":
                continue
            if p.suffix in (".md", ".html", ".sql") and MARK in p.read_text(encoding="utf-8", errors="ignore")[:300]:
                found.add(p)
            elif p.parent == WH / "outbound" / "prd" and p.name == "prd.json" or p.parent == WH / "outbound" / "spec" and p.name == "spec.json":
                found.add(p)
    return found


def out(check: bool = False) -> list[str]:
    exp = expected()
    errs = []
    for p, text in exp.items():
        cur = p.read_text(encoding="utf-8") if p.exists() else None
        if cur != text:
            if check:
                errs.append(f"출고본이 정본과 다르다(드리프트): {p.relative_to(ROOT).as_posix()} → uv run python scripts/warehouse.py out")
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8", newline="\n")
    for p in sorted(generated_on_disk() - set(exp)):
        if check:
            errs.append(f"원천이 없는 생성물: {p.relative_to(ROOT).as_posix()} → warehouse.py out 이 지운다")
        else:
            p.unlink()
    return errs


def check() -> list[str]:
    errs = check_symmetry()
    intake, prd, spec = load("intake"), load("prd"), load("spec")
    if intake is not None:
        errs += check_intake(intake)
    if prd is not None:
        errs += check_prd(prd)
    if spec is not None:
        errs += check_spec(spec, prd)
    if not errs:
        errs += out(check=True)
    return errs


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").add_argument("--write", action="store_true")
    sub.add_parser("gaps")
    sub.add_parser("out").add_argument("--check", action="store_true")
    sub.add_parser("check")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        res = scan(a.write)
        for k, v in res.items():
            for f in v:
                print(f"{k}: {f}")
        if not any(res.values()):
            print("✓ 입고 변화 없음")
        elif not a.write:
            print("→ 반영: uv run python scripts/warehouse.py scan --write (그다음 /intake 로 분석)")
        return 0
    if a.cmd == "gaps":
        intake = load("intake")
        if intake is None:
            print("입고 분석이 없다 — /intake 먼저")
            return 0
        empty, open_ = gaps(intake)
        print("근거가 없는 영역:", ", ".join(empty) if empty else "없음")
        for g in open_:
            print(f"{g['id']} [{g.get('area')}] {g.get('question')} ({g.get('status')})")
        pend = [f["path"] for f in intake.get("files", []) if f.get("status") in ("미분석", "재분석 필요")]
        if pend:
            print("아직 분석하지 않은 파일:", ", ".join(pend))
        return 0
    if a.cmd == "out":
        errs = out(check=a.check)
        for e in errs:
            print("✗", e)
        if not errs:
            print("✓ 출고본 최신" if a.check else "✓ 출고본을 만들었다")
        return 1 if errs else 0
    errs = check()
    for e in errs:
        print("✗", e)
    pend = scan(write=False)
    for k in ("새로", "바뀜"):
        for f in pend[k]:
            print(f"⚠ 입고 {k}: {f} — /intake 로 분석(검사를 막지는 않는다)")
    if not errs:
        print("✓ 자료 창고 · PRD/SPEC 정본 · 출고본 정상")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
