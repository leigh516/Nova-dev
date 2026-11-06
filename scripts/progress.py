#!/usr/bin/env python3
"""진척 보기(읽기 전용) — 진척을 한 축으로 답하지 않는다. 세 수를 따로 낸다(평균 내지 않는다).

  python nova.py progress            ① 계획 · task  ② 요구 상태 ↔ task  ③ 릴리스 초안
  python nova.py progress --check    ② 의 모순(완료인데 미완 task · 그 반대)이 있으면 종료 1 — 정보용(lint 에 넣지 않는다)
  python nova.py progress --json     기계용

① 마스터플랜 '## 5. 세부 계획' ↔ docs/plans/plan_index.md ↔ docs/plans/tasks/*.md 의 `- [ ]` · `- [x]` 수
② docs/requirement/requirement_index.md 상태가 완료 · 적용됨인데 연결 task 가 미완인 것, 그 반대(task 는 모두 끝났는데 요구가 열림)
③ docs/releases/releases.json 초안(draft) 판본의 묶인 요구 상태 · 종료 조건 형식(goals.lint)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goals  # noqa: E402
from novalib import ROOT  # noqa: E402

DONE = ("완료", "적용됨")       # 상태 칸의 머리말 — 꼬리 '(…)' 는 설명이다(완료(종료 조건 충족 …) · 적용됨(상시 규칙))
CLOSED = ("보류", "취소")


def _head(status: str, heads: tuple[str, ...]) -> bool:
    """머리말이 heads 중 하나이고 뒤가 비었거나 괄호 꼬리 '(…)' 뿐이면 참(REQ-261106-02-1).
    '적용됨 · E3 확인 대기' · '구현 완료(…)' 처럼 다른 말이 붙으면 아직 끝나지 않은 것으로 본다 — 확인 대기를 끝남으로 세지 않게."""
    m = re.fullmatch(r"(\S+?)\s*(\(.*\))?", status.strip())
    return bool(m) and m.group(1) in heads


def is_done(status: str) -> bool:
    """요구 상태가 완료 · 적용됨인가 — release ship · progress · dispatch 가 같은 판정을 쓴다."""
    return _head(status, DONE)


def is_finished(status: str) -> bool:
    """끝남(완료 · 적용됨) 또는 닫힘(보류 · 취소)."""
    return _head(status, DONE + CLOSED)
PLAN = re.compile(r"plan_REQ_\d+")
BOX = re.compile(r"^\s*- \[([ xX])\]\s*(.*)$")


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def rows(text: str) -> list[list[str]]:
    """마크다운 표의 본문 행(머리 · 구분줄 제외)."""
    out, seen_sep = [], False
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            continue
        if re.fullmatch(r"\|[-| :]+\|", s):
            seen_sep = True
            continue
        if seen_sep:
            out.append([c.strip() for c in s.strip("|").split("|")])
    return out


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def count_tasks(p: Path) -> dict:
    """task 문서의 체크 수 — 전체와 단계별('## N단계' 머리 아래). 취소(~~)는 미완으로 세지 않는다."""
    tot = {"done": 0, "open": 0, "cancelled": 0}
    stages: dict[str, dict] = {}
    cur = ""
    for ln in read(p).splitlines():
        h = re.match(r"^##\s*(\d+)단계", ln)
        if ln.startswith("## "):
            cur = h.group(1) if h else ""
        m = BOX.match(ln)
        if not m:
            continue
        k = "cancelled" if m.group(2).lstrip().startswith("~~") else ("open" if m.group(1) == " " else "done")
        tot[k] += 1
        if cur:
            stages.setdefault(cur, {"done": 0, "open": 0, "cancelled": 0})[k] += 1
    return {**tot, "stages": stages}


def plans(root: Path) -> dict:
    pl = root / "docs" / "plans"
    master = list(dict.fromkeys(PLAN.findall(section(read(pl / "master_plan.md"), "5. 세부 계획"))))
    index = list(dict.fromkeys(m for r in rows(read(pl / "plan_index.md")) for m in PLAN.findall(r[0]) if r))
    task_files = sorted(p.stem.replace("tasks_", "plan_") for p in (pl / "tasks").glob("tasks_REQ_*.md"))
    tasks = [{"plan": n, **count_tasks(pl / "tasks" / f"{n.replace('plan_', 'tasks_')}.md")} for n in task_files]
    return {"master": master, "index": index,
            "master_only": [n for n in master if n not in index], "index_only": [n for n in index if n not in master],
            "no_tasks": [n for n in dict.fromkeys(master + index) if n not in task_files],
            "tasks": tasks,
            "total": {k: sum(t[k] for t in tasks) for k in ("done", "open", "cancelled")}}


def reqs(root: Path, task_map: dict[str, dict]) -> dict:
    out, conflicts = [], []
    for r in rows(read(root / "docs" / "requirement" / "requirement_index.md")):
        if len(r) < 5:
            continue
        m = re.search(r"\[(REQ-[\d-]+)\]", r[0])
        if not m:
            continue
        rid, status = m.group(1), r[3]
        linked = list(dict.fromkeys(PLAN.findall(r[4])))
        stage = re.search(r"(\d+)단계", r[4])           # '[plan_REQ_01](…) 9단계' — 그 단계 task 만 이 요구의 것
        t = [(task_map[p]["stages"].get(stage.group(1), {"done": 0, "open": 0}) if stage else task_map[p])
             for p in linked if p in task_map]
        open_ = sum(x["open"] for x in t)
        done = sum(x["done"] for x in t)
        out.append({"req": rid, "status": status, "plans": linked, "open": open_, "done": done})
        if is_done(status) and open_:
            conflicts.append({"req": rid, "status": status, "kind": "완료인데 미완 task", "open": open_, "plans": linked})
        elif not is_finished(status) and t and not open_ and done:
            conflicts.append({"req": rid, "status": status, "kind": "task 는 모두 끝났는데 요구가 열려 있다", "open": 0, "plans": linked})
    return {"reqs": out, "conflicts": conflicts}


def releases(root: Path, req_rows: list[dict]) -> dict:
    p = root / "docs" / "releases" / "releases.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"releases": []}
    status = {r["req"]: r["status"] for r in req_rows}
    drafts = [{"version": r.get("version", "?"), "goal": r.get("goal", ""),
               "reqs": {q: status.get(q, "없음") for q in r.get("reqs", [])},
               "exit": len(r.get("exit", [])), "errors": goals.lint(r.get("exit", []), f"v{r.get('version', '?')}")}
              for r in data.get("releases", []) if r.get("status") == "draft"]
    return {"drafts": drafts, "shipped": [r.get("version") for r in data.get("releases", []) if r.get("status") == "shipped"]}


def collect(root: Path = ROOT) -> dict:
    pl = plans(root)
    rq = reqs(root, {t["plan"]: t for t in pl["tasks"]})
    return {"plans": pl, "reqs": rq, "releases": releases(root, rq["reqs"])}


def show(d: dict) -> None:
    p = d["plans"]
    t = p["total"]
    print(f"① 계획 · task — 마스터플랜 {len(p['master'])} · 계획 인덱스 {len(p['index'])} · task 문서 {len(p['tasks'])}"
          f" | task 끝 {t['done']} · 남음 {t['open']} · 취소 {t['cancelled']}")
    for r in p["tasks"]:
        print(f"   {r['plan']}: 끝 {r['done']} · 남음 {r['open']}" + (f" · 취소 {r['cancelled']}" if r["cancelled"] else ""))
    for key, msg in (("master_only", "마스터플랜에만 있다(plan_index 에 없음)"), ("index_only", "plan_index 에만 있다(마스터플랜 §5 에 없음)"),
                     ("no_tasks", "task 문서가 없다")):
        if p[key]:
            print(f"   ⚠ {msg}: {', '.join(p[key])}")
    rq = d["reqs"]
    print(f"② 요구 ↔ task — 요구 {len(rq['reqs'])}건 · 모순 {len(rq['conflicts'])}건")
    for c in rq["conflicts"]:
        print(f"   ✗ {c['req']} '{c['status']}' — {c['kind']}" + (f"(남음 {c['open']})" if c["open"] else "") + f" · {', '.join(c['plans'])}")
    rl = d["releases"]
    print(f"③ 릴리스 — 낸 판본 {len(rl['shipped'])} · 초안 {len(rl['drafts'])}")
    for r in rl["drafts"]:
        left = [q for q, s in r["reqs"].items() if not is_done(s)]
        print(f"   v{r['version']} 초안 · 묶인 요구 {len(r['reqs'])}(미완 {len(left)}) · 종료 조건 {r['exit']}개 · 형식 오류 {len(r['errors'])}")
        for q in left:
            print(f"     · {q}: {r['reqs'][q]}")
        for e in r["errors"]:
            print(f"     ✗ {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="② 모순이 있으면 종료 1")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    d = collect(Path(a.root))
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        show(d)
    return 1 if a.check and d["reqs"]["conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
