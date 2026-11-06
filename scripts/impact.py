#!/usr/bin/env python3
"""영향 조회(읽기 전용) — 바꾸려는 대상을 대장 · 원장 · 서비스 목록 · 소스에서 역참조해 5줄 보고 초안을 낸다.

  python nova.py impact <키워드> [<키워드> …]      표 이름 · 컬럼 · 화면ID · API 경로 · 권한키 · 이벤트 · 서비스 이름

조회 대상:
  docs/registry/{screens,db-dictionary,permissions,events}.md   대장 4종(ADR-004 — 코드에서 파생된 보기)
  registry/registry.json                                        생성물 원장(있으면)
  registry/entities.json                                        개념 원장(있으면 — 키 · 한국어 이름 · 표 · 별칭)
  packages/common-py/nova_common/services.json                  서비스 목록 단일 원천
  git grep -il                                                   소스 · 문서 참조(창고 원본 · 대장 자신은 뺀다)
이 도구는 후보를 모으는 것이지 판정하지 않는다 — 등급(L1~L3)은 힌트이고 판정은 사람 몫이다.
L2(추가만)와 L3(의미 변경 · 삭제)의 구분은 '무엇을 할 것인가'의 문제라 도구가 알 수 없다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT  # noqa: E402

LEDGERS = {
    "screens": ("화면", "docs/registry/screens.md"),
    "db": ("DB", "docs/registry/db-dictionary.md"),
    "permissions": ("권한", "docs/registry/permissions.md"),
    "events": ("이벤트", "docs/registry/events.md"),
}
# 대장마다 바뀌면 함께 갱신할 원천(대장 자체는 생성물이라 원천을 고치고 ledgers.py 를 돌린다)
UPDATES = {
    "screens": "화면 머리 주석(@screen · @status)",
    "db": "DB 모델(mapped_column comment=) · 마이그레이션",
    "permissions": "services/gateway/gateway/rbac.json",
    "events": "infra/k3s/base/kafka-topics.txt · 이벤트 페이로드",
    "registry": "생성물 원장(registry.py sync)",
    "entities": "개념 원장(naming entity · alias · retire — 이름을 바꾸면 Expand → Migrate → Contract)",
    "services": "services.json → python nova.py gen",
}
SKIP_PREFIX = ("docs/warehouse/", "docs/registry/", "registry/")
MAX_ROWS = 8


def _rows(text: str, kws: list[str]) -> list[str]:
    """표 본문 줄(머리 · 구분선 제외) 중 키워드가 하나라도 들어 있는 줄."""
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith("|") or set(s) <= set("|-: "):
            continue
        low = s.lower()
        if any(k in low for k in kws):
            out.append(s)
    return out


def _git_files(kws: list[str], root: Path) -> tuple[list[str], str]:
    """(파일 목록, 비고). git 저장소가 아니거나 git 이 없으면 비고에 이유를 남기고 빈 목록."""
    args = ["git", "-c", "core.quotepath=false", "grep", "-il"]
    for k in kws:
        args += ["-e", k]
    try:
        r = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return [], "git 이 없어 소스 조회를 하지 못했다"
    if r.returncode == 1:  # 일치 없음
        return [], ""
    if r.returncode != 0:
        return [], f"소스 조회 실패: {(r.stderr or '').strip()[:80]}"
    files = [f for f in r.stdout.splitlines() if f and not f.startswith(SKIP_PREFIX)]
    return files, ""


def analyze(keywords: list[str], root: Path = ROOT) -> dict:
    kws = [k.lower() for k in keywords if k.strip()]
    if not kws:
        raise SystemExit("✗ 키워드를 하나 이상 준다 — python nova.py impact <키워드> …")
    res: dict = {"keywords": keywords, "ledgers": {}, "registry": [], "entities": [], "services": [], "files": [], "note": ""}
    for key, (_, rel) in LEDGERS.items():
        p = root / rel
        res["ledgers"][key] = _rows(p.read_text(encoding="utf-8"), kws) if p.exists() else None
    rp = root / "registry" / "registry.json"
    if rp.exists():
        reg = json.loads(rp.read_text(encoding="utf-8"))
        for rid, e in reg.items():
            if not isinstance(e, dict) or e.get("status") == "deleted":
                continue
            hay = f"{rid} {e.get('name', '')} {e.get('loc', '')}".lower()
            if any(k in hay for k in kws):
                res["registry"].append(f"{rid} {e.get('kind', '')} {e.get('name', '')} ({e.get('loc', '')})")
    ep = root / "registry" / "entities.json"
    if ep.exists():
        for key, e in (json.loads(ep.read_text(encoding="utf-8")).get("entities") or {}).items():
            hay = " ".join([key, e.get("title_ko", ""), e.get("table") or "", *e.get("lookup_aliases", []), *e.get("forbidden_aliases", [])]).lower()
            if any(k in hay for k in kws):
                res["entities"].append(f"{key} [{e.get('status', '?')} · {e.get('layer', '?')}] {e.get('title_ko', '')} — 표 {e.get('service') or '-'}.{e.get('table') or '-'}")
    sp = root / "packages" / "common-py" / "nova_common" / "services.json"
    if sp.exists():
        for s in json.loads(sp.read_text(encoding="utf-8")).get("services", []):
            hay = f"{s.get('name', '')} {s.get('title', '')} {' '.join(s.get('routes', []))}".lower()
            if any(k in hay for k in kws):
                res["services"].append(s.get("name", "?"))
    res["files"], res["note"] = _git_files(kws, root)
    return res


def grade_hint(res: dict) -> tuple[str, str]:
    kinds = [k for k, rows in res["ledgers"].items() if rows]
    direct = len(kinds) + (1 if res["registry"] else 0) + (1 if res.get("entities") else 0) + (1 if res["services"] else 0)
    n = len(res["files"])
    if direct == 0 and n == 0:
        return "L1", "대장 · 원장 · 소스 어디에도 걸리지 않는다 — 로컬 변경으로 보인다"
    if len(kinds) >= 2 or res["services"] or n > 10:
        return "L2~L3", "참조가 넓다(대장 여러 종 · 서비스 · 소스 10개 넘음) — 추가(Expand)만이면 L2, 의미 변경 · 삭제면 L3(ADR + Expand→Migrate→Contract)"
    return "L1~L2", "참조가 좁다 — 계약(API · 표 · 이벤트)을 건드리면 L2 로 올려 잡는다"


def report(res: dict) -> list[str]:
    out = [f"■ 영향 조회: {' · '.join(res['keywords'])}", ""]
    for key, (label, rel) in LEDGERS.items():
        rows = res["ledgers"][key]
        if rows is None:
            out.append(f"  [{label}] {rel} 없음")
            continue
        out.append(f"  [{label}] {len(rows)}줄")
        out += [f"    {r[:140]}" for r in rows[:MAX_ROWS]]
        if len(rows) > MAX_ROWS:
            out.append(f"    … 외 {len(rows) - MAX_ROWS}줄")
    out.append(f"  [원장] {len(res['registry'])}건")
    out += [f"    {r[:140]}" for r in res["registry"][:MAX_ROWS]]
    out.append(f"  [개념 원장] {len(res.get('entities', []))}건")
    out += [f"    {r[:140]}" for r in res.get("entities", [])[:MAX_ROWS]]
    out.append(f"  [서비스] {', '.join(res['services']) or '없음'}")
    out.append(f"  [소스 · 문서] {len(res['files'])}파일" + (f" — {res['note']}" if res["note"] else ""))
    out += [f"    {f}" for f in res["files"][:20]]
    if len(res["files"]) > 20:
        out.append(f"    … 외 {len(res['files']) - 20}파일")

    direct = []
    for key, (label, _) in LEDGERS.items():
        if res["ledgers"][key]:
            direct.append(f"{label} {len(res['ledgers'][key])}")
    if res["registry"]:
        direct.append(f"원장 {len(res['registry'])}")
    if res.get("entities"):
        direct.append(f"개념 {len(res['entities'])}")
    if res["services"]:
        direct.append(f"서비스 {', '.join(res['services'])}")
    grade, why = grade_hint(res)
    upd = [UPDATES[k] for k, rows in res["ledgers"].items() if rows]
    if res["registry"]:
        upd.append(UPDATES["registry"])
    if res.get("entities"):
        upd.append(UPDATES["entities"])
    if res["services"]:
        upd.append(UPDATES["services"])
    upd += ["대장 다시 만들기(ledgers.py)"] if any(res["ledgers"].values()) else []
    upd.append("요구 · 계획(plan_REQ_NN §0 영향분석)")
    out += ["", "── 5줄 보고 초안(계획 §0 · issue --impact 에 옮긴다) ──",
            f"  1) 대상: {' · '.join(res['keywords'])}",
            f"  2) 직접 영향: {' · '.join(direct) or '(대장 · 원장 · 서비스에 없음)'}",
            f"  3) 간접 영향: 소스 · 문서 {len(res['files'])}파일" + (f"({res['note']})" if res["note"] else ""),
            f"  4) 등급 힌트: {grade} — {why}",
            f"  5) 갱신할 산출물: {' · '.join(upd)}",
            "",
            "⚠ 등급은 힌트다 — 판정은 사람 몫이다. L3(의미 변경 · 삭제)면 ADR 과 Expand→Migrate→Contract 계획이 먼저다."]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keywords", nargs="+", help="표 · 컬럼 · 화면ID · API 경로 · 권한키 · 이벤트 · 서비스 이름")
    a = ap.parse_args(argv)
    print("\n".join(report(analyze(a.keywords, ROOT))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
