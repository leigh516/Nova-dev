#!/usr/bin/env python3
"""worktree 세션 인수인계 · main 의 읽기 전용 관측(ADR-008 — 병렬 묶음 · 메시지 버스 · 단일 기록자).

  uv run python scripts/handoff.py status        (worktree 안) main 대비 뒤처짐 · 받은함 미처리 수 · HANDOFF.md 유무 · 미커밋 수
  uv run python scripts/handoff.py close-check   (worktree 안) 마감을 막는 조건 — 받은함 미처리 · HANDOFF.md 없음 → 종료 1
  uv run python scripts/handoff.py observe [--json]   (main 에서만) 모든 wt-* worktree 를 읽기 전용으로 관측

observe 는 조회 git 명령만 쓴다(worktree list · rev-list · diff --name-only · status --porcelain).
fetch · merge · checkout · add · commit · reset 은 이 파일에 없다 — 관측이 worktree 에 흔적을 남기면 안 된다.
묶음 · 경로 판정은 scripts/parallel.py(table · globs · in_bundle)가 정본이다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collab  # noqa: E402
import parallel  # noqa: E402
from novalib import current_branch, git, in_linked_worktree, main_root  # noqa: E402

HANDOFF = parallel.HANDOFF


def unread(branch: str, cwd: Path) -> list[dict]:
    """이 브랜치 앞으로 온, 아직 결과가 붙지 않은 메시지(내가 보낸 것은 빼고)."""
    return [m for m in collab.messages(cwd) if not collab.done_for(m, branch) and collab.for_me(m, branch) and m.get("from") != branch]


def dirty_paths(cwd: Path) -> list[str]:
    out = []
    for ln in git("status", "--porcelain", "-uall", cwd=cwd).splitlines():
        p = ln[3:].strip()
        out += [x.strip().strip('"') for x in p.split(" -> ")]   # 이름 바꾸기는 옛 · 새 경로 둘 다(옛 경로가 묶음 밖일 수 있다)
    return out


def status(*, cwd: Path | None = None) -> dict:
    cwd = Path(cwd or Path.cwd())
    if not in_linked_worktree(cwd):
        raise SystemExit("✗ handoff 는 worktree 안에서 쓴다 — 본 작업 트리는 /session-start · /session-end")
    me = current_branch(cwd)
    main_b = current_branch(main_root(cwd))
    return {"branch": me, "main": main_b,
            "behind": int(git("rev-list", "--count", f"HEAD..{main_b}", cwd=cwd)),
            "inbox": len(unread(me, cwd)), "handoff": (cwd / HANDOFF).exists(), "dirty": len(dirty_paths(cwd))}


def close_check(*, cwd: Path | None = None) -> list[str]:
    """마감을 막는 이유 — 비면 마감해도 된다. 미커밋은 막지 않는다(마감 절차가 이어서 커밋한다)."""
    cwd = Path(cwd or Path.cwd())
    s = status(cwd=cwd)
    why = []
    ms = unread(s["branch"], cwd)
    if ms:
        why.append(f"받은함에 처리 전 메시지 {len(ms)}건 — /inbox 로 처리하고 python nova.py done <ID> --result … "
                   f"({', '.join(m['id'][-8:] for m in ms)})")
    if not s["handoff"]:
        why.append(f"브랜치 루트에 {HANDOFF} 가 없다 — 한 일 · 검증 숫자 · 남은 것 · 보낸 것의 결과 대기를 적는다")
    return why


def worktrees(root: Path) -> list[tuple[Path, str]]:
    out, path = [], None
    for ln in git("worktree", "list", "--porcelain", cwd=root).splitlines():
        if ln.startswith("worktree "):
            path = Path(ln.split(" ", 1)[1])
        elif ln.startswith("branch refs/heads/") and path is not None:
            out.append((path, ln.split("refs/heads/", 1)[1]))
    return [(p, b) for p, b in out if b.startswith("wt-")]


def row_line(plan: Path, bundle: str) -> str:
    rel = "docs/plans/master_plan.md"
    if plan.exists():
        for n, ln in enumerate(plan.read_text(encoding="utf-8").splitlines(), 1):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if ln.lstrip().startswith("|") and cells and cells[0] == bundle:
                return f"{rel}:{n}"
    return rel


def observe(root: Path) -> list[dict]:
    if in_linked_worktree(root):
        raise SystemExit("✗ observe 는 본 작업 트리(main)에서만 쓴다 — 관측은 다른 브랜치를 들여다보는 일이다")
    main_b = current_branch(root)
    plan = parallel.plan_path(root)
    _, bundles = parallel.gate(plan)
    out = []
    for path, branch in worktrees(root):
        name = branch[3:]
        b = next((x for x in bundles if x.get("묶음") == name), None)
        committed = [f for f in git("diff", "--name-only", "--no-renames", f"{main_b}...{branch}", cwd=root).splitlines() if f]   # 옛 경로도(parallel.converge 와 같은 판정)
        dirty = dirty_paths(path) if path.exists() else []
        cell = b.get("경로", "") if b else ""
        outside = sorted({f for f in committed + dirty if f != HANDOFF and not (b and parallel.in_bundle(f, cell))})
        o = {"branch": branch, "bundle": name if b else None, "path": str(path), "row": row_line(plan, name),
             "behind": int(git("rev-list", "--count", f"{branch}..{main_b}", cwd=root)),
             "ahead": int(git("rev-list", "--count", f"{main_b}..{branch}", cwd=root)),
             "dirty": len(dirty), "handoff": (path / HANDOFF).exists(), "inbox": len(unread(branch, root)),
             "outside": outside, "problems": []}
        if not b:
            o["problems"].append(f"심각 · 묶음 '{name}' 이 병렬 묶음 표에 없다({o['row']}) — 경로를 모르면 병합 범위를 잴 수 없다")
        elif outside:
            o["problems"].append(f"심각 · 묶음 경로 밖 변경 {len(outside)}개(허용 경로: {o['row']}): " + ", ".join(outside[:10]))
        if o["behind"]:
            o["problems"].append(f"주의 · main 보다 {o['behind']}커밋 뒤처짐 — /worktree-sync 안내")
        if o["inbox"]:
            o["problems"].append(f"주의 · 받은함 미처리 {o['inbox']}건 — 확인 요청(처리 중일 수 있다)")
        out.append(o)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("close-check")
    ob = sub.add_parser("observe")
    ob.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        s = status()
        print(f"■ {s['branch']} — {s['main']} 대비 뒤처짐 {s['behind']}커밋 · 받은함 미처리 {s['inbox']}건 · "
              f"{HANDOFF} {'있음' if s['handoff'] else '없음'} · 미커밋 {s['dirty']}개")
        if s["behind"]:
            print("  → 뒤처졌다: /worktree-sync")
        return 0
    if a.cmd == "close-check":
        why = close_check()
        if why:
            print("✗ 아직 마감하지 않는다:")
            for w in why:
                print("  " + w)
            return 1
        print("✓ 마감해도 된다 — 커밋 → python nova.py send --to main --type report …")
        return 0
    obs = observe(main_root())
    if a.json:
        print(json.dumps(obs, ensure_ascii=False, indent=2))
        return 0
    if not obs:
        print("✓ 관측 대상 없음 — 열린 wt-* worktree 가 없다(평시 직렬 진행이면 정상)")
        return 0
    for o in obs:
        print(f"■ {o['branch']} · 앞섬 {o['ahead']} · 뒤처짐 {o['behind']} · 미커밋 {o['dirty']} · "
              f"{HANDOFF} {'있음' if o['handoff'] else '없음'} · 받은함 {o['inbox']}")
        for p in o["problems"]:
            print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
