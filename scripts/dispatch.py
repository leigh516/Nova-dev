#!/usr/bin/env python3
"""회차 분할안 — 마스터플랜 '병렬 묶음' 표와 묶음 담당 REQ 상태로 파도(선행 묶음이 끝나야 시작)를 나눈다.

  uv run python scripts/dispatch.py plan [--write] [--date YYYY-MM-DD] [--force]
      화면에 분할안. --write 면 docs/plans/drafts/dispatch_<날짜>.md 초안(본 작업 트리만 — 단일 기록자)
  uv run python scripts/dispatch.py next [--from <초안>]
      사람이 고친 초안을 읽어 지금 열 파도의 worktree-new 명령을 안내만 한다(직접 만들지 않는다)

파도는 표의 '선행 묶음' 칸(선택 — 묶음 이름, 여럿이면 쉼표 · 없으면 -)에서 나온다.
담당 REQ 가 모두 완료 · 적용됨(또는 보류 · 취소)인 묶음은 '끝남' — 파도에서 빠지고, 그 묶음을 기다리는 묶음도 기다리지 않는다.
게이트(공통 영역 완료 · 묶음 2개 이상 · 경로 겹침)는 scripts/parallel.py 의 gate 가 정본이다 — 여기서 다시 판정하지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parallel  # noqa: E402
import progress  # noqa: E402
from novalib import main_root, require_main, write  # noqa: E402

# 요구가 끝났는지는 progress.is_finished 하나로 판정한다(완료(…) · 적용됨(…) · 보류 · 취소 — REQ-261106-02-1)
REQ = re.compile(r"REQ-\d{6}-\d{2}")
DEP_COL = "선행 묶음"


def names(cell: str) -> list[str]:
    return [x.strip().strip("`") for x in re.split(r"[,·]", cell or "") if x.strip().strip("`") not in ("", "-")]


def req_status(root: Path) -> dict[str, str]:
    out = {}
    for r in progress.rows(progress.read(root / "docs" / "requirement" / "requirement_index.md")):
        m = REQ.search(r[0]) if r else None
        if m and len(r) >= 4:
            out[m.group(0)] = r[3]
    return out


def waves_of(deps: dict[str, list[str]]) -> tuple[list[list[str]], list[str]]:
    """위상 정렬을 층으로 — (파도들, 순환에 걸린 묶음). 같은 층은 표 순서를 지킨다."""
    left, done, waves = dict(deps), set(), []
    while left:
        layer = [b for b, ds in left.items() if all(d in done for d in ds)]
        if not layer:
            return waves, list(left)
        waves.append(layer)
        done |= set(layer)
        for b in layer:
            left.pop(b)
    return waves, []


def plan(root: Path) -> dict:
    mp = parallel.plan_path(root)
    gate_why, rows = parallel.gate(mp)
    status = req_status(root)
    errors, bundles = [], {}
    for r in rows:
        b = r.get("묶음", "")
        reqs = REQ.findall(r.get("담당 REQ", ""))
        bundles[b] = {"path": r.get("경로", ""), "reqs": {q: status.get(q, "인덱스에 없음") for q in reqs},
                      "deps": names(r.get(DEP_COL, ""))}
    for b, v in bundles.items():
        for d in v["deps"]:
            if d not in bundles:
                errors.append(f"묶음 '{b}' 의 선행 묶음 '{d}' 가 표에 없다 — {mp.name} '## 병렬 묶음' 표를 고친다")
    finished = [b for b, v in bundles.items() if v["reqs"] and all(progress.is_finished(s) for s in v["reqs"].values())]
    live = {b: [d for d in v["deps"] if d in bundles and d not in finished] for b, v in bundles.items() if b not in finished}
    waves, cycle = waves_of(live)
    if cycle:
        errors.append(f"선행 묶음 순환: {' ⇄ '.join(cycle)} — 순서를 지어내지 않는다(표를 고친다)")
    return {"gate": gate_why, "errors": errors, "bundles": bundles, "finished": finished, "waves": waves}


def render(p: dict, date: str) -> str:
    wave_of = {b: i + 1 for i, w in enumerate(p["waves"]) for b in w}
    lines = [f"# 회차 분할안 초안 — {date}", "",
             "> `uv run python scripts/dispatch.py plan --write` 가 만든 **초안**이다(정본은 마스터플랜 '## 병렬 묶음' 표).",
             "> 사람이 '파도' 칸을 고치고 행을 지워 이번 회차에서 뺄 수 있다. '경로' 는 고치지 않는다(겹침은 마스터플랜에서 고친다).",
             "> 열기는 `uv run python scripts/dispatch.py next` 가 안내하는 명령으로 — 파도 하나씩, 앞 파도의 담당 REQ 가 끝난 뒤.", "",
             "## 게이트", ""]
    lines += [f"- ✗ {w}" for w in p["gate"]] or ["- ✓ 병렬 게이트 열림(`python nova.py parallel-gate`)"]
    lines += [f"- ✗ {e}" for e in p["errors"]]
    lines += ["", "## 분할안", "", "| 파도 | 묶음 | 경로 | 담당 REQ | REQ 상태 | 선행 묶음 | 여는 명령 |", "|---|---|---|---|---|---|---|"]
    for b, v in p["bundles"].items():
        if b in p["finished"]:
            continue
        reqs = ", ".join(v["reqs"]) or "-"
        st = ", ".join(f"{q} {s}" for q, s in v["reqs"].items()) or "-"
        lines.append(f"| {wave_of.get(b, '?')} | {b} | {v['path']} | {reqs} | {st} | {', '.join(v['deps']) or '-'} | "
                     f"`python nova.py worktree-new {b}` |")
    lines += ["", "## 끝난 묶음", ""]
    lines += [f"- {b} — {', '.join(p['bundles'][b]['reqs'])}" for b in p["finished"]] or ["- 없음"]
    return "\n".join(lines) + "\n"


def write_draft(root: Path, *, date: str | None = None, force: bool = False) -> Path:
    require_main("회차 분할안 초안", root)
    date = date or dt.date.today().isoformat()
    path = root / "docs" / "plans" / "drafts" / f"dispatch_{date}.md"
    if path.exists() and not force:
        raise SystemExit(f"✗ 이미 있다: {path} — 사람이 고친 초안을 덮지 않는다(새로 만들려면 --force)")
    write(path, render(plan(root), date))
    return path


def latest_draft(root: Path) -> Path:
    found = sorted((root / "docs" / "plans" / "drafts").glob("dispatch_*.md"))
    if not found:
        raise SystemExit("✗ 분할안 초안이 없다 — 먼저 uv run python scripts/dispatch.py plan --write")
    return found[-1]


def next_step(root: Path, draft: Path | None = None) -> dict:
    """초안의 파도 칸을 읽어 '앞 파도가 모두 끝난' 가장 이른 파도의 묶음을 고른다. 안내만 — worktree 를 만들지 않는다."""
    draft = draft or latest_draft(root)
    rows = parallel.table(draft.read_text(encoding="utf-8"), "분할안")
    p = plan(root)
    status = req_status(root)
    by_wave: dict[int, list[str]] = {}
    for r in rows:
        w = r.get("파도", "").strip()
        if w.isdigit():
            by_wave.setdefault(int(w), []).append(r.get("묶음", ""))

    def finished(b: str) -> bool:
        reqs = REQ.findall(next((r.get("담당 REQ", "") for r in rows if r.get("묶음") == b), ""))
        return bool(reqs) and all(progress.is_finished(status.get(q, "")) for q in reqs)

    out = {"draft": draft, "gate": p["gate"] + p["errors"], "wave": None, "open": [], "commands": [], "waiting": []}
    for w in sorted(by_wave):
        todo = [b for b in by_wave[w] if not finished(b)]
        if not todo:
            continue
        out["wave"] = w
        out["open"] = [b for b in todo if (root / ".worktrees" / f"wt-{b}").exists()]
        if not out["gate"]:
            out["commands"] = [f"python nova.py worktree-new {b}" for b in todo if b not in out["open"]]
        out["waiting"] = [b for k in sorted(by_wave) if k > w for b in by_wave[k]]
        break
    return out


def show(p: dict) -> None:
    for w in p["gate"]:
        print(f"✗ 게이트: {w}")
    for e in p["errors"]:
        print(f"✗ {e}")
    for i, w in enumerate(p["waves"], 1):
        print(f"■ 파도 {i}: {', '.join(w)}")
    if p["finished"]:
        print(f"  끝난 묶음(파도에서 뺌): {', '.join(p['finished'])}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--write", action="store_true")
    pl.add_argument("--date")
    pl.add_argument("--force", action="store_true")
    nx = sub.add_parser("next")
    nx.add_argument("--from", dest="src")
    a = ap.parse_args(argv)
    root = main_root()
    if a.cmd == "plan":
        p = plan(root)
        show(p)
        if a.write:
            print(f"✓ 초안: {write_draft(root, date=a.date, force=a.force)} — 사람이 파도 칸을 고친 뒤 dispatch.py next")
        return 1 if p["errors"] else 0
    n = next_step(root, Path(a.src) if a.src else None)
    print(f"■ 초안: {n['draft']}")
    for w in n["gate"]:
        print(f"✗ {w}")
    if n["wave"] is None:
        print("✓ 열 파도가 없다 — 초안의 묶음이 모두 끝났다")
        return 0
    print(f"■ 파도 {n['wave']}" + (f" · 이미 열림: {', '.join(n['open'])}" if n["open"] else ""))
    for c in n["commands"]:
        print(f"  {c}")
    if n["gate"]:
        print("  (게이트 · 표 오류가 있어 명령을 안내하지 않는다 — 직렬로 간다)")
        return 1
    if n["waiting"]:
        print(f"  다음 파도(앞 파도의 담당 REQ 가 끝난 뒤): {', '.join(n['waiting'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
