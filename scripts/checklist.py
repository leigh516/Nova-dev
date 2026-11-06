#!/usr/bin/env python3
"""요구 체크리스트(checklist.html) — 계층형 클릭 질문 폼 · 자료에서 자동 채움 · JSON 정본 + md 보기.

  uv run python scripts/checklist.py build            폼 만들기: 질문 트리 + 자동 채움(docs/product/checklist_prefill.json) + 디자인 토큰
                                                      → docs/warehouse/inbound/checklist/checklist.html (파일 하나로 열림)
  uv run python scripts/checklist.py serve [--port N] 폼을 열고 [저장]을 저장소에 바로 기록(checklist_YYYYMMDD_NN.json + .md)
  uv run python scripts/checklist.py md               받은 checklist_*.json 마다 읽기 쉬운 checklist_*.md 를 만든다
  uv run python scripts/checklist.py import           완료(status: complete)된 체크리스트 → docs/product/intake.json 발견 · 부족 항목
  uv run python scripts/checklist.py check            트리 · 자동 채움 · 폼 · md 가 최신이고 올바른지 (lint)
  uv run python scripts/checklist.py mockups          입고 목업 · 캡처 목록(inbound/html-mockup · screenshot)을 자동 채움에 맞춘다 → build

질문 트리 정본: scripts/checklist_form/tree.json · 규칙: docs/warehouse/inbound/checklist/README.md
"""
from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import mimetypes
import hashlib
import json
import re
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT  # noqa: E402
import warehouse as wh  # noqa: E402

FORM_DIR = Path(__file__).resolve().parent / "checklist_form"
TOKENS_CSS = ROOT / "web" / "packages" / "ui" / "src" / "tokens.css"
MARK = "생성물: scripts/checklist.py"
UNKNOWN = "_unknown"
STATES = ["prefill", "confirmed", "customer", "unknown"]
STATE_KO = {"prefill": "자료에서 채움 · 확인 전", "confirmed": "자료에서 채움 · 고객 확인", "customer": "고객 답", "unknown": "건너뜀 · 나중에"}
LV_KO = {1: "기본", 2: "자세히", 3: "전문가"}
HEX = re.compile(r"#[0-9A-Fa-f]{6}")
PREVIEW_KINDS = {"radius", "shadow", "density", "font", "size", "text", "theme", "layout", "list", "style", "shape", "swatch", "pos"}
# 견본 색은 데이터의 HEX(고객이 볼 실제 색 — 색 견본과 같은 방식) 아니면 의미 토큰 변수만(REQ-261104-18)
SWATCH = re.compile(r"#[0-9A-Fa-f]{6}|var\(--color-[a-z0-9-]+\)")
STYLE_RADIUS = {"sm", "md", "lg", "xl", "pill"}
STYLE_GAP = {"1", "2", "3", "4"}
# [Nova 보기] 갤러리 카드 ID — 폼(template.html GALLERY)과 같아야 한다(test_checklist 가 맞춘다)
GALLERY_IDS = {"intro", "palette", "shell", "list", "form", "detail", "login", "confirm", "toast", "badge", "stat",
               "empty", "controls", "shortcut", "stack"}
# 표준 디자인 킷(REQ-261106-04-2) — 킷 목록 정본은 catalog.json 하나. 체크리스트 보기는 폼을 만들 때 여기서 채운다(두 원천이 어긋나지 않게)
KITS_CATALOG = ROOT / "design" / "tokens" / "kits" / "catalog.json"
PROJECT_JSON = ROOT / "nova.project.json"
KIT_QID = "design.kit"
OPTIONS_FROM = {"kits"}
# 킷 견본 px → 토큰 단계. 폼의 style 견본은 토큰 단계(var(--radius-md) …)로 그리므로 가장 가까운 Nova 기본 단계로 옮긴다
RADIUS_PX = {"sm": 6, "md": 10, "lg": 14, "xl": 20, "pill": 999}
GAP_PX = {"1": 4, "2": 8, "3": 12, "4": 16}
KIT_RESET = "/foundation 5단계에서 확인하고 필요하면 `python nova.py kit use <id>` 로 다시 설정"


def contrast(a: str, b: str) -> float:
    """WCAG 2.x 명도 대비 — 폼(JS)과 같은 식."""
    def lum(h: str) -> float:
        rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)
FILE_RE = re.compile(r"^checklist_(\d{8})_(\d{2})$")


def ck_dir() -> Path:
    return wh.WH / "inbound" / "checklist"


def form_path() -> Path:
    return ck_dir() / "checklist.html"


def prefill_path() -> Path:
    return wh.PRODUCT / "checklist_prefill.json"


def tree() -> dict:
    """질문 트리 — `options_from: kits` 질문의 보기는 킷 목록(catalog.json)에서 채운다."""
    t = json.loads((FORM_DIR / "tree.json").read_text(encoding="utf-8"))
    opts = kit_options()

    def walk(items):
        for q in items:
            if q.get("options_from") == "kits":
                q["options"] = copy.deepcopy(opts)
            for o in q.get("options", []):
                walk(o.get("children", []))
    for s in t.get("sections", []):
        walk(s.get("questions", []))
    return t


def kits() -> list[dict]:
    """킷 목록 정본(design/tokens/kits/catalog.json) — 없으면 빈 목록(check_tree 가 잡는다)."""
    if not KITS_CATALOG.exists():
        return []
    return json.loads(KITS_CATALOG.read_text(encoding="utf-8")).get("kits", [])


def _step(v, scale: dict) -> tuple[str, float | None]:
    """견본 값 → (토큰 단계, px). 단계 이름이면 그대로, 숫자(px)면 가장 가까운 단계."""
    if str(v) in scale:
        return str(v), float(scale[str(v)])
    try:
        px = float(v)
    except (TypeError, ValueError):
        return str(v), None   # 잘못된 값은 그대로 두어 check_tree 의 style 검사가 잡게 한다
    return min(scale, key=lambda k: abs(scale[k] - px)), px


def kit_options() -> list[dict]:
    out = []
    for k in kits():
        pv = k.get("preview") or {}
        r, rpx = _step(pv.get("radius"), RADIUS_PX)
        g, gpx = _step(pv.get("gap"), GAP_PX)
        o = {"id": k.get("id"), "label": k.get("label") or k.get("id"), "desc": k.get("desc", ""),
             "preview": {"kind": "style", "value": k.get("id"), "hex": pv.get("hex", ""), "radius": r, "gap": g,
                         "dark": bool(pv.get("dark")), "px": {"radius": rpx, "gap": gpx}},
             "kit": {"tokens": k.get("tokens"), "gaps": list(k.get("gaps", [])), "status": k.get("status", "")}}
        if k.get("id") == "nova":
            o.update(rec="Nova 기본", gallery="palette")
        if k.get("gaps"):
            o["warn"] = f"Nova 에 아직 없는 부품 {len(k['gaps'])}개 — 받은 뒤 부족 항목으로 묻는다"
        out.append(o)
    return out


def check_kits(t: dict) -> list[str]:
    """킷 질문 · 목록 대조 — 갭은 '화면 부품 · Nova 에 없는 부품'(parts.need) 보기 ID, 토큰 파일은 실제로 있어야 한다."""
    errs = []
    qs, _, _ = index(t)
    need = {o["id"] for o in qs.get("parts.need", {}).get("options", [])}
    for q in qs.values():
        if "options_from" not in q:
            continue
        w = f"tree.json {q['id']}"
        if q["options_from"] not in OPTIONS_FROM:
            errs.append(f"{w}: options_from 은 {sorted(OPTIONS_FROM)}")
            continue
        if q.get("type") != "one":
            errs.append(f"{w}: 킷 질문은 type one")
        ids = [o.get("id") for o in q.get("options", [])]
        if not ids:
            errs.append(f"{w}: 킷 목록이 없거나 비었다 → {KITS_CATALOG.relative_to(ROOT).as_posix()}")
        elif "nova" not in ids:
            errs.append(f"{w}: 킷 목록에 기본 킷 nova 가 없다")
        for o in q.get("options", []):
            for gp in o["kit"]["gaps"]:
                if gp not in need:
                    errs.append(f"catalog.json {o['id']}: 갭 {gp!r} 는 parts.need 보기 ID 가 아니다")
            tok = o["kit"]["tokens"]
            if tok and not (KITS_CATALOG.parent / tok).is_file():
                errs.append(f"catalog.json {o['id']}: 토큰 파일 {tok} 가 없다")
    return errs


def index(t: dict) -> tuple[dict, dict, dict]:
    """(질문 id → 질문, 질문 id → (부모 질문 id, 보기 id), 질문 id → 섹션)"""
    qs, parent, sec = {}, {}, {}

    def walk(items, par, sid):
        for q in items:
            qs[q["id"]] = q
            sec[q["id"]] = sid
            if par:
                parent[q["id"]] = par
            for o in q.get("options", []):
                walk(o.get("children", []), (q["id"], o["id"]), sid)
    for s in t["sections"]:
        walk(s["questions"], None, s)
    return qs, parent, sec


# ───────────────────────── 검사
def check_tree(t: dict) -> list[str]:
    errs, seen = [], set()

    def walk(items, where):
        for q in items:
            w = f"tree.json {q.get('id')}"
            if q.get("id") in seen or not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+", q.get("id", "")):
                errs.append(f"{w}: 질문 ID 중복 또는 형식(섹션.이름)")
            seen.add(q.get("id"))
            if not q.get("id", "").startswith(where + "."):
                errs.append(f"{w}: 질문 ID 는 섹션 ID '{where}.' 로 시작한다")
            if q.get("type") not in ("one", "many", "text", "rows", "color", "mockups"):
                errs.append(f"{w}: type 은 one|many|text|rows|color|mockups")
            if q.get("type") == "mockups" and not t.get("mockup_levels"):
                errs.append(f"{w}: mockups 질문에는 tree.json mockup_levels(채택 수준)가 필요하다")
            for o in q.get("options", []):
                if o.get("gallery") and o["gallery"] not in GALLERY_IDS:
                    errs.append(f"{w}.{o.get('id')}: gallery {o['gallery']!r} — [Nova 보기] 카드 {sorted(GALLERY_IDS)}")
            if q.get("type") == "color":
                pre = q.get("presets", [])
                if len(pre) < 2 or len({p.get("id") for p in pre}) != len(pre) or not all(HEX.fullmatch(p.get("hex", "")) for p in pre):
                    errs.append(f"{w}: color 질문은 견본(presets) 2개 이상 · ID 가 겹치지 않고 hex 는 #RRGGBB")
            for o in q.get("options", []):
                pv = o.get("preview")
                if pv and pv.get("kind") not in PREVIEW_KINDS:
                    errs.append(f"{w}.{o.get('id')}: preview kind {pv.get('kind')!r} — {sorted(PREVIEW_KINDS)}")
                if pv and pv.get("kind") == "swatch" and (not isinstance(pv.get("value"), list) or not pv["value"]
                                                          or not all(SWATCH.fullmatch(str(c)) for c in pv["value"])):
                    errs.append(f"{w}.{o.get('id')}: swatch 견본은 #RRGGBB 또는 var(--color-…) 목록")
                if pv and pv.get("kind") == "style" and (not HEX.fullmatch(pv.get("hex", "")) or pv.get("radius") not in STYLE_RADIUS
                                                         or str(pv.get("gap")) not in STYLE_GAP):
                    errs.append(f"{w}.{o.get('id')}: style 견본은 hex #RRGGBB · radius {sorted(STYLE_RADIUS)} · gap {sorted(STYLE_GAP)}(토큰 단계)")
            if q.get("type") == "rows":
                cols = q.get("columns", [])
                if not cols or len({c.get("id") for c in cols}) != len(cols):
                    errs.append(f"{w}: rows 질문은 columns(열)가 있고 열 ID 가 겹치지 않아야 한다")
                for c in cols:
                    if c.get("type") not in ("text", "one") or (c.get("type") == "one" and len(c.get("options", [])) < 2):
                        errs.append(f"{w}.{c.get('id')}: 열 type 은 text|one(보기 2개 이상)")
            if q.get("feeds") and not re.fullmatch(r"(foundation|standards|design)\.\S.*", q["feeds"]):
                errs.append(f"{w}: feeds 는 foundation.… · standards.… · design.…")
            for o in q.get("options", []):
                if o.get("rec") and o["rec"] not in t.get("badges", {}):
                    errs.append(f"{w}.{o.get('id')}: rec 배지 {o['rec']!r} 의 뜻이 tree.json badges 에 없다")
            if q.get("area") not in wh.AREAS:
                errs.append(f"{w}: area {q.get('area')!r} — PRD 영역 {wh.AREAS}")
            if q.get("lv") not in (1, 2, 3):
                errs.append(f"{w}: lv 는 1(기본) · 2(자세히) · 3(전문가)")
            if not q.get("q"):
                errs.append(f"{w}: 질문 문구(q)가 없다")
            opts = q.get("options", [])
            if q.get("type") in ("text", "rows") and opts:
                errs.append(f"{w}: text · rows 질문에는 보기를 두지 않는다")
            if q.get("type") in ("one", "many") and len(opts) < 2:
                errs.append(f"{w}: 보기가 2개 이상이어야 한다")
            ids = [o.get("id") for o in opts]
            if len(ids) != len(set(ids)) or UNKNOWN in ids:
                errs.append(f"{w}: 보기 ID 중복 또는 예약어({UNKNOWN})")
            for o in opts:
                walk(o.get("children", []), where)
    sids = [s["id"] for s in t.get("sections", [])]
    if len(sids) != len(set(sids)):
        errs.append("tree.json: 섹션 ID 중복")
    for s in t.get("sections", []):
        walk(s.get("questions", []), s["id"])
    terms = [g.get("term") for g in t.get("glossary", [])]
    if len(terms) != len(set(terms)) or any(not g.get("desc") for g in t.get("glossary", [])):
        errs.append("tree.json glossary: 용어가 겹치거나 풀이(desc)가 비었다")
    errs += check_kits(t)
    return errs


def check_answers(answers: dict, t: dict, where: str, *, prefill: bool = False) -> list[str]:
    qs, _, _ = index(t)
    errs = []
    for qid, a in answers.items():
        q = qs.get(qid)
        if not q:
            errs.append(f"{where}: 트리에 없는 질문 {qid}")
            continue
        if not isinstance(a, dict):
            errs.append(f"{where} {qid}: 답은 {{value, state, …}} 객체여야 한다")
            continue
        v = a.get("value")
        if not prefill and a.get("state") not in STATES:
            errs.append(f"{where} {qid}: state {a.get('state')!r} — {STATES}")
        if v == UNKNOWN:
            continue
        opt = {o["id"] for o in q.get("options", [])}
        if q["type"] == "text" and not isinstance(v, str):
            errs.append(f"{where} {qid}: 글 답은 문자열")
        elif q["type"] == "one" and (not isinstance(v, str) or v not in opt):
            errs.append(f"{where} {qid}: 없는 보기 {v!r} — {sorted(opt)}")
        elif q["type"] == "mockups":
            levels = {x["id"] for x in t.get("mockup_levels", [])}
            if not isinstance(v, dict) or not all(isinstance(x, dict) and x.get("level", "") in levels | {""} for x in v.values()):
                errs.append(f"{where} {qid}: 목업 답은 {{파일: {{level, note}}}} — level 은 {sorted(levels)}")
        elif q["type"] == "color":
            if not isinstance(v, dict) or not HEX.fullmatch(str(v.get("hex", ""))):
                errs.append(f"{where} {qid}: 색 답은 {{hex: '#RRGGBB', preset, text_hex}}")
            elif v.get("preset") and v["preset"] not in {p["id"] for p in q.get("presets", [])}:
                errs.append(f"{where} {qid}: 없는 견본 {v['preset']!r}")
        elif q["type"] == "rows":
            cols = {c["id"]: c for c in q.get("columns", [])}
            if not isinstance(v, list) or not all(isinstance(r, dict) and set(r) <= set(cols) for r in v):
                errs.append(f"{where} {qid}: 표 답은 열 ID 를 키로 하는 줄 목록")
            else:
                for r in v:
                    for k, x in r.items():
                        if cols[k]["type"] == "one" and x and x not in {o["id"] for o in cols[k]["options"]}:
                            errs.append(f"{where} {qid}: 열 {k} 에 없는 보기 {x!r}")
        elif q["type"] == "many" and (not isinstance(v, list) or set(v) - opt):
            errs.append(f"{where} {qid}: 보기 목록이 아니거나 없는 보기 {sorted(set(v or []) - opt) if isinstance(v, list) else v!r}")
        if prefill and not (a.get("evidence") or a.get("why")):
            errs.append(f"{where} {qid}: 자동 채움에는 근거(evidence: E-* 또는 why)가 필요하다 — 추측으로 채우지 않는다")
    return errs


# ───────────────────────── 폼 만들기
def evidence_for(prefill: dict) -> dict:
    """자동 채움이 가리키는 발견(E-*)만 폼에 싣는다 — 입고가 늘어도 폼이 흔들리지 않게."""
    want = {e for a in prefill.get("answers", {}).values() for e in a.get("evidence", [])}
    out = {}
    intake = wh.load("intake") or {}
    for f in intake.get("files", []):
        for e in f.get("findings", []):
            if e.get("id") in want:
                out[e["id"]] = {"text": e.get("text", ""), "file": f.get("path", "")}
    return out


MOCKUP_DIRS = {"html-mockup": (".html", ".htm"), "screenshot": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")}
# [Nova 보기] 갤러리에 넣는 실제 화면 캡처(있을 때만 — 새 프로젝트에는 없을 수 있다)
SHOTS = {"list": "app-items-list.png", "form": "app-items-new-error.png", "toast": "app-items-undo-toast.png",
         "confirm": "app-confirm-dialog.png", "detail": "app-item-detail.png", "mobile": "kmp-items.png"}
SHOT_DIR = ROOT / "docs" / "screenshots"


def mockup_files() -> list[dict]:
    """입고된 목업 · 화면 캡처 목록 — inbound/html-mockup · inbound/screenshot."""
    out = []
    for cat, exts in MOCKUP_DIRS.items():
        base = wh.WH / "inbound" / cat
        if base.exists():
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.suffix.lower() in exts:
                    out.append({"file": f"{cat}/{p.relative_to(base).as_posix()}", "kind": "목업" if cat == "html-mockup" else "캡처"})
    return out


def sync_mockups() -> int:
    """자동 채움 파일의 목업 목록을 입고 폴더와 맞춘다(요약은 남긴다). 바뀐 수를 돌려준다."""
    pre = json.loads(prefill_path().read_text(encoding="utf-8")) if prefill_path().exists() else {"answers": {}}
    old = {m["file"]: m for m in pre.get("mockups", [])}
    new = [{**m, **({"summary": old[m["file"]]["summary"]} if old.get(m["file"], {}).get("summary") else {})} for m in mockup_files()]
    if new == pre.get("mockups", []):
        return 0
    pre["mockups"] = new
    prefill_path().parent.mkdir(parents=True, exist_ok=True)
    prefill_path().write_text(json.dumps(pre, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return len(new)


def shots() -> dict:
    out = {}
    for k, name in SHOTS.items():
        p = SHOT_DIR / name
        if p.exists() and p.stat().st_size < 200_000:
            out[k] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")
    return out


def render_form() -> str:
    t = tree()
    pre = json.loads(prefill_path().read_text(encoding="utf-8")) if prefill_path().exists() else {"answers": {}}
    data = {"tree": t, "prefill": pre, "evidence": evidence_for(pre), "mockups": pre.get("mockups", []), "shots": shots()}
    blob = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data["build"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]
    tpl = (FORM_DIR / "template.html").read_text(encoding="utf-8")
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return tpl.replace("/*__TOKENS__*/", tokens, 1).replace("/*__DATA__*/null", js, 1)


# ───────────────────────── md 보기
def label(q: dict, a: dict) -> str:
    v = a.get("value")
    if v == UNKNOWN:
        return "건너뜀 · 나중에"
    if q["type"] == "text":
        return str(v)
    if q["type"] == "mockups":
        names = {x["id"]: x["label"] for x in tree().get("mockup_levels", [])}
        return " / ".join(f"{f}: {names.get(x.get('level'), x.get('level'))}" + (f"({x['note']})" if x.get("note") else "")
                          for f, x in v.items() if x.get("level"))
    if q["type"] == "color":
        p = next((x for x in q.get("presets", []) if x["id"] == v.get("preset")), None)
        out = f"{p['label'] if p else '직접 지정'} {v['hex']} (흰 배경 글자 대비 {contrast(v['hex'], '#FFFFFF'):.1f}:1"
        tt = v.get("text_hex")
        return out + (f", 글자용 {tt} {contrast(tt, '#FFFFFF'):.1f}:1)" if tt and tt != v["hex"] else ")")
    if q["type"] == "rows":
        cols = q.get("columns", [])

        def cell(c, r):
            x = r.get(c["id"], "")
            return next((o["label"] for o in c.get("options", []) if o["id"] == x), x) if c["type"] == "one" else x
        return " / ".join(" · ".join(filter(None, (cell(c, r) for c in cols))) for r in v)
    opts = {o["id"]: o for o in q.get("options", [])}
    vals = v if isinstance(v, list) else [v]
    out = []
    for x in vals:
        o = opts.get(x, {"label": x})
        out.append(f"{o['label']}({a['other']})" if o.get("other") and a.get("other") else o["label"])
    return ", ".join(out)


def visible(qid: str, answers: dict, parent: dict) -> bool:
    p = parent.get(qid)
    while p:
        a = answers.get(p[0], {})
        v = a.get("value")
        if not (v == p[1] or (isinstance(v, list) and p[1] in v)):
            return False
        p = parent.get(p[0])
    return True


def walk_visible(t: dict, answers: dict, lv: int, off: list | tuple = ()):
    """보이는 질문을 (섹션, 깊이, 질문) 순서로. 건너뛴 섹션(off)은 뺀다."""
    _, parent, _ = index(t)

    def walk(items, depth, sec):
        for q in items:
            if not visible(q["id"], answers, parent) or (q.get("lv", 1) > lv and empty(answers.get(q["id"]))):
                continue  # 범위 밖 질문이라도 답했으면 보인다(단계를 낮춰도 답은 남는다)
            yield sec, depth, q
            for o in q.get("options", []):
                if o.get("children"):
                    yield from walk(o["children"], depth + 1, sec)
    for s in t["sections"]:
        if s["id"] not in off:
            yield from walk(s["questions"], 0, s)


def empty(a: dict | None) -> bool:
    if not a:
        return True
    v = a.get("value")
    if isinstance(v, list):
        return not v or (isinstance(v[0], dict) and not any(any(r.values()) for r in v))
    if isinstance(v, dict) and "hex" not in v:   # 목업 채택표 — 하나도 고르지 않았으면 빈 답
        return not any(isinstance(x, dict) and x.get("level") for x in v.values())
    return v in ("", None)


def render_md(doc: dict, t: dict, name: str) -> str:
    ans = doc.get("answers", {})
    lv = doc.get("lv", 1)
    off = doc.get("skipped_sections", [])
    status = doc.get("status", "draft")
    lines = ["---", "form: nova-checklist", f"tree_version: {doc.get('tree_version', '')}", f"status: {status}",
             f"revision: {doc.get('revision', 0)}", f"created: {doc.get('created', '')}", f"updated: {doc.get('updated', '')}",
             f"level: {LV_KO.get(lv, lv)}", "---",
             f"<!-- {MARK} — 원천 {name}.json · 손으로 고치지 않는다 -->", f"# 요구 체크리스트 · {name}", ""]
    lines.append("> ✅ **제출됨(완료)** — 요구 분석(/intake)에 반영된다." if status == "complete"
                 else "> ✏️ **작성중(임시저장)** — 제출(완료)하기 전에는 요구 분석에 반영하지 않는다.")
    if lv < 3:
        lines.append(f"> 범위: '{LV_KO.get(lv, lv)}' 질문까지. 더 높은 단계 질문이 비어 있는 것은 빠뜨림이 아니라 범위 밖이다.")
    lines.append("")
    todo, stds, tech, look, cur = [], [], [], [], None
    for s in t["sections"]:
        if s["id"] in off:
            todo.append(f"{s['title']} — 섹션 전체를 건너뜀")
    for sec, depth, q in walk_visible(t, ans, lv, off):
        if sec["id"] != cur:
            cur = sec["id"]
            lines += ["", f"## {sec['title']}", ""]
        a = ans.get(q["id"])
        ind = "  " * depth
        if empty(a):
            lines.append(f"{ind}- {q['q']} → **(비어 있음)**")
            todo.append(f"{sec['title']} — {q['q']}")
            continue
        mark = "" if a.get("state") == "customer" else f" _({STATE_KO.get(a.get('state'), a.get('state'))})_"
        ev = f" · 근거 {', '.join(a['evidence'])}" if a.get("evidence") else ""
        text = label(q, a)
        if a.get("other"):
            text += f" — 기타: {a['other']}" if "(" + a["other"] + ")" not in text else ""
        lines.append(f"{ind}- {q['q']} → **{text}**{mark}{ev}")
        if a.get("state") in ("prefill", "unknown"):
            todo.append(f"{sec['title']} — {q['q']} ({STATE_KO[a['state']]})")
        if q.get("std"):
            stds.append(f"{q['std']}: {text}")
        if str(q.get("feeds", "")).startswith("foundation"):
            tech.append(f"`{q['feeds']}` — {q['q']} → {text}")
        if q["id"] == KIT_QID and a.get("state") != "unknown":
            look.insert(0, kit_line(q, a, t, status))
        elif sec["id"] == "design" and a.get("state") != "unknown":
            look.append(f"{q['q']} → {text}")
    if off:
        lines += ["", "## 건너뛴 섹션", ""] + [f"- {s['title']}" for s in t["sections"] if s["id"] in off]
    lines += ["", "## 채우거나 확인할 것", ""] + ([f"- {x}" for x in todo] or ["- 없음"])
    lines += ["", "## 기술 결정 (/foundation 입력)", ""] + ([f"- {x}" for x in tech] or ["- 답 없음 — /foundation 에서 묻는다"])
    lines += ["", "## 디자인 결정 (디자인 토큰 입력 — design/tokens/brand.tokens.json → python nova.py tokens 로 대비 검사)", ""] \
        + ([f"- {x}" for x in look] or ["- 답 없음 — Nova 기본 디자인"])
    lines += ["", "## 표준 판정 후보 (/foundation 에서 판정)", ""] + ([f"- {x}" for x in stds] or ["- 해당 답 없음"])
    return "\n".join(lines) + "\n"


def part_labels(t: dict) -> dict:
    qs, _, _ = index(t)
    return {o["id"]: o["label"] for o in qs.get("parts.need", {}).get("options", [])}


def kit_line(q: dict, a: dict, t: dict, status: str) -> str:
    """md '디자인 결정' 맨 앞 줄 — 고른 킷 · 그 킷에 없는 부품 · 언제 설정되는지."""
    kid = a.get("value")
    o = next((x for x in q.get("options", []) if x["id"] == kid), None)
    if o is None:
        return f"**킷 결정**: `{kid}` — 킷 목록(catalog.json)에 없는 킷이라 설정하지 않는다(부족 항목)"
    names = part_labels(t)
    gaps = [names.get(g, g) for g in o["kit"]["gaps"]]
    gap = f" · Nova 에 없는 부품: {', '.join(gaps)}(부족 항목으로 묻는다)" if gaps else ""
    when = "체크리스트로 설정됨(`checklist.py import` 때)" if status == "complete" else "제출(완료) 뒤 `checklist.py import` 때 설정된다"
    return f"**킷 결정**: {o['label']} (`{kid}`){gap} — {when} — {KIT_RESET}"


def run_kit_use(kid: str) -> tuple[bool, str]:
    """킷 설정 정본 동작 kits.use(`python nova.py kit use` 와 같다 — 목록 · 대비 검사 → nova.project.json design 기록 → 토큰 생성)를 부른다.
    같은 일을 여기서 다시 짜지 않는다 — 대비 미달 · 모르는 킷은 KitError 로 거절되고 메타 · 생성물은 그대로다."""
    import kits   # 지연 import — 폼 만들기 · 검사만 할 때 토큰 생성기까지 싣지 않는다
    root = PROJECT_JSON.parent
    owner = json.loads(PROJECT_JSON.read_text(encoding="utf-8")).get("owner", "")
    try:
        rec = kits.use(kid, root=root, by=owner or "checklist", source="checklist")
    except kits.KitError as e:
        return False, str(e)
    return True, f"킷 {rec['kit']} 설정({rec['date']} · {rec['by']} · 출처 {rec['source']})"


def apply_kit(kid: str, origin: str) -> tuple[bool, str]:
    """킷을 실제로 설정하고 어느 체크리스트의 어느 답인지를 nova.project.json design.origin 에 남긴다. (성공, 설명)
    design.source 는 kits.py 의 값(checklist)을 그대로 둔다 — 그 칸은 manual|checklist|default 만 받는 계약이다."""
    ok, msg = run_kit_use(kid)
    if not ok:
        return False, msg
    meta = json.loads(PROJECT_JSON.read_text(encoding="utf-8"))
    design = meta.get("design")
    if not isinstance(design, dict) or design.get("kit") != kid:
        return False, f"kit use 뒤에도 {PROJECT_JSON.name} design.kit 이 {kid} 가 아니다"
    if design.get("origin") != origin:
        design["origin"] = origin
        PROJECT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True, msg


LAST_KIT: dict | None = None   # 마지막 import 의 킷 설정 결과 — 명령 출력용


def import_kit(doc_path: Path, rel: str, ans: dict) -> tuple[list[dict], dict | None]:
    """완료본의 design.kit 을 실제로 설정한다. 목록에 없거나 설정이 거절되면 설정하지 않고 부족 항목으로 올린다.
    킷의 갭(Nova 에 없는 부품)은 언제나 부족 항목이다."""
    a = ans.get(KIT_QID)
    if empty(a) or a.get("value") == UNKNOWN or a.get("state") not in ("customer", "confirmed"):
        return [], None   # 답이 없거나 확인 전이면 가만둔다(빈 답 · 확인 전은 일반 부족 항목이 묻는다)
    kid, origin = a["value"], f"{rel}#{KIT_QID}"
    t = tree()
    q = index(t)[0].get(KIT_QID, {})
    o = next((x for x in q.get("options", []) if x["id"] == kid), None)
    ask = "표준 디자인 킷을 무엇으로 할까요?"
    if o is None:
        return [{"area": "화면", "question": ask, "why": f"고른 킷 {kid!r} 이 킷 목록(catalog.json)에 없어 설정하지 않음",
                 "origin": f"{origin}:설정"}], {"kit": kid, "ok": False, "msg": "킷 목록에 없음"}
    ok, msg = apply_kit(kid, f"checklist:{doc_path.name}#{KIT_QID}")
    gaps = [] if ok else [{"area": "화면", "question": ask, "why": f"고른 킷 {kid} 를 설정하지 못함 — {msg}", "origin": f"{origin}:설정"}]
    names = part_labels(t)
    for g in o["kit"]["gaps"]:
        gaps.append({"area": "화면", "question": f"'{o['label']}' 킷에 맞는 '{names.get(g, g)}' 부품이 Nova 에 없다 — 새로 만들까요, 빼고 갈까요?",
                     "why": f"표준 디자인 킷 {kid} 의 부품 갭(🗺)", "origin": f"{origin}:{g}"})
    return gaps, {"kit": kid, "ok": ok, "msg": msg}


def checklist_docs() -> list[Path]:
    return sorted(p for p in ck_dir().glob("checklist_*.json") if FILE_RE.match(p.stem)) if ck_dir().exists() else []


def expected_md() -> dict[Path, str]:
    t = tree()
    out = {}
    for p in checklist_docs():
        out[p.with_suffix(".md")] = render_md(json.loads(p.read_text(encoding="utf-8")), t, p.stem)
    return out


def write_md() -> list[Path]:
    done = []
    for p, text in expected_md().items():
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8", newline="\n")
            done.append(p)
    return done


# ───────────────────────── 입고 분석으로 가져오기
def latest(status: str | None = "complete") -> Path | None:
    best, key = None, None
    for p in checklist_docs():
        d = json.loads(p.read_text(encoding="utf-8"))
        if status and d.get("status") != status:
            continue
        k = (d.get("updated", ""), d.get("revision", 0))
        if key is None or k > key:
            best, key = p, k
    return best


def import_to_intake() -> tuple[str, int, int]:
    """최신 완료 체크리스트 → intake.json: 답은 발견(E-*), 비었거나 모름 · 확인 전인 기본 질문은 부족 항목(G-*). 다시 해도 같은 결과(멱등)."""
    p = latest("complete")
    if p is None:
        return "", 0, 0
    t = tree()
    doc = json.loads(p.read_text(encoding="utf-8"))
    rel = f"checklist/{p.name}"
    wh.scan(write=True)
    intake = wh.load("intake") or {"version": 1, "files": [], "gaps": []}
    entry = next((f for f in intake["files"] if f["path"] == rel), None)
    if entry is None:
        entry = {"path": rel, "category": "checklist", "sha256": wh.sha256(p), "size": p.stat().st_size}
        intake["files"].append(entry)
    nums = [int(e["id"][2:]) for f in intake["files"] if f is not entry for e in f.get("findings", []) if re.fullmatch(r"E-\d+", e.get("id", ""))]
    n = max(nums, default=0)
    findings, gaps = [], []
    ans = doc.get("answers", {})
    off = doc.get("skipped_sections", [])
    for s in t["sections"]:  # 건너뛴 섹션의 기본 질문은 인터뷰로 묻는다
        if s["id"] in off:
            for q in s["questions"]:
                if q.get("lv", 1) == 1:
                    gaps.append({"area": q["area"], "question": q["q"], "why": "체크리스트에서 섹션을 건너뜀(답하기 어려움)", "origin": f"{rel}#{q['id']}"})
    for sec, _depth, q in walk_visible(t, ans, doc.get("lv", 1), off):
        a = ans.get(q["id"])
        filled = not empty(a)
        if filled and a.get("state") in ("customer", "confirmed"):
            n += 1
            kind = "요구" if q["area"] in ("기능", "범위(목표 · 비목표)", "화면", "외부 연동") else "사실"
            text = f"{q['q']} → {label(q, a)}"
            findings.append({"id": f"E-{n:03d}", "area": q["area"], "kind": kind, "text": text, "quote": f"체크리스트 {q['id']}: {label(q, a)}"})
        elif q.get("lv", 1) == 1 or filled:
            why = "체크리스트에서 건너뜀(답하기 어려움)" if filled and a.get("state") == "unknown" else \
                  "자료에서 채웠지만 고객 확인 전" if filled else "체크리스트에서 비어 있음"
            gaps.append({"area": q["area"], "question": q["q"], "why": why, "origin": f"{rel}#{q['id']}"})
    global LAST_KIT
    kit_gaps, LAST_KIT = import_kit(p, rel, ans)
    gaps += kit_gaps
    kit_note = ""
    if LAST_KIT:
        kit_note = (f" 킷 {LAST_KIT['kit']}: 체크리스트로 설정됨 — {KIT_RESET}." if LAST_KIT["ok"]
                    else f" 킷 {LAST_KIT['kit']}: 설정하지 않음({LAST_KIT['msg']}) — 부족 항목.")
        for e in findings:
            if e["quote"].startswith(f"체크리스트 {KIT_QID}:"):
                e["text"] += " — 체크리스트로 설정됨" if LAST_KIT["ok"] else " — 설정하지 않음(부족 항목)"
    for f in intake["files"]:  # 이전 판 체크리스트는 최신 완료본이 대신한다(같은 답이 두 번 세지지 않게)
        if f is not entry and f["category"] == "checklist" and FILE_RE.match(Path(f["path"]).stem) and f.get("status") != "삭제됨":
            f.update(status="분석됨", analyzed=f.get("analyzed") or dt.date.today().isoformat(), findings=[],
                     summary=f"이전 판 — 최신 완료본 {rel} 이 대신한다")
    entry.update(sha256=wh.sha256(p), size=p.stat().st_size, status="분석됨", analyzed=dt.date.today().isoformat(),
                 summary=f"요구 체크리스트(판 {doc.get('revision', 0)}, 완료) — 답 {len(findings)}개 · 채울 것 {len(gaps)}개. "
                         f"부족 항목은 /req-interview 로 묻는다.{kit_note}", findings=findings)
    # 체크리스트에서 나온 부족 항목은 다시 가져올 때 바꾼다(답한 것 · 인터뷰 중인 것은 남긴다)
    keep = [g for g in intake.get("gaps", []) if not str(g.get("origin", "")).startswith("checklist/") or g.get("status") in ("답함", "인터뷰 중")]
    have = {g.get("origin") for g in keep}
    gn = max((int(g["id"][2:]) for g in intake.get("gaps", []) if re.fullmatch(r"G-\d+", g.get("id", ""))), default=0)
    for g in gaps:
        if g["origin"] in have:
            continue
        gn += 1
        keep.append({"id": f"G-{gn:03d}", **g, "status": "열림", "answer": "", "interview": ""})
    intake["gaps"] = keep
    wh.dump("intake", intake)
    return rel, len(findings), len(gaps)


# ───────────────────────── 검사 · 저장 서버
def check() -> list[str]:
    t = tree()
    errs = check_tree(t)
    if errs:
        return errs
    if prefill_path().exists():
        pre = json.loads(prefill_path().read_text(encoding="utf-8"))
        errs += check_answers(pre.get("answers", {}), t, "checklist_prefill.json", prefill=True)
        known = {e["id"] for f in (wh.load("intake") or {}).get("files", []) for e in f.get("findings", [])}
        for qid, a in pre.get("answers", {}).items():
            for e in a.get("evidence", []):
                if e not in known:
                    errs.append(f"checklist_prefill.json {qid}: intake.json 에 없는 근거 {e}")
    for p in checklist_docs():
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("form") != "nova-checklist":
            errs.append(f"{p.name}: form 이 nova-checklist 가 아니다")
        if d.get("status") not in ("draft", "complete"):
            errs.append(f"{p.name}: status 는 draft|complete")
        errs += check_answers(d.get("answers", {}), t, p.name)
    if not form_path().exists() or form_path().read_text(encoding="utf-8") != render_form():
        errs.append("checklist.html 이 원천(트리 · 자동 채움 · 토큰)과 다르다 → uv run python scripts/checklist.py build")
    for p, text in expected_md().items():
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            errs.append(f"{p.name} 가 {p.stem}.json 과 다르다 → uv run python scripts/checklist.py md")
    if prefill_path().exists():   # 자동 채움의 목업 목록 — 입고 폴더에 실제로 있어야 한다
        for m in json.loads(prefill_path().read_text(encoding="utf-8")).get("mockups", []):
            if not (wh.WH / "inbound" / m.get("file", "")).is_file():
                errs.append(f"checklist_prefill.json mockups: 입고에 없는 파일 {m.get('file')} → uv run python scripts/checklist.py mockups")
    for p in ck_dir().glob("checklist_*.md"):
        if not p.with_suffix(".json").exists() and MARK in p.read_text(encoding="utf-8")[:600]:
            errs.append(f"{p.name}: 원천 json 이 없는 생성물")
    return errs


def next_name(day: str) -> str:
    n = 1
    while (ck_dir() / f"checklist_{day}_{n:02d}.json").exists():
        n += 1
    return f"checklist_{day}_{n:02d}"


def save_doc(doc: dict) -> str:
    """서버 저장 — 같은 세션(file 이 이미 있는 이름)이면 덮고, 아니면 오늘 날짜의 다음 번호."""
    if not isinstance(doc, dict) or not isinstance(doc.get("answers", {}), dict):
        raise ValueError("체크리스트 형식이 아니다 — JSON 객체와 answers 객체가 필요하다")
    t = tree()
    errs = check_answers(doc.get("answers", {}), t, "저장 요청")
    if doc.get("form") != "nova-checklist" or errs:
        raise ValueError("; ".join(errs) or "체크리스트 형식이 아니다")
    name = doc.get("file") or ""
    if not (FILE_RE.match(name) and (ck_dir() / f"{name}.json").exists()):
        name = next_name(dt.date.today().strftime("%Y%m%d"))
    doc["file"] = name
    p = ck_dir() / f"{name}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    p.with_suffix(".md").write_text(render_md(doc, t, name), encoding="utf-8", newline="\n")
    return name


MAX_SAVE = 2_000_000   # 저장 요청 본문 상한(바이트)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/checklist.html"):
            self._send(200, render_form().encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/mockups":
            self._json(200, mockup_files())
        elif self.path.startswith("/files/"):   # 목업 · 캡처 열어 보기 — 두 폴더만, 읽기 전용
            rel = urllib.parse.unquote(self.path[len("/files/"):].split("?")[0])
            cat = rel.split("/")[0]
            base = (wh.WH / "inbound" / cat).resolve() if cat in MOCKUP_DIRS else None
            p = (wh.WH / "inbound" / rel).resolve()
            if base is None or base not in p.parents or not p.is_file() or p.suffix.lower() not in MOCKUP_DIRS[cat]:
                return self._json(404, {"error": {"code": "NOT_FOUND", "message": "없는 파일"}})
            # 입고 목업은 남이 만든 HTML 일 수 있다 — 샌드박스로 열어 이 서버의 [저장] API 를 부르지 못하게 한다
            self._send(200, p.read_bytes(), mimetypes.guess_type(p.name)[0] or "application/octet-stream",
                       {"Content-Security-Policy": "sandbox"})
        elif self.path == "/api/latest":
            p = latest(None)
            self._json(200, json.loads(p.read_text(encoding="utf-8")) if p else {})
        else:
            self._json(404, {"error": {"code": "NOT_FOUND", "message": "없는 경로"}})

    def _same_origin(self) -> bool:
        """Origin 이 있으면 이 서버(127.0.0.1 · localhost 의 같은 포트)만 — 다른 사이트의 fetch 저장(CSRF)을 막는다."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True   # 브라우저 밖 도구(curl 등) — 로컬 접속만 받으므로 허용
        port = self.server.server_address[1]
        return origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

    def do_POST(self):  # noqa: N802
        if self.path != "/api/save":
            return self._json(404, {"error": {"code": "NOT_FOUND", "message": "없는 경로"}})
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if n < 0:
            self.close_connection = True
            return self._json(400, {"error": {"code": "INVALID", "message": "Content-Length 가 올바르지 않다"}})
        if n > MAX_SAVE:
            self.close_connection = True   # 본문을 읽지 않으므로 연결을 끊는다
            return self._json(413, {"error": {"code": "TOO_LARGE", "message": f"저장 요청이 너무 크다(최대 {MAX_SAVE:,}바이트)"}})
        raw = self.rfile.read(n)   # 거절하더라도 본문은 먼저 비운다 — 읽지 않은 채 닫으면 응답이 끊길 수 있다
        if not self._same_origin():
            return self._json(403, {"error": {"code": "FORBIDDEN_ORIGIN", "message": "다른 사이트에서 온 저장 요청은 받지 않는다"}})
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self._json(415, {"error": {"code": "UNSUPPORTED_MEDIA_TYPE", "message": "저장 요청은 Content-Type: application/json 이어야 한다"}})
        try:
            name = save_doc(json.loads(raw.decode("utf-8")))
            print(f"✓ 저장: docs/warehouse/inbound/checklist/{name}.json · .md")
            self._json(200, {"file": name})
        except (ValueError, json.JSONDecodeError) as e:
            self._json(400, {"error": {"code": "INVALID", "message": str(e)}})

    def log_message(self, *_):
        pass


def serve(port: int, open_browser: bool = True) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)  # 이 PC 에서만 접속
    url = f"http://127.0.0.1:{port}/"
    print(f"체크리스트: {url}  (끝내려면 Ctrl+C) — [저장]이 docs/warehouse/inbound/checklist/ 에 바로 기록된다")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sp = sub.add_parser("serve")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--no-open", action="store_true")
    sub.add_parser("md")
    sub.add_parser("import")
    sub.add_parser("check")
    sub.add_parser("mockups")
    a = ap.parse_args(argv)
    if a.cmd == "mockups":
        n = sync_mockups()
        print(f"✓ 목업 목록을 맞췄다 — {n}개 (docs/product/checklist_prefill.json mockups) → checklist.py build" if n else "✓ 목업 목록 변화 없음")
        return 0
    if a.cmd == "build":
        errs = check_tree(tree())
        if prefill_path().exists():
            errs += check_answers(json.loads(prefill_path().read_text(encoding="utf-8")).get("answers", {}), tree(), "checklist_prefill.json", prefill=True)
        if errs:
            for e in errs:
                print("✗", e)
            return 1
        form_path().parent.mkdir(parents=True, exist_ok=True)
        form_path().write_text(render_form(), encoding="utf-8", newline="\n")
        n = len(json.loads(prefill_path().read_text(encoding="utf-8")).get("answers", {})) if prefill_path().exists() else 0
        print(f"✓ {form_path().relative_to(ROOT).as_posix()} (자동 채움 {n}개)")
        return 0
    if a.cmd == "serve":
        serve(a.port, not a.no_open)
        return 0
    if a.cmd == "md":
        for p in write_md():
            print("✓", p.relative_to(ROOT).as_posix())
        return 0
    if a.cmd == "import":
        rel, nf, ng = import_to_intake()
        drafts = [p.name for p in checklist_docs() if json.loads(p.read_text(encoding="utf-8")).get("status") != "complete"]
        if drafts:
            print(f"작성중 {len(drafts)}건은 반영하지 않는다: {', '.join(drafts)}")
        print(f"✓ {rel} → 발견 {nf}개 · 부족 항목 {ng}개" if rel else "완료로 표시된 체크리스트가 없다")
        if rel and LAST_KIT:
            print(f"✓ 킷 {LAST_KIT['kit']} 설정 — {KIT_RESET}" if LAST_KIT["ok"]
                  else f"✗ 킷 {LAST_KIT['kit']} 설정하지 않음 — {LAST_KIT['msg']} (부족 항목으로 올림)")
        return 0
    errs = check()
    for e in errs:
        print("✗", e)
    if not errs:
        print("✓ 체크리스트 트리 · 자동 채움 · 폼 · md 정상")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
