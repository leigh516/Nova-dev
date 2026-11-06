#!/usr/bin/env python3
"""대장 4종 — 화면 · DB 사전 · 권한 · 이벤트 (REQ-261103-04 · ADR-004). 전부 코드에서 파생한다(손으로 쓰지 않는다).

  uv run python scripts/ledgers.py          # registry/ledgers.json(기계용) + docs/registry/{screens,db-dictionary,permissions,events}.md(사람용)
  uv run python scripts/ledgers.py --check  # 생성물 최신 여부 + 대장 정합 검사(lint)

원천:
  DB 사전  SQLAlchemy 메타데이터(각 서비스 <pkg>.main 의 svc.Base) — 1행 = 1컬럼, '의미' = mapped_column(comment=…)
  권한     서비스 권한 모듈(services.json perm) × 라우트 행위(GET=read … · rbac.json overrides) + 역할 정본 rbac.json
  이벤트   kafka-topics.txt + 서비스 코드의 svc.emit(…) · @svc.on(…) (상수 이름도 해석) · 페이로드는 events/<토픽>.avsc 또는 emit 의 dict 키
  화면     웹 화면 파일(page.tsx)이 부르는 API(api(…) · useApi(…) · source=…) → 그 API 의 서비스 → 그 서비스의 표.
           이름 · 진행 상태는 화면 머리 주석 `/** @screen 이름 · @status 기획|설계|개발|완료 */`
정합 검사(실패): 화면이 없는 API 를 부름 · 메뉴/역할 표가 없는 권한을 씀 · 개발 계정 역할이 역할 표에 없음 · 구독만 있고 카탈로그에 없는 토픽
알림(실패 아님): 발행자 없는 토픽 · 구독자 없는 토픽 · 의미(comment) 없는 컬럼
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, project, same, write  # noqa: E402

from nova_common import catalog  # noqa: E402

OUT_JSON = ROOT / "registry" / "ledgers.json"
VIEW = ROOT / "docs" / "registry"
GW = ROOT / "services" / "gateway" / "gateway"
TOPICS = ROOT / "infra" / "k3s" / "base" / "kafka-topics.txt"
SCHEMAS = ROOT / "packages" / "common-py" / "events"
METHOD_ACTION = {"GET": "read", "HEAD": "read", "POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete"}
ACTION_LABEL = {"read": "조회", "create": "등록", "update": "수정", "delete": "삭제"}
STATUSES = ("기획", "설계", "개발", "완료")
HDR = "> 생성 파일 — `uv run python scripts/ledgers.py` 가 코드에서 파생한다(ADR-004). 직접 고치지 않는다 — 원천(코드 · 선언)을 고친다."
INFRA_TABLES = {"outbox", "processed_event"}


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def service_files(name: str) -> list[Path]:
    base = ROOT / "services" / name
    return sorted(p for p in base.rglob("*.py") if "tests" not in p.parts and ".pytest_cache" not in p.parts)


# ------------------------------------------------------------------ API (생성물 원장 스캐너와 같은 규칙)
ROUTE = re.compile(r"@(?:app|router)\.(get|post|put|patch|delete)\(\s*\"([^\"]*)\"")
PREFIX = re.compile(r"APIRouter\(\s*prefix\s*=\s*\"([^\"]+)\"")


def scan_apis() -> list[dict]:
    out = []
    for s in catalog.services():
        for p in service_files(s.name):
            text = p.read_text(encoding="utf-8")
            pm = PREFIX.search(text)
            for m in ROUTE.finditer(text):
                path = (pm.group(1) if pm else "") + m.group(2)
                public = path.removeprefix("/v1") if s.gateway else path  # 화면이 부르는 경로(/v1 아래)
                if public.startswith("/internal"):
                    continue
                out.append({"method": m.group(1).upper(), "path": path, "public": public, "service": s.name, "loc": rel(p)})
    return out


def path_regex(path: str) -> re.Pattern:
    return re.compile("^" + re.sub(r"\\\{[^}]*\\\}", "[^/]+", re.escape(path)) + "$")


# ------------------------------------------------------------------ DB 사전
def scan_db() -> list[dict]:
    rows = []
    saved = dict(os.environ)  # import 동안만 메모리 DB — 끝나면 환경을 되돌린다(호출한 프로세스 · 하위 프로세스에 새지 않게)
    try:
        mods = {}
        for s in catalog.services():
            if not s.db:
                continue
            os.environ.setdefault(f"DATABASE_URL_{s.env}", "sqlite://")
            sys.path.insert(0, str(ROOT / "services" / s.name))
            mods[s.name] = importlib.import_module(f"{s.package}.main")
    finally:
        os.environ.clear()
        os.environ.update(saved)
    for s in catalog.services():
        if s.name not in mods:
            continue
        mod = mods[s.name]
        for t in sorted(mod.svc.Base.metadata.sorted_tables, key=lambda t: (t.name in INFRA_TABLES, t.name)):
            for c in t.columns:
                flags = [x for x, on in (("PK", c.primary_key), ("UNIQUE", c.unique), ("INDEX", c.index), ("NULL", c.nullable and not c.primary_key)) if on]
                fks = [f"FK→{fk.column.table.name}.{fk.column.name}" for fk in c.foreign_keys]
                rows.append({"table": t.name, "column": c.name, "type": str(c.type), "meaning": c.comment or "",
                             "flags": flags + fks, "service": s.name, "common": t.name in INFRA_TABLES})
    return rows


# ------------------------------------------------------------------ 권한
def perm_matches(granted: list[str], perm: str) -> bool:
    return "*" in granted or perm in granted or f"{perm.split('.', 1)[0]}.*" in granted


def scan_permissions(apis: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    rbac = json.loads((GW / "rbac.json").read_text(encoding="utf-8"))
    overrides = [(re.compile(o["pattern"]), o["action"]) for o in rbac.get("overrides", [])]
    perms: dict[str, dict] = {}
    for a in apis:
        spec = catalog.get(a["service"])
        if spec.gateway:
            continue
        module = spec.perm or spec.name
        action = next((act for rx, act in overrides if rx.search(a["public"].replace("{", "x").replace("}", ""))), None) \
            or METHOD_ACTION.get(a["method"], "read")
        key = f"{module}.{action}"
        p = perms.setdefault(key, {"key": key, "module": module, "action": action, "apis": [], "service": spec.name})
        p["apis"].append(f"{a['method']} {a['public']}")
    # 게이트웨이 자체 권한(OWN_PERMS)
    own = re.search(r"OWN_PERMS\s*=\s*\{([^}]*)\}", (GW / "routing.py").read_text(encoding="utf-8"))
    for k in re.findall(r"\"(\w+\.\w+)\"", own.group(1) if own else ""):
        if "." in k and not k.startswith("/"):
            m, act = k.split(".", 1)
            perms.setdefault(k, {"key": k, "module": m, "action": act, "apis": ["게이트웨이 운영 API"], "service": catalog.gateway()})
    roles = []
    errors = []
    for code, r in rbac["roles"].items():
        granted = r["perms"] if isinstance(r, dict) else r
        for g in granted:
            if g != "*" and not g.endswith(".*") and g not in perms:
                errors.append(f"권한 표: 역할 {code} 가 없는 권한 {g} 을(를) 가짐(쓰는 API 가 없다)")
            if g.endswith(".*") and not any(p["module"] == g[:-2] for p in perms.values()):
                errors.append(f"권한 표: 역할 {code} 의 {g} — 그런 모듈이 없다")
        roles.append({"code": code, "name": r.get("name", code) if isinstance(r, dict) else code, "grants": granted})
    out = []
    for key in sorted(perms):
        p = perms[key]
        holders = [r["code"] for r in roles if perm_matches(r["grants"], key)]
        out.append({**p, "label": f"{p['module']} {ACTION_LABEL.get(p['action'], p['action'])}", "roles": holders})
    # 메뉴 · 개발 계정
    menu = json.loads((GW / "menu.json").read_text(encoding="utf-8"))
    for it in menu.get("items", []):
        if it.get("perm") and it["perm"] not in perms:
            errors.append(f"메뉴 {it['key']}: 없는 권한 {it['perm']}")
    users = json.loads((GW / "dev_users.json").read_text(encoding="utf-8"))
    codes = {r["code"] for r in roles}
    for u in users.get("users", []):
        if u["role"] not in codes:
            errors.append(f"개발 계정 {u['email']}: 역할 표에 없는 역할 {u['role']}")
    return out, roles, errors


# ------------------------------------------------------------------ 이벤트
CONST = re.compile(r"^(\w+)\s*=\s*\"([a-z][a-z0-9_]*\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)\"", re.M)
EMIT = re.compile(r"svc\.emit\(\s*\w+\s*,\s*(?:\"([^\"]+)\"|(\w+))\s*,\s*[^,]+,\s*(\{[^}]*\})?")
# 키워드 인자(broadcast=True 등, REQ-261104-11-4)가 붙어도 구독으로 읽는다 — 빠지면 대장에서 구독자가 사라진다
ON = re.compile(r"@svc\.on\(\s*(?:\"([^\"]+)\"|(\w+))\s*(?:,[^)]*)?\)")


def scan_events() -> tuple[list[dict], list[str]]:
    lines = [ln.split() for ln in TOPICS.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    topics = {ln[0]: {"topic": ln[0], "partitions": int(ln[1]), "retention_days": int(ln[2]), "publishers": set(), "subscribers": set(), "payload": set()} for ln in lines}
    errors = []
    for s in catalog.services():
        for p in service_files(s.name):
            text = p.read_text(encoding="utf-8")
            consts = dict(CONST.findall(text))
            for m in EMIT.finditer(text):
                t = m.group(1) or consts.get(m.group(2) or "")
                if t and t in topics:
                    topics[t]["publishers"].add(s.name)
                    topics[t]["payload"].update(re.findall(r"\"(\w+)\"\s*:", m.group(3) or ""))
            for m in ON.finditer(text):
                t = m.group(1) or consts.get(m.group(2) or "")
                if t is None:
                    continue
                if t not in topics:
                    errors.append(f"이벤트: {s.name} 가 카탈로그에 없는 토픽 {t} 을(를) 구독")
                else:
                    topics[t]["subscribers"].add(s.name)
    out = []
    for t in topics.values():
        schema = SCHEMAS / f"{t['topic']}.avsc"
        if schema.exists():
            t["payload"] = {f["name"] for f in json.loads(schema.read_text(encoding="utf-8")).get("fields", [])}
        out.append({**t, "publishers": sorted(t["publishers"]), "subscribers": sorted(t["subscribers"]), "payload": sorted(t["payload"]),
                    "schema": rel(schema) if schema.exists() else None})
    return out, errors


# ------------------------------------------------------------------ 화면
DECL = re.compile(r"@screen\s+([^·*@]+?)\s*(?:·\s*@status\s+(\S+))?\s*\*/")
CALLS = [
    (re.compile(r"\bapi(?:<[^>()]*>)?\(\s*([`\"'])(/[^`\"']*)\1(?P<rest>[^)]{0,120})"), None),
    (re.compile(r"\buseApi(?:<[^>()]*>)?\(\s*([`\"'])(/[^`\"']*)\1"), "GET"),
    (re.compile(r"\bsource=\{?\s*([`\"'])(/[^`\"']*)\1"), "GET"),
]
METHOD_IN = re.compile(r"method:\s*\"(\w+)\"")


def scan_screens(apis: list[dict], db: list[dict]) -> tuple[list[dict], list[str]]:
    index = [(a, path_regex(a["public"])) for a in apis]
    tables = {}
    for r in db:
        if not r["common"]:
            tables.setdefault(r["service"], set()).add(r["table"])
    reg = {}
    regf = ROOT / "registry" / "registry.json"
    if regf.exists():
        for rid, r in json.loads(regf.read_text(encoding="utf-8")).items():
            if r["kind"] == "SCR" and r["status"] != "deleted":
                reg[(r["scope"], r["name"])] = rid
    out, errors = [], []
    for w in project().get("web_apps", []):
        base = ROOT / "web" / "apps" / w["name"] / "app"
        scope = w.get("scope", "W" + w["name"].upper())
        for page in sorted(base.rglob("page.tsx")) if base.exists() else []:
            parts = [x for x in page.relative_to(base).parts[:-1] if not (x.startswith("(") and x.endswith(")"))]
            route = "/" + "/".join(parts)
            text = page.read_text(encoding="utf-8")
            d = DECL.search(text)
            name = d.group(1).strip() if d else route
            status = (d.group(2) if d and d.group(2) else "개발")
            if status not in STATUSES:
                errors.append(f"화면 {route}: @status '{status}' — {'·'.join(STATUSES)} 중 하나")
            used, svcs = [], set()
            for rx, fixed in CALLS:
                for m in rx.finditer(text):
                    path = re.sub(r"\$\{[^}]*\}", "{x}", m.group(2)).split("?")[0]
                    method = fixed or (METHOD_IN.search(m.group("rest") or "") or [None, "GET"])[1]
                    probe = path.replace("{x}", "x")
                    hit = next((a for a, rx2 in index if a["method"] == method and rx2.match(probe)), None)
                    if hit is None:
                        errors.append(f"화면 {route}: 없는 API 를 부름 {method} {path} ({rel(page)})")
                        continue
                    key = f"{hit['method']} {hit['public']}"
                    if key not in used:
                        used.append(key)
                    svcs.add(hit["service"])
            used_tables = sorted({t for s in svcs for t in tables.get(s, ())})
            out.append({"id": reg.get((scope, route)), "app": w["name"], "name": name, "route": route, "status": status,
                        "apis": used, "tables": used_tables, "loc": rel(page)})
    return out, errors


# ------------------------------------------------------------------ 보기(MD)
def md_table(head: list[str], rows: list[list[str]]) -> str:
    esc = lambda v: str(v).replace("|", "\\|").replace("\n", " ")  # noqa: E731
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head), *("| " + " | ".join(esc(c) for c in r) + " |" for r in rows)]) + "\n"


def render(data: dict) -> dict[Path, str]:
    s, d, p, e = data["screens"], data["db"], data["permissions"], data["events"]
    v = {}
    v[VIEW / "screens.md"] = f"""# 화면 대장

{HDR}

화면 ↔ 라우트 ↔ API ↔ 표 ↔ 상태. 새 화면은 머리 주석 `/** @screen 이름 · @status 기획|설계|개발|완료 */` 를 쓰고, 부르는 API 는 코드에서 자동으로 잡힌다. 표는 그 API 를 가진 서비스의 표(서비스 단위).

""" + md_table(["화면ID", "앱", "이름", "라우트", "사용 API", "사용 표", "상태"],
               [[x["id"] or "(원장 sync 필요)", x["app"], x["name"], x["route"], ", ".join(x["apis"]) or "—", ", ".join(x["tables"]) or "—", x["status"]] for x in s])
    v[VIEW / "db-dictionary.md"] = f"""# DB 사전 (1행 = 1컬럼)

{HDR}

현재 상태의 조회용 정본 — `grep <컬럼>` 으로 바로 찾는다. '의미'는 모델의 `mapped_column(comment=…)`. 소유 서비스만 쓰고, 다른 서비스는 API · 이벤트로만 접근한다(backend.md §2).
공통 표(`outbox` · `processed_event`)는 모든 DB 서비스에 같은 모양으로 있다 — 맨 아래 한 번만 적는다.

""" + md_table(["표", "컬럼", "타입", "의미", "제약", "소유 서비스"],
               [[r["table"], r["column"], r["type"], r["meaning"] or "(의미 없음 — comment 를 쓴다)", " ".join(r["flags"]) or "—", r["service"]] for r in d if not r["common"]]) + """
## 공통 표 (모든 DB 서비스)

""" + md_table(["표", "컬럼", "타입", "의미", "제약"],
               [[r["table"], r["column"], r["type"], r["meaning"], " ".join(r["flags"]) or "—"]
                for r in {(r["table"], r["column"]): r for r in d if r["common"]}.values()])
    v[VIEW / "permissions.md"] = f"""# 권한 대장

{HDR}

권한키 `<모듈>.<행위>` — 모듈 = services.json `perm`(없으면 서비스 이름), 행위 = HTTP 메서드(GET=read · POST=create · PUT/PATCH=update · DELETE=delete) 또는 rbac.json `overrides`.
역할 정본: [`services/gateway/gateway/rbac.json`](../../services/gateway/gateway/rbac.json) — 역할은 여기 먼저 등재한다. AI 자동화도 같은 권한 검사를 받는다(STD-AX-001).

## 역할

""" + md_table(["역할", "이름", "부여"], [[r["code"], r["name"], ", ".join(r["grants"]) or "—"] for r in data["roles"]]) + """
## 권한

""" + md_table(["권한키", "설명", "보유 역할", "쓰는 API"], [[x["key"], x["label"], ", ".join(x["roles"]) or "—", ", ".join(x["apis"])] for x in p])
    v[VIEW / "events.md"] = f"""# 이벤트 대장

{HDR}

이벤트 이름 `<도메인>.<개체>.<과거형>` — 일어난 사실. **카탈로그(`infra/k3s/base/kafka-topics.txt`) 등재 없는 발행 금지**. 페이로드는 추가만(새 필드는 기본값) — 필드 삭제 · 타입 변경 · 의미 변경은 새 토픽(봉투 `version` 도 올린다).

""" + md_table(["이벤트", "발행", "구독", "페이로드", "파티션", "보존(일)"],
               [[x["topic"], ", ".join(x["publishers"]) or "—(아직 없음)", ", ".join(x["subscribers"]) or "—", ", ".join(x["payload"]) or "—", x["partitions"], x["retention_days"]] for x in e])
    return v


def build() -> tuple[dict, list[str], list[str]]:
    apis = scan_apis()
    db = scan_db()
    perms, roles, perr = scan_permissions(apis)
    events, eerr = scan_events()
    screens, serr = scan_screens(apis, db)
    data = {"screens": screens, "db": db, "permissions": perms, "roles": roles, "events": events}
    warns = [f"이벤트 {x['topic']}: 발행하는 서비스가 아직 없다" for x in events if not x["publishers"]]
    warns += [f"이벤트 {x['topic']}: 구독하는 서비스가 없다" for x in events if not x["subscribers"] and x["publishers"]]
    warns += [f"DB {r['table']}.{r['column']}: 의미(comment) 없음" for r in db if not r["meaning"]]
    return data, perr + eerr + serr, warns


def main(check: bool) -> int:
    data, errors, warns = build()
    outs = {OUT_JSON: json.dumps(data, ensure_ascii=False, indent=1) + "\n", **render(data)}
    for w in warns:
        print("·", w)
    stale = [p for p, t in outs.items() if not same(p, t)]
    if check:
        errors += [f"대장이 최신이 아님: {rel(p)} — uv run python scripts/ledgers.py" for p in stale]
    else:
        for p in stale:
            write(p, outs[p])
    for e in errors:
        print("✗", e)
    if errors:
        return 1
    print(f"✓ 대장 정상: 화면 {len(data['screens'])} · 컬럼 {len(data['db'])} · 권한 {len(data['permissions'])} · 역할 {len(data['roles'])} · 이벤트 {len(data['events'])}"
          + ("" if check else f" (변경 {len(stale)})"))
    return 0


def cli(argv: list[str] | None = None) -> int:
    """명령줄 — -h/--help 는 사용법만 출력하고 아무것도 쓰지 않는다(모르는 인자도 쓰기 전에 거절)."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="쓰지 않고 최신 여부 · 정합만 검사(lint)")
    return main(ap.parse_args(argv).check)


if __name__ == "__main__":
    raise SystemExit(cli())
