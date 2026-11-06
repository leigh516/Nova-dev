"""생성물 원장(artifact registry) — DB 테이블 · API · 화면 · 컴포넌트 · 서비스 · 토픽에 일관 ID 를 주고 생애를 추적한다.

원천은 추가 전용 이벤트 로그 registry/events.jsonl(JSONL — 한 줄 한 사건, 병합 · 감사 친화).
현재 상태 registry/registry.json(JSON 스냅샷)과 사람용 docs/registry/README.md(MD 보기)는 이벤트를 재생해 생성한다(손으로 고치지 않는다).
무엇을 생성물로 보는지(스캐너)는 registry/registry.config.json 에서 정한다 — 엔진(이 파일)은 프로젝트와 무관하다.

    uv run python scripts/registry.py scan                 # 코드에서 발견한 생성물 수(종류·범위별)
    uv run python scripts/registry.py sync --by 이름 [--note 사유]   # 코드 ↔ 원장 맞추기(신규 create·이동 update·사라짐 delete)
    uv run python scripts/registry.py check                # CI·make lint: 스냅샷=재생, 코드=원장, 중복·삭제 이름 재생성
    uv run python scripts/registry.py show <ID|이름>        # 한 생성물의 이력
    uv run python scripts/registry.py usage <ID|이름>       # 저장소 안 현재 참조 위치(삭제물 사용성 확인)
    uv run python scripts/registry.py restore <ID> --by 이름 --note 사유
    uv run python scripts/registry.py deprecate <ID> --by 이름 --note 사유 [--replaced-by <ID>]
    uv run python scripts/registry.py rename <ID> <새 이름> --by 이름 --note 사유
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, project, same, write  # noqa: E402

from nova_common import catalog  # noqa: E402

EVENTS = ROOT / "registry" / "events.jsonl"
SNAPSHOT = ROOT / "registry" / "registry.json"
CONFIG = ROOT / "registry" / "registry.config.json"
VIEW = ROOT / "docs" / "registry" / "README.md"


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


KIND_LABEL: dict[str, str] = config()["kinds"]
ID_RE = re.compile(r"^(" + "|".join(map(re.escape, KIND_LABEL)) + r")-[A-Z0-9]+-\d{4}$")


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class Artifact:
    kind: str
    scope: str
    name: str
    loc: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.kind, self.scope, self.name)


# ------------------------------------------------------------------ 이벤트 · 재생
def event(action: str, rec: dict, *, by: str, at: str, seq: int, note: str = "", refs: list[str] | None = None, replaced_by: str | None = None) -> dict:
    e = {"seq": seq, "at": at, "by": by, "action": action, "id": rec["id"], "kind": rec["kind"], "scope": rec["scope"], "name": rec["name"], "loc": rec.get("loc", "")}
    if note:
        e["note"] = note
    if refs is not None:
        e["refs"] = refs
    if replaced_by:
        e["replaced_by"] = replaced_by
    return e


def apply(state: dict[str, dict], e: dict) -> None:
    """이벤트 하나를 상태에 적용(재생·동기화 공용)."""
    a, rid = e["action"], e["id"]
    if a == "create":
        if rid in state:
            raise RegistryError(f"이미 있는 ID 재생성: {rid}")
        state[rid] = {"id": rid, "kind": e["kind"], "scope": e["scope"], "name": e["name"], "loc": e["loc"], "status": "active",
                      "created_at": e["at"], "updated_at": e["at"], "deleted_at": None, "refs": [], "replaced_by": None, "versions": 1}
        return
    if rid not in state:
        raise RegistryError(f"없는 ID 에 {a}: {rid}")
    r = state[rid]
    r["updated_at"], r["versions"] = e["at"], r["versions"] + 1
    if a in ("update", "rename"):
        r["name"], r["loc"] = e["name"], e["loc"]
    elif a == "deprecate":
        r["status"], r["replaced_by"] = "deprecated", e.get("replaced_by")
    elif a == "delete":
        r["status"], r["deleted_at"], r["refs"] = "deleted", e["at"], e.get("refs", [])
        r["replaced_by"] = e.get("replaced_by") or r["replaced_by"]
    elif a == "restore":
        r["status"], r["deleted_at"] = "active", None
    else:
        raise RegistryError(f"알 수 없는 action: {a}")


def replay(events: list[dict]) -> dict[str, dict]:
    state: dict[str, dict] = {}
    for i, e in enumerate(events, 1):
        if e["seq"] != i:
            raise RegistryError(f"seq 불연속: {i} 자리에 {e['seq']}")
        apply(state, e)
    return state


def _next_id(state: dict, kind: str, scope: str) -> str:
    nums = [int(i.rsplit("-", 1)[1]) for i, r in state.items() if r["kind"] == kind and r["scope"] == scope]
    return f"{kind}-{scope}-{(max(nums) if nums else 0) + 1:04d}"


def plan_sync(state: dict, scanned: list[Artifact], *, by: str, at: str, start_seq: int, refs_of=lambda a: [], note: str = "") -> list[dict]:
    """코드에서 발견한 생성물과 원장을 비교해 추가할 이벤트를 만든다(상태는 바꾸지 않음)."""
    seen: dict[tuple, Artifact] = {}
    for a in scanned:
        if a.key in seen:
            raise RegistryError(f"같은 이름 중복: {a.kind}/{a.scope}/{a.name} — {seen[a.key].loc} · {a.loc}")
        seen[a.key] = a
    state = {k: {**v, "refs": list(v["refs"])} for k, v in state.items()}
    by_key = {}
    for r in state.values():
        by_key.setdefault((r["kind"], r["scope"], r["name"]), []).append(r)
    out, seq = [], start_seq

    def add(e):
        nonlocal seq
        out.append(e)
        apply(state, e)
        seq += 1

    for key, a in seen.items():
        recs = by_key.get(key, [])
        live = [r for r in recs if r["status"] != "deleted"]
        if live:
            r = live[0]
            if r["loc"] != a.loc:
                add(event("update", {**r, "loc": a.loc}, by=by, at=at, seq=seq, note=note or "위치 변경"))
            continue
        dead = [r for r in recs if r["status"] == "deleted"]
        if dead:
            ids = ", ".join(r["id"] for r in dead)
            raise RegistryError(f"삭제된 이름을 새로 만들 수 없음: {a.kind}/{a.scope}/{a.name} (원장 {ids}) — 되살리려면 `uv run python scripts/registry.py restore {dead[-1]['id']} --by <이름> --note <사유>`")
        rid = _next_id(state, a.kind, a.scope)
        add(event("create", {"id": rid, "kind": a.kind, "scope": a.scope, "name": a.name, "loc": a.loc}, by=by, at=at, seq=seq, note=note))
    # 이번 동기화에서 새로 생긴 것(종류·이름 → ID들) — 다른 서비스로 '옮긴' 것을 알아보는 데 쓴다(서비스 분리 · 통합)
    created: dict[tuple, list[dict]] = {}
    for e in out:
        if e["action"] == "create":
            created.setdefault((e["kind"], e["name"]), []).append(e)
    for r in sorted(state.values(), key=lambda r: r["id"]):
        if r["status"] != "deleted" and (r["kind"], r["scope"], r["name"]) not in seen:
            a = Artifact(r["kind"], r["scope"], r["name"], r["loc"])
            moved = [c for c in created.get((r["kind"], r["name"]), []) if c["scope"] != r["scope"]]
            to = moved[0]["id"] if len(moved) == 1 else None  # 여러 곳에 생겼으면 어느 쪽인지 모르므로 연결 안 함
            add(event("delete", r, by=by, at=at, seq=seq, note=note or (f"{to} 로 이동" if to else "코드에서 사라짐"), refs=refs_of(a), replaced_by=to))
    return out


def check(events: list[dict], snapshot: dict, scanned: list[Artifact]) -> list[str]:
    errs = []
    try:
        state = replay(events)
    except RegistryError as e:
        return [f"이벤트 로그 오류: {e}"]
    if state != snapshot:
        errs.append("스냅샷(registry.json)이 이벤트 재생 결과와 다름 — 손으로 고치지 말고 `uv run python scripts/registry.py sync --by <이름>`")
    for rid in state:
        if not ID_RE.match(rid):
            errs.append(f"ID 형식 오류: {rid}")
    active = {(r["kind"], r["scope"], r["name"]): r for r in state.values() if r["status"] != "deleted"}
    deleted = {(r["kind"], r["scope"], r["name"]): r for r in state.values() if r["status"] == "deleted"}
    keys = set()
    for a in scanned:
        if a.key in keys:
            errs.append(f"같은 이름 중복: {a.kind}/{a.scope}/{a.name} ({a.loc})")
        keys.add(a.key)
        if a.key not in active:
            hint = f" — 삭제된 {deleted[a.key]['id']} 를 restore 하세요" if a.key in deleted else ""
            errs.append(f"미등록 생성물: {a.kind}/{a.scope}/{a.name} ({a.loc}){hint} — `uv run python scripts/registry.py sync --by <이름> --note <사유>`")
    for key, r in active.items():
        if key not in keys:
            errs.append(f"원장에는 있으나 코드에 없음(삭제 미기록): {r['id']} {r['name']}")
    return errs


# ------------------------------------------------------------------ 코드에서 생성물 발견 (registry.config.json 의 scanners)
def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _fmt(template: str, groups: tuple, prefix: str = "") -> str:
    """'{0!u} {prefix}{1}' — {n} 은 정규식 그룹, !u 는 대문자, {prefix} 는 라우터 접두어."""
    def one(m: re.Match) -> str:
        v = groups[int(m.group(1))] or ""
        return v.upper() if m.group(2) == "!u" else v
    return re.sub(r"\{(\d+)(!u)?\}", one, template.replace("{prefix}", prefix))


def _service_files(name: str) -> list[Path]:
    base = ROOT / "services" / name
    return sorted(p for p in base.rglob("*.py") if "tests" not in p.parts and ".pytest_cache" not in p.parts)


def scan(cfg: dict | None = None) -> list[Artifact]:
    cfg = cfg or config()
    webs = project().get("web_apps", [])
    out: list[Artifact] = []
    for sc in cfg["scanners"]:
        kind, typ = sc["kind"], sc["type"]
        if typ == "services":
            for svc in catalog.services():
                base = ROOT / "services" / svc.name
                if base.exists():
                    out.append(Artifact(kind, sc["scope"], svc.name, _rel(base)))
            for w in webs:
                base = ROOT / "web" / "apps" / w["name"]
                if base.exists():
                    out.append(Artifact(kind, sc["scope"], f"web-{w['name']}", _rel(base)))
        elif typ == "service_regex":
            rx = re.compile(sc["regex"])
            prx = re.compile(sc["prefix_regex"]) if sc.get("prefix_regex") else None
            for svc in catalog.services():
                found = False
                for p in _service_files(svc.name):
                    text = p.read_text(encoding="utf-8")
                    pm = prx.search(text) if prx else None
                    for m in rx.finditer(text):
                        found = True
                        out.append(Artifact(kind, svc.scope, _fmt(sc["template"], m.groups(), pm.group(1) if pm else ""), _rel(p)))
                if found:
                    for t in sc.get("infra_tables", []):
                        out.append(Artifact(kind, svc.scope, t, sc["infra_loc"]))
        elif typ == "web_pages":
            for w in webs:
                base = ROOT / sc["root"].format(app=w["name"])
                for p in sorted(base.rglob("page.tsx")) if base.exists() else []:
                    parts = [x for x in p.relative_to(base).parts[:-1] if not (x.startswith("(") and x.endswith(")"))]
                    out.append(Artifact(kind, w.get("scope", "W" + w["name"].upper()), "/" + "/".join(parts), _rel(p)))
        elif typ == "glob_regex":
            rx = re.compile(sc["regex"], re.M)
            for p in sorted(ROOT.glob(sc["glob"])):
                if {"node_modules", "build", ".next"} & set(p.parts):
                    continue
                for m in rx.finditer(p.read_text(encoding="utf-8")):
                    out.append(Artifact(kind, sc["scope"], _fmt(sc.get("template", "{0}"), m.groups()), _rel(p)))
        elif typ == "lines":
            f = ROOT / sc["file"]
            for ln in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
                if ln.strip() and not ln.startswith("#"):
                    out.append(Artifact(kind, sc["scope"], ln.split()[0], _rel(f)))
        else:
            raise RegistryError(f"알 수 없는 스캐너 type: {typ}")
    return out


def refs_of(a: Artifact) -> list[str]:
    """저장소 안 참조 위치(정의 파일 제외, 최대 20) — 삭제물이 아직 어디서 쓰이는지."""
    needle = a.name.split(" ", 1)[-1] if a.kind == "API" else a.name
    if len(needle) < 3:
        return []
    try:
        r = subprocess.run(["git", "grep", "-l", "-F", needle, "--", ".", ":!registry", ":!docs/registry"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return []
    return [f for f in r.stdout.splitlines() if f != a.loc][:20]


# ------------------------------------------------------------------ 파일 입출력
def load_events() -> list[dict]:
    if not EVENTS.exists():
        return []
    return [json.loads(ln) for ln in EVENTS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def append_events(new: list[dict]) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8", newline="\n") as f:
        for e in new:
            f.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")


def snapshot_text(state: dict) -> str:
    return json.dumps(dict(sorted(state.items())), ensure_ascii=False, indent=1) + "\n"


def write_derived(state: dict) -> None:
    write(SNAPSHOT, snapshot_text(state))
    write(VIEW, render_md(state))


def render_md(state: dict) -> str:
    rows = sorted(state.values(), key=lambda r: r["id"])
    active = [r for r in rows if r["status"] != "deleted"]
    lines = ["# 생성물 원장 (artifact registry)", "",
             "> 생성 파일 — `uv run python scripts/registry.py sync` 가 `registry/events.jsonl`(원천)을 재생해 만든다. 직접 고치지 않는다.",
             "> 새로 만들기 전에 여기서 이미 있는 것을 찾는다(계획서 §8 재사용). 삭제된 이름은 새로 만들지 말고 `restore <ID>`.", "",
             "대장(코드에서 파생, ADR-004): [화면](screens.md) · [DB 사전](db-dictionary.md) · [권한](permissions.md) · [이벤트](events.md)", "",
             "| 종류 | 활성 | 폐기 | 삭제 |", "|---|---|---|---|"]
    for k, label in KIND_LABEL.items():
        ks = [r for r in rows if r["kind"] == k]
        lines.append(f"| {label} (`{k}`) | {sum(r['status'] == 'active' for r in ks)} | {sum(r['status'] == 'deprecated' for r in ks)} | {sum(r['status'] == 'deleted' for r in ks)} |")
    gone = [r for r in rows if r["status"] in ("deleted", "deprecated")]
    if gone:
        lines += ["", "## 삭제·폐기 (사용성 관리)", "", "| ID | 이름 | 상태 | 시각 | 대체 | 남은 참조(삭제 시점) |", "|---|---|---|---|---|---|"]
        for r in gone:
            refs = "<br>".join(f"`{x}`" for x in r["refs"][:5]) + (f" 외 {len(r['refs']) - 5}" if len(r["refs"]) > 5 else "")
            lines.append(f"| `{r['id']}` | {r['name']} | {r['status']} | {(r['deleted_at'] or r['updated_at'])[:10]} | {r['replaced_by'] or '—'} | {refs or '—'} |")
    for k, label in KIND_LABEL.items():
        ks = [r for r in active if r["kind"] == k]
        if not ks:
            continue
        lines += ["", f"## {label} (`{k}`)", "", "| ID | 이름 | 위치 | 버전 |", "|---|---|---|---|"]
        lines += [f"| `{r['id']}` | {r['name']} | `{r['loc']}` | {r['versions']} |" for r in ks]
    return "\n".join(lines) + "\n"


def _find(state: dict, key: str) -> dict:
    if key in state:
        return state[key]
    hits = [r for r in state.values() if r["name"] == key]
    if len(hits) != 1:
        raise RegistryError(f"ID 또는 유일한 이름이 아님: {key} ({len(hits)}건)")
    return hits[0]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="생성물 원장")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    sub.add_parser("check")
    for name in ("sync", "restore", "deprecate", "rename", "show", "usage"):
        p = sub.add_parser(name)
        if name in ("restore", "deprecate", "rename", "show", "usage"):
            p.add_argument("target")
        if name == "rename":
            p.add_argument("new_name")
        if name in ("sync", "restore", "deprecate", "rename"):
            p.add_argument("--by", required=True)
            p.add_argument("--note", default="")
        if name == "deprecate":
            p.add_argument("--replaced-by")
    a = ap.parse_args(argv)
    events = load_events()
    state = replay(events)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if a.cmd == "scan":
            found = scan()
            counts: dict[tuple, int] = {}
            for x in found:
                counts[(x.kind, x.scope)] = counts.get((x.kind, x.scope), 0) + 1
            for (k, s), n in sorted(counts.items()):
                print(f"{k:4s} {s:7s} {n}")
            print(f"합계 {len(found)}")
        elif a.cmd == "check":
            snap = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
            errs = check(events, snap, scan())
            if not same(VIEW, render_md(state)):
                errs.append("docs/registry/README.md 가 재생 결과와 다름 — `uv run python scripts/registry.py sync --by <이름>`")
            for e in errs:
                print("✗", e)
            if errs:
                return 1
            print(f"✓ 생성물 원장 정상: 활성 {sum(r['status'] != 'deleted' for r in state.values())} · 이벤트 {len(events)}")
        elif a.cmd == "sync":
            new = plan_sync(state, scan(), by=a.by, at=now, start_seq=len(events) + 1, refs_of=refs_of, note=a.note)
            append_events(new)
            state = replay(events + new)
            write_derived(state)
            acts: dict[str, int] = {}
            for e in new:
                acts[e["action"]] = acts.get(e["action"], 0) + 1
            print(f"동기화: {acts or '변경 없음'} · 활성 {sum(r['status'] != 'deleted' for r in state.values())}")
        elif a.cmd in ("restore", "deprecate", "rename"):
            r = _find(state, a.target)
            if a.cmd == "restore" and r["status"] != "deleted":
                raise RegistryError(f"삭제 상태가 아님: {r['id']}")
            rec = {**r, "name": a.new_name} if a.cmd == "rename" else r
            e = event(a.cmd, rec, by=a.by, at=now, seq=len(events) + 1, note=a.note, replaced_by=getattr(a, "replaced_by", None))
            append_events([e])
            write_derived(replay(events + [e]))
            print(f"{a.cmd}: {r['id']}")
        elif a.cmd == "show":
            r = _find(state, a.target)
            print(json.dumps(r, ensure_ascii=False, indent=1))
            for e in events:
                if e["id"] == r["id"]:
                    print(f"  #{e['seq']} {e['at']} {e['action']:9s} {e['by']} {e.get('note', '')}")
        elif a.cmd == "usage":
            r = _find(state, a.target)
            refs = refs_of(Artifact(r["kind"], r["scope"], r["name"], r["loc"]))
            print(f"{r['id']} {r['name']} [{r['status']}] 참조 {len(refs)}곳")
            for x in refs:
                print("  ", x)
    except RegistryError as e:
        print("✗", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
