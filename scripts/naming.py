#!/usr/bin/env python3
"""명명 규약 검사 · 개념 원장 (REQ-261104-14). 이름은 센스가 아니라 공식으로 — 같은 개념은 누가 지어도 같은 이름.

  python nova.py naming check                  # lint — 대장 · 서비스 · 토픽 · 권한 · 팩 · 오류 코드 · @nova/ui 를 형식에 대조
  python nova.py naming lookup <개념…>          # 이름 짓기 전에 조회 — 정확 · 별칭 · 유사 · 은퇴 · 없음(항상 종료 0)
  python nova.py naming --write                # docs/conventions/naming.md 의 형식 표 구간 생성(gen)
  python nova.py naming entity add <키> --title <한국어> --service <서비스|*> --table <표> --layer platform|core|pack [--pack <팩>]
  python nova.py naming alias add <키> <별칭> [--forbidden]
  python nova.py naming retire <키> --why <사유>
  python nova.py naming layer set <키> <층> --why <사유> [--pack <팩>]

원천:
  registry/naming.json      선언 정본(형식 · 금지 축약 · 불규칙 과거형 · 예외 · baseline · 프로젝트 추가 형식)
  registry/entities.jsonl   개념 원장 이력(추가 전용 — 한 줄 한 사건) → registry/entities.json(상태, 재생 결과 — 손으로 고치지 않는다)
  docs/conventions/naming.md  사람이 읽는 규약 — 형식 표 구간만 생성물
검사 대상: registry/ledgers.json(DB 사전 · 권한) · services.json · kafka-topics.txt · rbac.json · packs/*/pack.json · 팩 확장 표
           · 소스의 ApiError( 오류 코드 · 생성물 원장의 API 경로 · UI 컴포넌트 · @nova/ui 내보내기 이름
개념 원장 검사: 형식 · 층 · 금지 별칭이 대장 이름에 쓰였는지 · 좀비(원장에만 있는 표) · 미등재(실물에만 있는 업무 표 — 실패)
쓰기(entity · alias · retire · layer)는 단일 기록자 — 본 작업 트리(main)에서만(ADR-008).
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, require_main, same, write  # noqa: E402

RULES = "registry/naming.json"
ENTITIES = "registry/entities.json"
ENTITY_LOG = "registry/entities.jsonl"
LEDGERS = "registry/ledgers.json"
ARTIFACTS = "registry/registry.json"
SERVICES = "packages/common-py/nova_common/services.json"
TOPICS = "infra/k3s/base/kafka-topics.txt"
RBAC = "services/gateway/gateway/rbac.json"
UI_INDEX = "web/packages/ui/src/index.ts"
DOC = "docs/conventions/naming.md"
BEGIN = "<!-- naming:begin — 생성물: registry/naming.json 에서 `python nova.py naming --write` 가 만든다. 손으로 고치지 않는다 -->"
END = "<!-- naming:end -->"

LAYERS = ("platform", "core", "pack")
STATUSES = ("active", "deprecated", "retired")
# 대상 종류 → 그 종류에 적용하는 형식(정규식 하나로 끝나는 것). 타입 · 도메인 · 과거형처럼 문맥이 필요한 규칙은 collect 가 따로 본다
KIND_FORMATS = {
    "table": ("table", "table_singular"), "column": ("column",), "topic": ("topic",), "permission": ("permission",),
    "error_code": ("error_code",), "api_segment": ("api_segment",), "component": ("component",),
    "web_export": ("web_export",), "service": ("service",), "scope": ("scope",), "pack": ("pack",),
}
KIND_LABEL = {"table": "표", "column": "칸", "topic": "토픽", "permission": "권한", "error_code": "오류 코드",
              "api_segment": "API 경로", "component": "컴포넌트", "web_export": "@nova/ui", "service": "서비스",
              "scope": "범위", "pack": "팩"}
# 잡음(기준 테이블 표지) — 떼어도 같은 개념. _log · _history · _detail 같은 파생 표지는 다른 개념이라 남긴다
NOISE = {"tbl", "table", "테이블", "master", "mst", "마스터", "기준정보"}
AFFIX_NOISE = ("마스터", "테이블", "기준정보")
ERROR_CODE = re.compile(r"ApiError\(\s*\d+\s*,\s*[\"']([^\"']+)[\"']")
TABLENAME = re.compile(r"__tablename__\s*=\s*[\"']([^\"']+)[\"']")
EXPORT_BLOCK = re.compile(r"export\s*\{([^}]*)\}", re.S)


class NamingError(Exception):
    pass


@dataclass(frozen=True)
class Violation:
    rule: str
    target: str
    message: str


# ------------------------------------------------------------------ 선언 읽기
def load_rules(root: Path = ROOT) -> dict:
    p = Path(root) / RULES
    if not p.exists():
        raise NamingError(f"{RULES} 가 없다 — 명명 규약 선언 정본")
    return json.loads(p.read_text(encoding="utf-8"))


def formats(root: Path = ROOT) -> dict[str, dict]:
    """플랫폼 형식 표(naming.json formats)."""
    return load_rules(root).get("formats") or {}


def pattern(rule: str, root: Path = ROOT, **subs: str) -> re.Pattern:
    """다른 스크립트(new_service · packs · 토픽 테스트)가 쓰는 정규식 — 정규식을 한 곳(naming.json)에만 둔다."""
    f = formats(root).get(rule)
    if not f or "regex" not in f:
        raise NamingError(f"naming.json formats.{rule}.regex 가 없다")
    rx = f["regex"]
    for k, v in subs.items():
        rx = rx.replace("{" + k + "}", re.escape(v))
    return re.compile(rx)


def _read_json(root: Path, rel: str, default=None):
    p = Path(root) / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# ------------------------------------------------------------------ 정규화 · 조회
def normalize(raw: str) -> str:
    """이름 정규화 — camel · 구분자 · 복수형 · 잡음(master · tbl · 마스터)을 흡수해 비교 가능한 토큰 열로.
    예: DeptMaster · dept_master · dept-masters · '부서 마스터' → 'dept' / '부서'. _log · _history 는 남긴다(다른 개념)."""
    s = str(raw or "").strip()
    if not s:
        return ""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s).lower()
    s = re.sub(r"[_\-./\\\s]+", " ", s).strip()

    def one(t: str) -> str:
        if re.search(r"\w{3}ies$", t):
            t = t[:-3] + "y"
        elif re.search(r"\w{3}s$", t) and not t.endswith(("ss", "us", "is")):
            t = t[:-1]
        for n in AFFIX_NOISE:
            if len(t) - len(n) >= 2:
                if t.endswith(n):
                    return t[: -len(n)]
                if t.startswith(n):
                    return t[len(n):]
        return t

    toks = [one(t) for t in s.split(" ") if t]
    kept = [t for t in toks if t and t not in NOISE]
    return " ".join(kept or toks)


def similarity(a: str, b: str) -> float:
    """정규화된 두 이름의 닮은 정도(0~1) — 토큰 겹침 · 포함 · 글자 유사도 중 큰 값."""
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / len(ta | tb)
    contain = 0.6 if min(len(a), len(b)) >= 3 and (a in b or b in a) else 0.0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return max(jac, contain, ratio if ratio >= 0.8 else 0.0)


def lookup(root: Path, query: str) -> dict:
    """개념 하나를 원장에 대조 — verdict: 정확 · 별칭 · 유사 · 은퇴 · 없음."""
    q = normalize(query)
    state = entities(root)
    exact, alias, similar = [], [], []
    for key, e in state.items():
        names = {normalize(key)} | ({normalize(e["table"])} if e.get("table") else set())
        aliases = {normalize(a) for a in e.get("lookup_aliases", []) + e.get("forbidden_aliases", [])}
        if q in names:
            exact.append(e)
        elif q in aliases:
            alias.append(e)
        else:
            score = max((similarity(q, n) for n in names | aliases), default=0.0)
            if score >= 0.5:
                similar.append({**e, "score": round(score, 2)})
    live = lambda xs: [e for e in xs if e["status"] != "retired"]  # noqa: E731
    if live(exact):
        verdict, matches = "정확", live(exact)
    elif live(alias):
        verdict, matches = "별칭", live(alias)
    elif exact or alias:
        verdict, matches = "은퇴", exact + alias
    elif similar:
        verdict, matches = "유사", sorted(similar, key=lambda e: -e["score"])
    else:
        verdict, matches = "없음", []
    return {"query": query, "normalized": q, "verdict": verdict, "matches": matches}


def advice(res: dict) -> list[str]:
    """판정마다 다음 행동 — 처방이 다르다."""
    v, ms = res["verdict"], res["matches"]
    where = lambda e: f"`{e['key']}`(표 {e.get('service') or '-'}.{e.get('table') or '-'} · {e['layer']}{' · ' + e['pack'] if e.get('pack') else ''})"  # noqa: E731
    out = [f"■ '{res['query']}' (정규화 '{res['normalized']}') → {v}"]
    if v == "정확":
        out += [f"  · {where(e)} {e['title_ko']}" for e in ms]
        out.append("  다음: 만들지 않는다 — 기존 개체를 쓴다. 다른 서비스의 개체면 `<개체>_id` 칸(ref_column, FK 없음)으로 가리키고 API · 이벤트로만 읽는다")
    elif v == "별칭":
        out += [f"  · {where(e)} {e['title_ko']}" + (" — 금지 별칭" if normalize(res['query']) in {normalize(a) for a in e.get('forbidden_aliases', [])} else "") for e in ms]
        out.append("  다음: 만들지 않는다 — 정본 이름을 쓴다(같은 개념에 두 이름이 생기는 사고를 막는다)")
    elif v == "은퇴":
        out += [f"  · {where(e)} {e['title_ko']} — {e.get('note') or '사유 없음'}" for e in ms]
        out.append("  다음: 복원인지 신설인지 사람이 판정한다(은퇴 사유를 재료로). 신설이면 왜 같은 이름을 다시 쓰지 않는지 근거를 계획 §0 에")
    elif v == "유사":
        out += [f"  · {where(e)} {e['title_ko']} · 유사도 {int(e['score'] * 100)}%" + (" · 은퇴" if e["status"] == "retired" else "") for e in ms[:5]]
        out.append("  다음: 같은 개념이면 기존 이름을 쓴다. 다른 개념이면 왜 다른지 근거를 계획 §0 · §7 에 적고 진행")
    else:
        out.append("  다음: 새 개념이다 — 사람 승인 후 `python nova.py naming entity add <키> --title <한국어> --service <서비스> --table <표> --layer core|platform|pack`")
    return out


# ------------------------------------------------------------------ 개념 원장(이력 JSONL → 상태 JSON)
def load_events(root: Path = ROOT) -> list[dict]:
    p = Path(root) / ENTITY_LOG
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def apply(state: dict[str, dict], e: dict) -> None:
    """이벤트 하나를 상태에 적용(재생 · 쓰기 공용) — registry.py 와 같은 형식(seq · at · by · action · 대상 · note)."""
    a, key = e["action"], e["key"]
    if a == "create":
        if key in state:
            raise NamingError(f"이미 있는 개념 재생성: {key}")
        d = e["data"]
        state[key] = {"key": key, "title_ko": d["title_ko"], "service": d.get("service"), "table": d.get("table"),
                      "layer": d["layer"], "pack": d.get("pack"), "lookup_aliases": list(d.get("lookup_aliases", [])),
                      "forbidden_aliases": list(d.get("forbidden_aliases", [])), "status": "active",
                      "since": e["at"][:10], "note": e.get("note", "")}
        return
    if key not in state:
        raise NamingError(f"없는 개념에 {a}: {key}")
    r = state[key]
    if a == "alias":
        field = "forbidden_aliases" if e.get("forbidden") else "lookup_aliases"
        if e["alias"] not in r[field]:
            r[field].append(e["alias"])
    elif a == "retire":
        r["status"] = "retired"
        r["note"] = (r["note"] + " · " if r["note"] else "") + f"은퇴 {e['at'][:10]}: {e.get('note', '')}"
    elif a == "layer":
        r["layer"], r["pack"] = e["layer"], e.get("pack")
    else:
        raise NamingError(f"알 수 없는 action: {a}")


def replay(events: list[dict]) -> dict[str, dict]:
    state: dict[str, dict] = {}
    for i, e in enumerate(events, 1):
        if e.get("seq") != i:
            raise NamingError(f"seq 불연속: {i} 자리에 {e.get('seq')}")
        apply(state, e)
    return state


def snapshot_text(state: dict) -> str:
    body = {"$comment": "개념 원장 현재 상태 — 생성물: registry/entities.jsonl(이력)을 재생해 scripts/naming.py 가 쓴다. 손으로 고치지 않는다(python nova.py naming entity|alias|retire|layer).",
            "entities": dict(sorted(state.items()))}
    return json.dumps(body, ensure_ascii=False, indent=1) + "\n"


def entities(root: Path = ROOT) -> dict[str, dict]:
    return replay(load_events(root))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _by() -> str:
    return os.environ.get("NOVA_BY") or os.environ.get("USER") or os.environ.get("USERNAME") or "dev"


def _commit(root: Path, new: list[dict]) -> dict:
    """이벤트를 붙이고 상태를 다시 쓴다 — 적용이 실패하면 아무것도 쓰지 않는다."""
    events = load_events(root)
    state = replay(events)
    for e in new:
        apply(state, e)
    p = Path(root) / ENTITY_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        for e in new:
            f.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
    write(Path(root) / ENTITIES, snapshot_text(state))
    return state


def _event(root: Path, action: str, key: str, *, by: str | None, at: str | None, note: str = "", **extra) -> dict:
    e = {"seq": len(load_events(root)) + 1, "at": at or _now(), "by": by or _by(), "action": action, "key": key}
    e.update(extra)
    if note:
        e["note"] = note
    return e


def _services(root: Path) -> dict[str, dict]:
    return {s["name"]: s for s in (_read_json(root, SERVICES, {}) or {}).get("services", [])}


def _validate_entity(root: Path, key: str, d: dict) -> list[str]:
    errs = []
    fm = formats(root)
    if not pattern("entity_key", root).match(key):
        errs.append(f"키 형식: {key} — {fm['entity_key']['regex']}")
    if not str(d.get("title_ko") or "").strip():
        errs.append(f"{key}: title_ko(한국어 이름)가 비었다")
    if d.get("layer") not in LAYERS:
        errs.append(f"{key}: layer '{d.get('layer')}' — {' · '.join(LAYERS)} 중 하나")
    if (d.get("layer") == "pack") != bool(d.get("pack")):
        errs.append(f"{key}: layer=pack 이면 pack 을 적고, 아니면 비운다")
    if d.get("pack") and not (Path(root) / "packs" / d["pack"] / "pack.json").exists():
        errs.append(f"{key}: 없는 팩 {d['pack']}")
    svc = d.get("service")
    if svc == "*":
        if d.get("layer") != "platform":
            errs.append(f"{key}: service '*'(모든 DB 서비스)는 platform 층만")
    elif svc and svc not in _services(root):
        errs.append(f"{key}: 없는 서비스 {svc}")
    if d.get("table") and not pattern("table", root).match(d["table"]):
        errs.append(f"{key}: 표 이름 형식 {d['table']}")
    if d.get("table") and not svc:
        errs.append(f"{key}: 표가 있으면 소유 서비스(service)도 적는다")
    return errs


def add_entity(root: Path, key: str, title: str, service: str | None, table: str | None, layer: str, pack: str | None = None, *,
               lookup_aliases: list[str] | None = None, forbidden_aliases: list[str] | None = None,
               by: str | None = None, note: str = "", at: str | None = None) -> dict:
    state = entities(root)
    if key in state:
        st = state[key]["status"]
        raise NamingError(f"이미 있는 개념: {key} ({st})" + (" — 은퇴한 키다. 복원인지 신설인지 사람이 판정한다" if st == "retired" else ""))
    data = {"title_ko": title, "service": service, "table": table, "layer": layer, "pack": pack,
            "lookup_aliases": lookup_aliases or [], "forbidden_aliases": forbidden_aliases or []}
    errs = _validate_entity(root, key, data)
    if table:
        dup = [k for k, e in state.items() if e["status"] != "retired" and e.get("service") == service and e.get("table") == table]
        if dup:
            errs.append(f"{service}.{table} 는 이미 {dup[0]} 로 등재됐다")
    if errs:
        raise NamingError(" · ".join(errs))
    return _commit(root, [_event(root, "create", key, by=by, at=at, note=note, data=data)])[key]


def add_alias(root: Path, key: str, alias: str, forbidden: bool = False, *, by: str | None = None, note: str = "") -> dict:
    state = entities(root)
    if key not in state:
        raise NamingError(f"없는 개념: {key} — 먼저 `naming lookup {key}`")
    n = normalize(alias)
    for k, e in state.items():
        if k != key and e["status"] != "retired" and n in {normalize(k), normalize(e.get("table") or "")}:
            raise NamingError(f"'{alias}' 는 다른 개념 {k} 의 정본 이름이다")
    return _commit(root, [_event(root, "alias", key, by=by, at=None, note=note, alias=alias, forbidden=bool(forbidden))])[key]


def retire(root: Path, key: str, why: str, *, by: str | None = None) -> dict:
    state = entities(root)
    if key not in state:
        raise NamingError(f"없는 개념: {key}")
    if state[key]["status"] == "retired":
        raise NamingError(f"이미 은퇴: {key}")
    if not why.strip():
        raise NamingError("은퇴 사유(--why)가 필요하다 — 다음 사람이 복원 · 신설을 판정할 재료")
    return _commit(root, [_event(root, "retire", key, by=by, at=None, note=why)])[key]


def set_layer(root: Path, key: str, layer: str, why: str, pack: str | None = None, *, by: str | None = None) -> dict:
    state = entities(root)
    if key not in state:
        raise NamingError(f"없는 개념: {key}")
    if not why.strip():
        raise NamingError("층 변경 사유(--why)가 필요하다 — 코어 ↔ 팩 이동은 STD-DOMAIN-PACK-001 승격 절차의 기록")
    errs = _validate_entity(root, key, {**state[key], "layer": layer, "pack": pack})
    if errs:
        raise NamingError(" · ".join(errs))
    return _commit(root, [_event(root, "layer", key, by=by, at=None, note=why, layer=layer, pack=pack)])[key]


def reset_for_project(root: Path, by: str = "new_project", at: str | None = None) -> dict:
    """새 프로젝트용 — 이력을 비우고, 플랫폼 개념과 아직 있는 서비스(샘플)의 개념만 다시 등재한다.
    코어 개념의 금지 별칭은 비운다(새 프로젝트의 도메인어가 플랫폼의 금지어에 걸리지 않게)."""
    old = entities(root)
    svcs = _services(root)
    keep = [e for e in old.values() if e["status"] != "retired" and (e["layer"] == "platform" or e.get("service") in svcs)]
    at = at or _now()
    events = []
    for i, e in enumerate(sorted(keep, key=lambda e: e["key"]), 1):
        data = {k: e[k] for k in ("title_ko", "service", "table", "layer", "pack", "lookup_aliases")}
        data["forbidden_aliases"] = e["forbidden_aliases"] if e["layer"] == "platform" else []
        events.append({"seq": i, "at": at, "by": by, "action": "create", "key": e["key"], "data": data,
                       "note": "Nova 에서 생성 — 플랫폼 · 샘플 개념만 물려받음"})
    state = replay(events)
    write(Path(root) / ENTITY_LOG, "".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in events))
    write(Path(root) / ENTITIES, snapshot_text(state))
    return state


# ------------------------------------------------------------------ 검사
def tokens(name: str) -> list[str]:
    """식별자 마디 — camel 경계 · 구분자로 자른 소문자 토큰(금지 축약 대조용)."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    return [t for t in re.split(r"[^A-Za-z0-9]+", s.lower()) if t]


def gather(root: Path) -> tuple[dict[str, list[tuple[str, str]]], list[dict], list[str]]:
    """검사 대상 이름 모으기 — (종류 → [(대상 키, 이름)], DB 칸 행, 대상 누락 오류)."""
    root = Path(root)
    names: dict[str, list[tuple[str, str]]] = {k: [] for k in KIND_FORMATS}
    errs = []
    led = _read_json(root, LEDGERS)
    if led is None:
        errs.append(f"{LEDGERS} 가 없다 — 먼저 `uv run python scripts/ledgers.py`")
        led = {"db": [], "permissions": []}
    cols: dict[tuple, dict] = {}
    for r in led.get("db", []):
        svc = "*" if r.get("common") else r["service"]
        cols.setdefault((svc, r["table"], r["column"]), {**r, "owner": svc})
    rows = list(cols.values())
    for svc, table in sorted({(r["owner"], r["table"]) for r in rows}):
        names["table"].append((f"{svc}:{table}", table))
    for r in rows:
        names["column"].append((f"{r['owner']}:{r['table']}.{r['column']}", r["column"]))
    svcs = _services(root)
    for s in svcs.values():
        names["service"].append((s["name"], s["name"]))
        names["scope"].append((s["name"], s.get("scope", "")))
    tp = root / TOPICS
    for ln in tp.read_text(encoding="utf-8").splitlines() if tp.exists() else []:
        if ln.strip() and not ln.startswith("#"):
            names["topic"].append((ln.split()[0], ln.split()[0]))
    perms = {p["key"] for p in led.get("permissions", [])}
    rbac = _read_json(root, RBAC, {}) or {}
    for r in rbac.get("roles", {}).values():
        perms.update(r["perms"] if isinstance(r, dict) else r)
    names["permission"] = [(p, p) for p in sorted(perms)]
    packs = root / "packs"
    for d in sorted(packs.iterdir()) if packs.exists() else []:
        if d.is_dir() and not d.name.startswith(("_", ".")) and d.name != "__pycache__":
            names["pack"].append((d.name, d.name))
    codes = set()
    for base in ("services", "packages", "packs"):
        for p in sorted((root / base).rglob("*.py")) if (root / base).exists() else []:
            if {".venv", "tests", "__pycache__", "node_modules"} & set(p.parts):
                continue
            codes.update(ERROR_CODE.findall(p.read_text(encoding="utf-8")))
    names["error_code"] = [(c, c) for c in sorted(codes)]
    reg = _read_json(root, ARTIFACTS, {}) or {}
    segs, comps = set(), set()
    for r in reg.values():
        if not isinstance(r, dict) or r.get("status") == "deleted":
            continue
        if r.get("kind") == "API" and " " in r.get("name", ""):
            path = r["name"].split(" ", 1)[1]
            segs.update((path, s) for s in path.split("/") if s)
        elif r.get("kind") == "CMP":
            comps.add(r["name"])
    names["api_segment"] = sorted(segs)
    names["component"] = [(c, c) for c in sorted(comps)]
    ui = root / UI_INDEX
    exports = set()
    for m in EXPORT_BLOCK.finditer(ui.read_text(encoding="utf-8") if ui.exists() else ""):
        for part in m.group(1).split(","):
            part = re.sub(r"^\s*type\s+", "", part).strip()
            if part:
                exports.add(part.split(" as ")[-1].strip())
    names["web_export"] = [(x, x) for x in sorted(exports)]
    return names, rows, errs


def _is_past(word: str, irregular: set[str]) -> bool:
    return word.endswith("ed") or word in irregular


def collect(root: Path = ROOT) -> tuple[list[Violation], list[str]]:
    """(형식 위반 — baseline · exceptions 로 거를 수 있다, 원장 · 판정 불가 오류 — 거를 수 없다)."""
    root = Path(root)
    errs: list[str] = []
    rules = load_rules(root)
    fm = rules.get("formats") or {}
    if not fm:
        return [], ["naming.json formats 가 비었다 — 판정 불가(형식 없이는 아무것도 막지 못한다)"]
    for rid, f in fm.items():
        if not (f.get("regex") or f.get("deny")):
            errs.append(f"naming.json formats.{rid}: regex · deny 가 모두 없다 — 판정 불가")
    for rid in {r for rs in KIND_FORMATS.values() for r in rs} | {"column_datetime", "column_bool", "pk", "column_ref", "pack_ext_table", "entity_key"}:
        if rid not in fm:
            errs.append(f"naming.json formats.{rid} 가 없다 — 판정 불가")
    if errs:
        return [], errs
    project = rules.get("project") or {}
    forbidden = {**rules.get("forbidden_abbr", {}), **project.get("forbidden_abbr", {})}
    irregular = set(rules.get("past_tense_irregular", []))
    names, rows, gerrs = gather(root)
    errs += gerrs
    out: list[Violation] = []

    def check_fmt(rid: str, f: dict, target: str, name: str, label: str) -> None:
        if "regex" in f and not re.search(f["regex"], name):
            out.append(Violation(rid, target, f"{label} '{name}' — {f.get('label', rid)} 형식 {f['regex']} (예: {f.get('example', '-')})"))
        if "deny" in f and re.search(f["deny"], name):
            out.append(Violation(rid, target, f"{label} '{name}' — {f.get('label', rid)}: {f.get('example', f['deny'])}"))

    for kind, rids in KIND_FORMATS.items():
        for target, name in names[kind]:
            for rid in rids:
                check_fmt(rid, fm[rid], target, name, KIND_LABEL[kind])
            for t in tokens(name):
                if t in forbidden:
                    out.append(Violation("forbidden_abbr", f"{kind}:{target}", f"{KIND_LABEL[kind]} '{name}' — 금지 축약 '{t}' → '{forbidden[t]}'"))
    for rid, f in (project.get("formats") or {}).items():
        kind = f.get("applies_to")
        if kind not in names:
            errs.append(f"naming.json project.formats.{rid}: applies_to '{kind}' — {' · '.join(names)} 중 하나")
            continue
        for target, name in names[kind]:
            check_fmt(f"project.{rid}", f, target, name, KIND_LABEL[kind])
    # DB — 타입 표지(시각 _at · 참거짓 is_) · 기본키
    for r in rows:
        tgt, col, typ = f"{r['owner']}:{r['table']}.{r['column']}", r["column"], r["type"].upper()
        is_time = typ.startswith(("DATETIME", "TIMESTAMP"))
        if is_time and not re.search(fm["column_datetime"]["regex"], col):
            out.append(Violation("column_datetime", tgt, f"칸 '{r['table']}.{col}'({typ}) — 시각 칸은 <속성>_at"))
        elif not is_time and col.endswith("_at"):
            out.append(Violation("column_datetime", tgt, f"칸 '{r['table']}.{col}'({typ}) — _at 으로 끝나면 시각 타입이어야 한다"))
        is_bool = typ.startswith("BOOL")
        if is_bool and not re.search(fm["column_bool"]["regex"], col):
            out.append(Violation("column_bool", tgt, f"칸 '{r['table']}.{col}'(BOOLEAN) — 참거짓 칸은 is_ · has_ · can_ 으로 시작"))
        elif not is_bool and re.search(r"^(is|has|can)_", col):
            out.append(Violation("column_bool", tgt, f"칸 '{r['table']}.{col}'({typ}) — is_ · has_ · can_ 으로 시작하면 BOOLEAN 이어야 한다"))
        # 참조 칸 — 이름이 형식(regex)에 맞으면 타입이 정해진 값이어야 한다(이름을 강제하는 규칙이 아니라 '이 이름이면 이 타입')
        ref = fm["column_ref"]
        if re.search(ref["regex"], col) and ref.get("type") and typ != ref["type"].upper():
            out.append(Violation("column_ref", tgt, f"칸 '{r['table']}.{col}'({typ}) — 참조 칸은 {ref['type']}(ref_column(), UUIDv7)"))
    tables: dict[tuple, list[dict]] = {}
    for r in rows:
        tables.setdefault((r["owner"], r["table"]), []).append(r)
    for (svc, table), cs in sorted(tables.items()):
        pks = [c for c in cs if "PK" in c.get("flags", [])]
        want = fm["pk"]
        if len(pks) != 1 or not re.search(want["regex"], pks[0]["column"]) or (want.get("type") and pks[0]["type"].upper() != want["type"]):
            got = ", ".join(f"{c['column']} {c['type']}" for c in pks) or "없음"
            out.append(Violation("pk", f"{svc}:{table}", f"표 '{table}' 기본키 {got} — 단일 칸 id {want.get('type', '')}(id_column(), ADR-003)"))
    # 토픽 — 첫 마디 도메인 · 끝 마디 과거형
    svcs = _services(root)
    domains = {s["name"].replace("-", "_") for s in svcs.values()} | {s.get("package") for s in svcs.values() if s.get("package")} \
        | set(rules.get("topic_domains", {}))
    for target, t in names["topic"]:
        parts = t.split(".")
        if len(parts) != 3:
            continue  # 형식 위반으로 이미 잡힌다
        if parts[0] not in domains:
            out.append(Violation("topic", target, f"토픽 '{t}' — 첫 마디 '{parts[0]}' 는 서비스(밑줄) · 패키지 · topic_domains({', '.join(sorted(rules.get('topic_domains', {})))}) 가 아니다"))
        if not _is_past(parts[2], irregular):
            out.append(Violation("topic", target, f"토픽 '{t}' — 끝 마디 '{parts[2]}' 는 과거형(-ed 또는 past_tense_irregular)이어야 한다(일어난 사실)"))
    # 권한 — 모듈 실재
    modules = {s.get("perm") or s["name"] for s in svcs.values() if not s.get("gateway")} | set(rules.get("declared_permission_modules", {}))
    for target, p in names["permission"]:
        if p != "*" and "." in p and p.split(".", 1)[0] not in modules:
            out.append(Violation("permission", target, f"권한 '{p}' — 모듈 '{p.split('.', 1)[0]}' 는 서비스 perm/이름 · declared_permission_modules 가 아니다"))
    # 팩 — 확장 표 · pack.json entities
    state_for_packs = {}
    try:
        state_for_packs = entities(root)
    except NamingError:
        pass  # 원장 오류는 아래 원장 검사가 보고한다
    for _, pk in names["pack"]:
        d = root / "packs" / pk
        for py in sorted((d / "schema").rglob("*.py")) if (d / "schema").exists() else []:
            for t in TABLENAME.findall(py.read_text(encoding="utf-8")):
                if not pattern("pack_ext_table", root, pack=pk).match(t):
                    out.append(Violation("pack_ext_table", f"{pk}:{t}", f"팩 {pk} 의 표 '{t}' — 확장 표는 {pk}_<개체>_ext(코어 표에 칸을 더하지 않는다)"))
        meta = _read_json(root, f"packs/{pk}/pack.json", {}) or {}
        for k in meta.get("entities", []):
            e = state_for_packs.get(k)
            if not e or e["layer"] != "pack" or e.get("pack") != pk:
                errs.append(f"팩 {pk}: pack.json entities 의 '{k}' — 개념 원장에 layer=pack · pack={pk} 로 등재돼야 한다")
    errs += check_entities(root, names, rows)
    return out, errs


def check_entities(root: Path, names: dict, rows: list[dict]) -> list[str]:
    """개념 원장 — 재생 일치 · 항목 형식 · 금지 별칭 사용 · 좀비 · 미등재."""
    root = Path(root)
    errs = []
    try:
        state = entities(root)
    except NamingError as e:
        return [f"개념 원장 이력 오류: {e}"]
    snap = root / ENTITIES
    if not same(snap, snapshot_text(state)):
        errs.append(f"{ENTITIES} 가 {ENTITY_LOG} 재생 결과와 다르다 — 손으로 고치지 말고 `python nova.py naming entity|alias|retire|layer`")
    seen: dict[tuple, str] = {}
    for key, e in state.items():
        errs += [f"개념 원장: {x}" for x in _validate_entity(root, key, e)]
        if e["status"] not in STATUSES:
            errs.append(f"개념 원장: {key} status '{e['status']}'")
        if e["status"] != "retired" and e.get("table"):
            k = (e.get("service"), e["table"])
            if k in seen:
                errs.append(f"개념 원장: {k[0]}.{k[1]} 가 {seen[k]} · {key} 두 개념에 등재됐다")
            seen[k] = key
        if e.get("pack"):
            meta = _read_json(root, f"packs/{e['pack']}/pack.json", {}) or {}
            if e["status"] != "retired" and key not in meta.get("entities", []):
                errs.append(f"개념 원장: {key} 는 팩 {e['pack']} 개념인데 packs/{e['pack']}/pack.json entities 에 없다")
    # 금지 별칭 — 대장 이름의 마디로 쓰였으면 실패(같은 개념이 다른 이름으로 생긴 것)
    pool = [(k, t, n) for k in ("table", "column", "topic", "permission", "api_segment", "component") for t, n in names.get(k, [])]
    for key, e in state.items():
        if e["status"] == "retired":
            continue
        for alias in e.get("forbidden_aliases", []):
            at = normalize(alias).split()
            if not at:
                continue
            for kind, target, n in pool:
                nt = normalize(n).split()
                if any(nt[i:i + len(at)] == at for i in range(len(nt) - len(at) + 1)):
                    errs.append(f"금지 별칭: {KIND_LABEL[kind]} '{n}'({target}) 에 '{alias}' — 개념 '{key}'({e['title_ko']}) 의 정본 이름을 쓴다")
    # 좀비 · 미등재
    biz = {(r["owner"], r["table"]) for r in rows if r["owner"] != "*"}
    common = {r["table"] for r in rows if r["owner"] == "*"}
    covered = set()
    for key, e in state.items():
        if e["status"] == "retired" or not e.get("table"):
            continue
        if e.get("service") == "*":
            covered.add(("*", e["table"]))
            if rows and e["table"] not in common:
                errs.append(f"좀비 개념: {key} — 공통 표 '{e['table']}' 가 실물(DB 사전)에 없다. 사라졌으면 `naming retire {key} --why …`")
        else:
            covered.add((e["service"], e["table"]))
            if (e["service"], e["table"]) not in biz:
                errs.append(f"좀비 개념: {key} — 표 {e['service']}.{e['table']} 가 실물(DB 사전)에 없다. 이름이 바뀌었거나 사라졌으면 `naming retire {key} --why …`")
    for svc, table in sorted(biz - covered):
        errs.append(f"미등재 표: {svc}.{table} — 개념 원장에 없다. `python nova.py naming lookup {table}` 후 사람 승인으로 `naming entity add`")
    return errs


def check(root: Path = ROOT) -> tuple[list[str], dict]:
    """실패 메시지 목록과 요약 수치."""
    root = Path(root)
    try:
        rules = load_rules(root)
    except NamingError as e:
        return [f"{e} — 판정 불가"], {}
    viol, errs = collect(root)
    allow = {}
    for kind in ("baseline", "exceptions"):
        for i, b in enumerate(rules.get(kind) or []):
            if not (b.get("rule") and b.get("target") and str(b.get("why") or "").strip()):
                errs.append(f"naming.json {kind}[{i}]: rule · target · why(이유) 가 모두 있어야 한다 — {b}")
                continue
            allow[(b["rule"], b["target"])] = kind
    hit = set()
    for v in viol:
        if (v.rule, v.target) in allow:
            hit.add((v.rule, v.target))
        else:
            errs.append(f"[{v.rule}] {v.message}")
    for (rule, target), kind in sorted(allow.items()):
        if (rule, target) not in hit:
            errs.append(f"naming.json {kind}: [{rule}] {target} 는 더 이상 위반이 아니다 — 목록에서 지운다(baseline 은 줄기만 한다)")
    doc = root / DOC
    if not doc.exists():
        errs.append(f"{DOC} 가 없다")
    else:
        text = doc.read_text(encoding="utf-8").replace("\r\n", "\n")
        try:
            if text != splice(text, render_section(rules)):
                errs.append(f"{DOC} 형식 표 구간이 naming.json 과 다르다 — `python nova.py naming --write`")
        except NamingError as e:
            errs.append(str(e))
    stats = {"rules": len(rules.get("formats", {})) + len((rules.get("project") or {}).get("formats", {})),
             "violations": len(viol), "baseline": len(rules.get("baseline") or []), "exceptions": len(rules.get("exceptions") or [])}
    try:
        stats["entities"] = sum(e["status"] != "retired" for e in entities(root).values())
    except NamingError:
        stats["entities"] = 0
    return errs, stats


# ------------------------------------------------------------------ 사람용 문서 구간
def _cell(v: str) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_section(rules: dict) -> str:
    fm = rules.get("formats") or {}
    lines = [BEGIN, "", "### 형식 표", "", "| 규칙 | 대상 | 형식 | 예 | 이유 |", "|---|---|---|---|---|"]
    for rid, f in fm.items():
        spec = (f"`{_cell(f['regex'])}`" if "regex" in f else "") + (f" 아님 `{_cell(f['deny'])}`" if "deny" in f else "")
        if f.get("type"):
            spec += f" · 타입 `{f['type']}`"
        lines.append(f"| `{rid}` | {_cell(f.get('label', rid))} | {spec.strip()} | {_cell(f.get('example', '—'))} | {_cell(f.get('why', '—'))} |")
    lines += ["", "### 금지 축약 (모든 식별자 마디)", "", "| 축약 | 대신 쓰는 말 |", "|---|---|"]
    lines += [f"| `{k}` | `{v}` |" for k, v in rules.get("forbidden_abbr", {}).items()]
    lines += ["", "### 토픽 끝 마디 — 불규칙 과거형", "", " · ".join(f"`{w}`" for w in rules.get("past_tense_irregular", [])) or "(없음)"]
    lines += ["", "### 토픽 첫 마디 · 권한 모듈로 더 허용하는 말", "", "| 구분 | 말 | 이유 |", "|---|---|---|"]
    lines += [f"| 토픽 도메인 | `{k}` | {_cell(v)} |" for k, v in rules.get("topic_domains", {}).items()]
    lines += [f"| 권한 모듈 | `{k}` | {_cell(v)} |" for k, v in rules.get("declared_permission_modules", {}).items()]
    for kind, title in (("baseline", "baseline — 이 규약 이전부터 있던 위반(신규만 막는다 · 고치면 지운다)"), ("exceptions", "의도한 예외")):
        items = rules.get(kind) or []
        lines += ["", f"### {title}", ""]
        if items:
            lines += ["| 규칙 | 대상 | 이유 |", "|---|---|---|"]
            lines += [f"| `{b['rule']}` | `{_cell(b['target'])}` | {_cell(b.get('why', ''))} |" for b in items]
        else:
            lines.append("(없음)")
    proj = rules.get("project") or {}
    lines += ["", "### 프로젝트 추가 형식", ""]
    pf, pa = proj.get("formats") or {}, proj.get("forbidden_abbr") or {}
    if pf or pa:
        lines += ["| 규칙 | 적용 대상 | 형식 | 이유 |", "|---|---|---|---|"]
        lines += [f"| `project.{k}` | {f.get('applies_to', '?')} | `{_cell(f.get('regex') or f.get('deny', ''))}` | {_cell(f.get('why', ''))} |" for k, f in pf.items()]
        lines += [f"| 금지 축약 | 모든 마디 | `{k}` → `{v}` | 프로젝트 |" for k, v in pa.items()]
    else:
        lines.append("(없음 — `registry/naming.json` `project` 절에 더한다)")
    lines += ["", END]
    return "\n".join(lines)


def splice(text: str, section: str) -> str:
    b, e = text.find(BEGIN), text.find(END)
    if b < 0 or e < 0 or e < b:
        raise NamingError(f"{DOC} 에 생성 구간 표식이 없다 — '{BEGIN[:20]}…' 와 '{END}' 사이에 만든다")
    return text[:b] + section + text[e + len(END):]


def write_doc(root: Path = ROOT) -> bool:
    p = Path(root) / DOC
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    new = splice(text, render_section(load_rules(root)))
    if new != text:
        write(p, new)
        return True
    return False


# ------------------------------------------------------------------ 명령줄
def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help=f"{DOC} 생성 구간을 naming.json 에서 다시 만든다")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("check", help="lint — 형식 · 원장 검사(실패면 1)")
    lk = sub.add_parser("lookup", help="이름 짓기 전에 조회(항상 0)")
    lk.add_argument("concepts", nargs="+")
    lk.add_argument("--json", action="store_true")
    ent = sub.add_parser("entity").add_subparsers(dest="sub", required=True)
    ea = ent.add_parser("add")
    ea.add_argument("key")
    ea.add_argument("--title", required=True)
    ea.add_argument("--service")
    ea.add_argument("--table")
    ea.add_argument("--layer", required=True, choices=LAYERS)
    ea.add_argument("--pack")
    ea.add_argument("--note", default="")
    al = sub.add_parser("alias").add_subparsers(dest="sub", required=True)
    aa = al.add_parser("add")
    aa.add_argument("key")
    aa.add_argument("alias")
    aa.add_argument("--forbidden", action="store_true", help="금지 별칭 — 대장 이름에 쓰이면 check 실패")
    rt = sub.add_parser("retire")
    rt.add_argument("key")
    rt.add_argument("--why", required=True)
    ly = sub.add_parser("layer").add_subparsers(dest="sub", required=True)
    ls = ly.add_parser("set")
    ls.add_argument("key")
    ls.add_argument("layer", choices=LAYERS)
    ls.add_argument("--why", required=True)
    ls.add_argument("--pack")
    for p in (ea, aa, rt, ls):
        p.add_argument("--by")
    a = ap.parse_args(argv)
    try:
        if a.write and not a.cmd:
            changed = write_doc(root)
            print(f"✓ {DOC} 형식 표 구간 " + ("갱신" if changed else "변경 없음"))
            return 0
        if a.cmd == "check":
            errs, st = check(root)
            for e in errs:
                print("✗", e)
            if errs:
                return 1
            print(f"✓ 명명 정상: 형식 {st['rules']} · baseline {st['baseline']} · 예외 {st['exceptions']} · 개념 {st['entities']}")
            return 0
        if a.cmd == "lookup":
            res = [lookup(root, c) for c in a.concepts]
            if a.json:
                print(json.dumps(res, ensure_ascii=False, indent=1))
            else:
                for r in res:
                    print("\n".join(advice(r)))
            return 0
        if a.cmd in ("entity", "alias", "retire", "layer"):
            require_main(f"naming {a.cmd}", cwd=root)
            if a.cmd == "entity":
                e = add_entity(root, a.key, a.title, a.service, a.table, a.layer, a.pack, by=a.by, note=a.note)
            elif a.cmd == "alias":
                e = add_alias(root, a.key, a.alias, a.forbidden, by=a.by)
            elif a.cmd == "retire":
                e = retire(root, a.key, a.why, by=a.by)
            else:
                e = set_layer(root, a.key, a.layer, a.why, a.pack, by=a.by)
            print(f"✓ {a.cmd}: {e['key']} [{e['status']} · {e['layer']}] — {ENTITY_LOG} · {ENTITIES}")
            return 0
        ap.print_help()
        return 2
    except NamingError as e:
        print("✗", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
