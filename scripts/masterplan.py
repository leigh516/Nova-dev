#!/usr/bin/env python3
"""마스터플랜 판본 — 초안 → 채택을 도구가 한 번에 하고, 지난 판본은 봉인해 바뀌지 않게 지킨다(ADR-008).

  python nova.py masterplan status                                     지금 정본 · 이력 · 초안
  python nova.py masterplan adopt drafts/master_plan_v1.2-draft.md --why "REQ-…" --what "<바뀐 것>"
      지금 정본을 archive/master_plan_v<지금>.md 로 봉인 → 초안을 정본으로(상태 정식 · 채택일) → 이력 한 줄 → 초안 삭제
  python nova.py masterplan seal                                       봉인이 없는 보관본을 봉인(처음 한 번)
  python nova.py masterplan check                                      lint — 정본 하나 · 판본 번호 = 이력 · 보관본 봉인 그대로

참조: project-start-guide-05 ADR-0065 · 0066(정본 지정 · 복사-봉인 · 봉인 불변 검사)을 Nova 크기로 줄였다.
봉인: docs/plans/archive/seals.json(보관본 sha256 — 상태 JSON, ADR-004). 첫 판본은 영구히 그대로 둔다("처음 무엇을 하려 했나"에 언제든 답한다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, require_main, write  # noqa: E402

VER = re.compile(r"^\|\s*버전\s*\|\s*\*\*v(\d+\.\d+)\*\*", re.M)
# 병렬(worktree) 전에 반드시 끝나야 하는 공통 영역 — 이 줄이 표에서 빠지면 병렬 게이트가 그 영역을 보지 못한다.
# 특히 화면 공통 모듈: 이것이 끝나기 전에 갈라지면 worktree 마다 서로 다른 화면 구성 · 부품이 생겨 통일성이 깨진다.
# (이름, 항목 칸에 들어 있어야 할 낱말 — 하나라도)
REQUIRED_COMMON = (
    ("CI(test · lint)", ("CI",)),
    ("인증 · 권한", ("인증",)),
    ("DB · 마이그레이션", ("DB",)),
    ("서비스 사이 계약(API · 이벤트)", ("계약",)),
    ("화면 공통 모듈(화면 틀 · 공통 UI 부품 · 템플릿 · 디자인 토큰)", ("화면",)),
    ("공통 컴포넌트(라이브러리 — nova_common · @nova/sdk · kr.nova.shared)", ("공통 컴포넌트", "공통 라이브러리")),
    ("공통 명명 규약 · 개념 원장", ("명명",)),
)
COMMON_HEADING = "공통 영역 완료 선언"


def common_errors(text: str, where: str) -> list[str]:
    """'공통 영역 완료 선언' 표에 필수 항목이 다 있는지. 절이 없는 문서(옛 판본)는 검사하지 않는다."""
    m = re.search(rf"^## {COMMON_HEADING}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return []
    items = [ln.strip().strip("|").split("|")[0].strip() for ln in m.group(1).splitlines() if ln.strip().startswith("|")][2:]
    errs = []
    for name, words in REQUIRED_COMMON:
        if not any(any(w in it for w in words) for it in items):
            errs.append(f"{where}: '{COMMON_HEADING}' 표에 필수 공통 영역 '{name}' 이 없다 — 빠지면 병렬 게이트가 그 영역을 보지 않고 열린다"
                        f"(공통 모듈이 끝나기 전에 갈라지면 worktree 마다 화면 구성 · 부품 · 이름이 달라진다)")
    return errs
STATE = re.compile(r"^\|\s*상태\s*\|\s*([^|]+?)\s*\|", re.M)


def plans(root: Path = ROOT) -> Path:
    return root / "docs" / "plans"


def version_of(text: str) -> str:
    m = VER.search(text)
    return m.group(1) if m else ""


def vkey(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def seals(root: Path = ROOT) -> dict:
    p = plans(root) / "archive" / "seals.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_seals(d: dict, root: Path = ROOT) -> None:
    write(plans(root) / "archive" / "seals.json", json.dumps(dict(sorted(d.items())), ensure_ascii=False, indent=2) + "\n")


def changelog_rows(root: Path = ROOT) -> list[dict]:
    text = (plans(root) / "master_plan_changelog.md").read_text(encoding="utf-8")
    out = []
    for ln in text.splitlines():
        m = re.match(r"^\|\s*v(\d+\.\d+)\s*\|\s*\**([^|*]+?)\**\s*\|\s*([^|]*)\|", ln)
        if m:
            out.append({"version": m.group(1), "state": m.group(2).strip(), "line": ln})
    return out


EXIT_SECTION = re.compile(r"^## 종료 조건[^\n]*\n(.*?)(?=^## |\Z)", re.S | re.M)


def release_errors(root: Path = ROOT) -> list[str]:
    """마스터플랜 1 : 릴리스 N 맞물림(규약 docs/conventions/versioning.md §7).
    정본 종료 조건 절의 '이 판본(vX.Y)' = 정본 판본, '릴리스 vA.B.C' 가 원장에 있고 그 masterplan 이 정본,
    draft 판본의 masterplan 이 정본. 원장이 없거나 문장에 번호가 없으면(새 프로젝트) 검사할 것이 없다.
    오류는 'master_plan.md: ' 로 시작한다 — 채택(adopt)은 곧 바뀔 정본의 오류로 막지 않는다(채택 뒤 같은 커밋에서 맞춘다)."""
    text = (plans(root) / "master_plan.md").read_text(encoding="utf-8")
    cur = version_of(text)
    led_p = root / "docs" / "releases" / "releases.json"
    if not led_p.exists():   # 판본 원장이 없는 저장소(계획 폴더만 옮긴 곳) — 맞물릴 상대가 없다
        return []
    rels = json.loads(led_p.read_text(encoding="utf-8")).get("releases", [])
    errs, w = [], "master_plan.md: "
    m = EXIT_SECTION.search(text)
    lead = "\n".join(ln for ln in (m.group(1) if m else "").splitlines() if not ln.lstrip().startswith("|"))
    pv = re.search(r"판본\s*\(v(\d+\.\d+)\)", lead)
    if pv and pv.group(1) != cur:
        errs.append(f"{w}종료 조건 절이 '이 판본(v{pv.group(1)})' 이라 한다 — 정본은 v{cur}. 채택 뒤 문장을 맞춘다")
    rv = re.search(r"릴리스\s*v(\d+\.\d+\.\d+(?:-rc\.\d+)?)", lead)
    if rv:
        r = next((x for x in rels if x.get("version") == rv.group(1)), None)
        if r is None:
            errs.append(f"{w}종료 조건 절의 릴리스 v{rv.group(1)} 이 판본 원장(docs/releases/releases.json)에 없다 — release draft 로 연다")
        elif r.get("masterplan") and r["masterplan"] != f"v{cur}":
            errs.append(f"{w}릴리스 v{rv.group(1)} 의 masterplan 이 {r['masterplan']} — 정본 v{cur} 이 닫을 릴리스가 아니다(원장 또는 문장을 맞춘다)")
    for r in rels:
        if r.get("status") == "draft" and r.get("masterplan") and r["masterplan"] != f"v{cur}":
            errs.append(f"{w}draft 판본 v{r.get('version')} 의 masterplan 이 {r['masterplan']} — 지금 정본은 v{cur}"
                        "(정본을 채택했으면 원장 masterplan 칸을 같은 커밋에서 맞춘다)")
    if (plans(root) / "master_plan_changelog.md").exists():
        known = {f"v{x['version']}" for x in changelog_rows(root)}
        for r in rels:
            if r.get("masterplan") and r["masterplan"] not in known:
                errs.append(f"{w}판본 v{r.get('version')} 의 masterplan {r['masterplan']} 이 마스터플랜 이력에 없다")
    return errs


def check(root: Path = ROOT) -> list[str]:
    p, errs = plans(root), []
    cur = version_of((p / "master_plan.md").read_text(encoding="utf-8"))
    errs += release_errors(root)
    errs += common_errors((p / "master_plan.md").read_text(encoding="utf-8"), "master_plan.md")
    for d in sorted((p / "drafts").glob("*.md")):   # 초안은 다음 정본이다 — 채택 전에 같은 기준
        errs += common_errors(d.read_text(encoding="utf-8"), f"drafts/{d.name}")
    rows = changelog_rows(root)
    official = [r for r in rows if r["state"] == "정식"]
    st = STATE.search((p / "master_plan.md").read_text(encoding="utf-8"))
    if not official and len(rows) == 1 and rows[0]["version"] == cur and st and st.group(1).startswith("초안"):
        return errs   # 시작 판본 — new-project 직후 첫 채택(v1.0) 전에는 정식이 없는 것이 맞다
    if len(official) != 1:
        errs.append(f"이력에 '정식' 판본이 {len(official)}개 — 정본은 언제나 하나다")
    elif official[0]["version"] != cur:
        errs.append(f"정본 판본 v{cur} 과 이력의 정식 v{official[0]['version']} 이 다르다 — 채택은 masterplan adopt 로")
    if rows and rows[-1]["state"] != "정식":
        errs.append("이력의 마지막 줄이 정식 판본이 아니다")
    sealed = seals(root)
    for r in rows:
        if r["state"] == "보관":
            a = p / "archive" / f"master_plan_v{r['version']}.md"
            if not a.exists():
                errs.append(f"보관 판본 v{r['version']} 의 파일이 없다: archive/{a.name}")
            elif a.name not in sealed:
                errs.append(f"보관본 {a.name} 이 봉인되지 않았다 → python nova.py masterplan seal")
            elif sealed[a.name] != sha(a):
                errs.append(f"봉인된 보관본 {a.name} 이 바뀌었다 — 지난 판본은 고치지 않는다(바꿀 것은 새 초안으로). 되돌린다: git checkout -- docs/plans/archive/{a.name}")
    for d in sorted((p / "drafts").glob("*.md")):
        st = STATE.search(d.read_text(encoding="utf-8"))
        if st and "정식" in st.group(1):
            errs.append(f"초안 {d.name} 의 상태가 '정식' — 초안은 정본이 될 수 없다(채택은 masterplan adopt)")
    return errs


def adopt(draft: Path, why: str, what: str, root: Path = ROOT, today: dt.date | None = None) -> str:
    require_main("마스터플랜 채택", root)
    p = plans(root)
    draft = draft if draft.is_absolute() else (p / draft if not str(draft).startswith("docs") else root / draft)
    if not draft.exists() or draft.parent != p / "drafts":
        raise SystemExit(f"✗ 초안은 docs/plans/drafts/ 에 있어야 한다: {draft}")
    if not why.strip() or not what.strip():
        raise SystemExit("✗ --why(근거 — 사용자가 정한 요구 · ADR)와 --what(바뀐 것)은 비울 수 없다 — 채택 조건(README §1)")
    # 곧 교체될 정본의 공통 영역 누락은 막지 않는다 — 고치는 길이 바로 이 채택이다. 대신 새 정본(초안)은 반드시 갖춰야 한다
    errs = [e for e in check(root) if not e.startswith(("master_plan.md: ", f"drafts/{draft.name}: "))]
    errs += common_errors(draft.read_text(encoding="utf-8"), f"drafts/{draft.name}")
    if errs:
        raise SystemExit("✗ 지금 판본 상태부터 바로잡는다:\n  " + "\n  ".join(errs))
    cur_p = p / "master_plan.md"
    cur_text, new_text = cur_p.read_text(encoding="utf-8"), draft.read_text(encoding="utf-8")
    cur, new = version_of(cur_text), version_of(new_text)
    if not new or vkey(new) <= vkey(cur):
        raise SystemExit(f"✗ 초안 판본(v{new or '?'})이 지금 정본(v{cur})보다 커야 한다")
    arch = p / "archive" / f"master_plan_v{cur}.md"
    if arch.exists():
        raise SystemExit(f"✗ 봉인본 {arch.name} 이 이미 있다 — 지난 판본은 덮어쓰지 않는다")
    today = today or dt.date.today()
    # 1) 지금 정본 → 봉인(복사 · 해시)
    write(arch, STATE.sub("| 상태 | 보관(봉인) |", cur_text, count=1))   # 정식이든 시작 초안이든
    s = seals(root)
    s[arch.name] = sha(arch)
    save_seals(s, root)
    # 2) 초안 → 정본
    body = STATE.sub("| 상태 | 정식 |", new_text, count=1)
    body = re.sub(r"^\|\s*채택일\s*\|[^\n]*", f"| 채택일 | {today.isoformat()} |", body, count=1, flags=re.M)
    body = re.sub(r"^\|\s*이전 정식\s*\|[^\n]*", f"| 이전 정식 | [v{cur}](archive/{arch.name}) |", body, count=1, flags=re.M)
    write(cur_p, body)
    # 3) 이력: 지난 정식 → 보관, 새 줄
    cl = p / "master_plan_changelog.md"
    t = cl.read_text(encoding="utf-8")
    rows = changelog_rows(root)
    # 지난 정본 줄 — 정식 줄, 없으면 시작 판본(new-project 직후 v0.1 초안 — check 가 그 하나만 허용한다)
    old = next((r for r in rows if r["state"] == "정식"), None) or next(r for r in rows if r["version"] == cur)
    t = t.replace(old["line"], re.sub(r"\*\*(정식|초안)\*\*|정식|초안", "보관", old["line"], count=1).replace("[master_plan.md](master_plan.md)", f"[archive/{arch.name}](archive/{arch.name})"))
    t = t.rstrip("\n") + f"\n| v{new} | **정식** | {today.isoformat()} | {what.strip()} | {why.strip()} | [master_plan.md](master_plan.md) |\n"
    write(cl, t)
    draft.unlink()
    return new


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("check")
    sub.add_parser("seal")
    ad = sub.add_parser("adopt")
    ad.add_argument("draft")
    ad.add_argument("--why", required=True)
    ad.add_argument("--what", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        errs = check()
        for e in errs:
            print("✗", e)
        if not errs:
            print("✓ 마스터플랜 판본 정상 — 정본 하나 · 이력 일치 · 보관본 봉인 그대로")
        return 1 if errs else 0
    if a.cmd == "seal":
        s, n = seals(), 0
        for f in sorted((plans() / "archive").glob("master_plan_v*.md")):
            if f.name not in s:
                s[f.name], n = sha(f), n + 1
        save_seals(s)
        print(f"✓ 봉인 {n}개 추가 — docs/plans/archive/seals.json")
        return 0
    if a.cmd == "adopt":
        v = adopt(Path(a.draft), a.why, a.what)
        print(f"✓ v{v} 채택 — 지난 판본은 봉인 · 이력 갱신 · 초안 삭제. 다음: 커밋 · git 기록")
        return 0
    cur = version_of((plans() / "master_plan.md").read_text(encoding="utf-8"))
    print(f"■ 정본 v{cur} (docs/plans/master_plan.md)")
    for r in changelog_rows():
        print(f"  v{r['version']} · {r['state']}")
    for d in sorted((plans() / "drafts").glob("*.md")):
        print(f"  초안: {d.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
