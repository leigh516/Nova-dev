#!/usr/bin/env python3
"""병렬 개발 — 공통 영역이 끝나기 전에는 worktree 로 갈라지지 않는다(ADR-008).

  python nova.py parallel-gate               마스터플랜의 두 표를 검사(열렸나 · 왜 닫혔나)
  python nova.py worktree-new <묶음>          게이트 통과 → .worktrees/wt-<묶음> (브랜치 wt-<묶음>) + 버스로 인계 카드
  python parallel.py new --scratch <이름> [--push]  격리 작업 폴더 .worktrees/scratch-<이름>(게이트 · 묶음 표 안 봄) + 버스로 인계 카드
  python parallel.py prune [--yes]           병합됨 · 미커밋 0 · 받은함 미처리 0(전체 공지 제외) 인 .worktrees/ 정리(기본은 판정만 · 원격 브랜치는 안 지움)
  python nova.py worktree-list               worktree 와 묶음 상태
  python nova.py converge <묶음> [--verify]   main 에서 병합(--no-ff) → (--verify 면 test · lint) → 남은 worktree 에 알림
  python nova.py worktree-sync [--dry]       (worktree 안에서) main 따라잡기 — 들어올 변경을 갈라 보이고(--dry 면 여기서 멈춤) merge(rebase 금지)

converge 는 묶음 '경로' 밖 파일이 섞이면 병합하지 않는다(브랜치 루트의 HANDOFF.md 인계 메모만 허용).

게이트가 보는 것(마스터플랜 docs/plans/master_plan.md — 표 두 개, 나머지는 사람의 판단):
  ① '## 공통 영역 완료 선언' 표의 모든 행이 완료(또는 미해당)이고, 완료 행에는 증거가 있다
  ② '## 병렬 묶음' 표에 묶음이 2개 이상
  ③ 묶음끼리 경로가 겹치지 않는다(같은 파일을 두 브랜치가 고치지 않게)
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from novalib import ROOT, current_branch, git, in_linked_worktree, main_root, py, require_main  # noqa: E402

HANDOFF = "HANDOFF.md"   # 묶음 브랜치가 남기는 인계 메모(브랜치 루트) — converge 가 경로 검사에서 허용하고 내용을 보여 준다

DONE = ("완료", "미해당")
NAME = re.compile(r"^[a-z][a-z0-9-]{1,30}$")


def table(text: str, heading: str) -> list[dict]:
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return []
    rows = [ln for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    if len(rows) < 2:
        return []
    head = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    out = []
    for ln in rows[2:]:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if any(cells):
            out.append(dict(zip(head, cells)))
    return out


def globs(cell: str) -> list[str]:
    return [g.strip().strip("`") for g in re.split(r"[,·]", cell) if g.strip().strip("`")]


def prefix(g: str) -> str:
    return re.split(r"[*?\[]", g, 1)[0].rstrip("/")


def overlap(a: str, b: str) -> bool:
    pa, pb = prefix(a), prefix(b)
    return pa == pb or pa.startswith(pb + "/") or pb.startswith(pa + "/") or not pa or not pb


def glob_re(g: str) -> re.Pattern:
    """묶음 '경로' 글롭 → 정규식. `**` 는 여러 단계, `*` 는 한 단계. 와일드카드가 없으면 그 폴더 · 파일 아래 전부."""
    g = g.strip().rstrip("/")
    if not re.search(r"[*?\[]", g):
        return re.compile(re.escape(g) + r"(/.*)?$")
    out, i = "", 0
    while i < len(g):
        if g.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif g.startswith("**", i):
            out, i = out + ".*", i + 2
        elif g[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif g[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(g[i]), i + 1
    return re.compile(out + "$")


def in_bundle(path: str, cell: str) -> bool:
    return any(glob_re(g).match(path) for g in globs(cell))


def gate(plan: Path) -> tuple[list[str], list[dict]]:
    """(닫힌 이유, 묶음) — 이유가 없으면 열림."""
    import project_profile
    if project_profile.load_meta().get("profile", {}).get("value") == "lite":
        # 소형은 갈라질 만큼 크지 않다 — 병렬 비용(수렴 · 버스 · 인계)이 이득보다 크다(REQ-261104-17-5)
        return ["⓪ 규모 프로파일이 lite — 병렬 없이 직렬로 간다(바꾸려면 python nova.py profile set product --why …)"], []
    if not plan.exists():
        return [f"마스터플랜이 없다: {plan}"], []
    text = plan.read_text(encoding="utf-8")
    why, decl, bundles = [], table(text, "공통 영역 완료 선언"), table(text, "병렬 묶음")
    if not decl:
        why.append("① '## 공통 영역 완료 선언' 표가 없다 — 모든 프로젝트가 함께 쓰는 기반(CI · DB · 인증 · 화면 틀 · 계약 · 토큰)이 끝났는지 먼저 선언한다")
    for r in decl:
        st, ev = r.get("상태", ""), r.get("증거", "")
        if st not in DONE:
            why.append(f"① 공통 영역 '{r.get('항목', '?')}' 이 '{st or '빈칸'}' — 완료(또는 미해당)가 되기 전에는 갈라지지 않는다")
        elif st == "완료" and ev in ("", "-"):
            why.append(f"① 공통 영역 '{r.get('항목', '?')}' 완료의 증거가 없다(테스트 · 커밋 · 문서 링크)")
    names = [b.get("묶음", "") for b in bundles]
    if len(set(names)) < 2:
        why.append("② '## 병렬 묶음' 표에 묶음이 2개 이상 있어야 한다 — 하나면 갈라질 이유가 없다")
    for n in names:
        if n and not NAME.match(n):
            why.append(f"② 묶음 이름 '{n}' — 영문 소문자 · 숫자 · 하이픈(브랜치 wt-<묶음>)")
    for i, a in enumerate(bundles):
        for b in bundles[i + 1:]:
            for ga in globs(a.get("경로", "")):
                for gb in globs(b.get("경로", "")):
                    if overlap(ga, gb):
                        why.append(f"③ 묶음 '{a.get('묶음')}' 과 '{b.get('묶음')}' 의 경로가 겹친다: {ga} ↔ {gb}")
    return why, bundles


def plan_path(root: Path) -> Path:
    return root / "docs" / "plans" / "master_plan.md"


def install_deps(path: Path) -> None:
    """새 worktree 의 의존성 — uv sync 를 시도하고 실패해도 경고만(worktree 는 이미 만들어졌고 나중에 손으로 할 수 있다)."""
    exe = shutil.which("uv")
    if not exe:
        print("⚠ uv 가 없어 의존성을 설치하지 않았다 — 그 worktree 에서 python nova.py install")
    else:
        r = subprocess.run([exe, "sync", "--all-packages"], cwd=path, capture_output=True, text=True, encoding="utf-8")
        print("✓ uv sync 완료" if r.returncode == 0 else f"⚠ uv sync 실패(경고만) — 그 worktree 에서 다시: {r.stderr.strip()[-300:]}")
    if (path / "web").exists():
        print(f"  웹을 고친다면: cd {path / 'web'} && npm install")


def push_branch(path: Path, branch: str) -> None:
    """원격에 묶음 브랜치를 올려 둔다(다른 PC · 검토자가 볼 수 있게). 원격이 없거나 실패하면 경고만."""
    r = subprocess.run(["git", "push", "-u", "origin", branch], cwd=path, capture_output=True, text=True, encoding="utf-8")
    print(f"✓ git push -u origin {branch}" if r.returncode == 0
          else f"⚠ git push 실패(원격 없음 또는 권한 — 경고만): {(r.stderr or r.stdout).strip()[-300:]}")


def new(bundle: str, *, root: Path | None = None, notify: bool = True, install: bool = True, push: bool = True) -> Path:
    root = root or main_root()
    require_main("worktree 만들기", root)
    why, bundles = gate(plan_path(root))
    if why:
        raise SystemExit("✗ 병렬 게이트 닫힘:\n  " + "\n  ".join(why))
    b = next((x for x in bundles if x.get("묶음") == bundle), None)
    if not b:
        raise SystemExit(f"✗ '{bundle}' 은 병렬 묶음 표에 없다 — 있는 묶음: {', '.join(x.get('묶음', '') for x in bundles)}")
    if git("status", "--porcelain", cwd=root):
        raise SystemExit("✗ 본 작업 트리에 커밋 안 된 변경이 있다 — worktree 는 마지막 커밋에서 갈라지므로 먼저 커밋한다")
    branch, path = f"wt-{bundle}", root / ".worktrees" / f"wt-{bundle}"
    if path.exists():
        raise SystemExit(f"✗ 이미 있다: {path}")
    git("worktree", "add", "-b", branch, str(path), cwd=root)
    if install:
        install_deps(path)
    if push:
        push_branch(path, branch)
    if notify:
        import collab
        body = (f"담당 경로: {b.get('경로', '')}\n담당 요구: {b.get('담당 REQ', b.get('REQ', '-'))}\n\n"
                "규칙\n- 담당 경로 밖은 고치지 않는다(공통부를 바꿔야 하면 main 에 question)\n"
                "- 번호가 붙는 기록(요구 · 계획 · 이력 · git 기록 · 세션)은 쓰지 않는다 — 병합 뒤 main 이 남긴다\n"
                "- 각 REQ 는 종료 조건(exit)이 모두 녹색이면 끝낸다. 새로 보인 것은 report 로 main 에(직접 넓히지 않는다)\n"
                "- 끝나면 test · lint 녹색 → 커밋 → main 에 report(무엇을 · 검증 숫자)\n\n"
                f"시작: cd {path} → claude → /session-start (받은함 확인: python nova.py inbox)")
        collab.send([branch], "handoff", f"{bundle} 묶음 작업 시작", body, sender="main", cwd=root)
    return path


def scratch(name: str, *, root: Path | None = None, notify: bool = True, install: bool = True, push: bool = False) -> Path:
    """격리 작업 폴더 — 병렬 게이트 · 묶음 표를 보지 않는다(같은 파일을 쓰거나 무거운 테스트를 따로 돌릴 때).
    main 이 git worktree add 를 직접 쓰면 버스 등록이 빠진다 — 그 자리를 정식 명령으로 둔다. 원격 푸시는 --push 일 때만."""
    root = root or main_root()
    require_main("격리 작업 폴더 만들기", root)
    if not NAME.match(name):
        raise SystemExit(f"✗ 이름 '{name}' — 영문 소문자로 시작 · 소문자 · 숫자 · 하이픈 2~31자(브랜치 scratch-<이름>)")
    if git("status", "--porcelain", cwd=root):
        raise SystemExit("✗ 본 작업 트리에 커밋 안 된 변경이 있다 — worktree 는 마지막 커밋에서 갈라지므로 먼저 커밋한다")
    branch, path = f"scratch-{name}", root / ".worktrees" / f"scratch-{name}"
    if path.exists():
        raise SystemExit(f"✗ 이미 있다: {path}")
    if _run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root).returncode == 0:
        raise SystemExit(f"✗ 브랜치 {branch} 가 이미 있다 — 다른 이름을 쓰거나 정리(python nova.py worktree-prune)")
    git("worktree", "add", "-b", branch, str(path), cwd=root)
    (path / ".pytest_tmp").mkdir(exist_ok=True)   # 시스템 Temp 권한 문제 — pytest 임시 폴더를 미리 둔다
    if install:
        install_deps(path)
    if push:
        push_branch(path, branch)
    if notify:
        import collab
        body = ("담당: 격리 작업(병렬 묶음 아님 — 게이트 · 묶음 표를 보지 않는다)\n\n"
                "규칙\n- 번호가 붙는 기록(요구 · 계획 · 이력 · git 기록 · 세션)은 쓰지 않는다 — main 이 남긴다\n"
                "- 끝나면 커밋 → main 에 report(무엇을 · 검증 숫자) → 이 메시지를 done\n"
                "- 정리는 main 이 병합 뒤 python nova.py worktree-prune(병합됨 · 미커밋 0 · 받은함 미처리 0(전체 공지 제외) 일 때만 지운다)\n\n"
                f"시작: cd {path} → claude → /session-start (받은함 확인: python nova.py inbox)")
        collab.send([branch], "handoff", f"{name} 격리 작업 시작", body, sender="main", cwd=root)
    return path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """실패해도 예외를 올리지 않는 git 호출 — 정리는 단계마다 결과를 보고 다음으로 간다(시험에서 바꿔 끼운다)."""
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def _rmdir(p: Path) -> None:
    p.rmdir()


def linked_worktrees(root: Path) -> list[tuple[Path, str]]:
    """.worktrees/ 아래 linked worktree 의 (경로, 브랜치) — 브랜치가 없으면(detached) 빈 문자열."""
    base = (root / ".worktrees").resolve()
    out, cur = [], None
    for ln in git("worktree", "list", "--porcelain", cwd=root).splitlines() + [""]:
        if ln.startswith("worktree "):
            cur = [Path(ln[len("worktree "):]), ""]
        elif ln.startswith("branch refs/heads/") and cur:
            cur[1] = ln.split("refs/heads/", 1)[1]
        elif not ln.strip() and cur:
            p = cur[0].resolve()
            if p.parent == base:
                out.append((root / ".worktrees" / p.name, cur[1]))
            cur = None
    return out


def prune(*, root: Path | None = None, yes: bool = False) -> list[dict]:
    """병합 끝난 worktree 정리 — (a) main 에 병합됨 (b) 미커밋 변경 0 (c) 그 브랜치 받은함 미처리 0 인 것만
    ((c) 에서 전체 공지 — to * · type report — 는 세지 않는다).
    기본은 판정만 보여 준다. yes 일 때만 worktree remove → 로컬 브랜치 삭제. 원격 브랜치는 지우지 않는다."""
    import collab
    root = root or main_root()
    require_main("worktree 정리", root)
    main_b = current_branch(root)
    rows = []
    for path, branch in linked_worktrees(root):
        why = []
        if not branch:
            why.append("브랜치 없음(detached) — 손으로 판단한다")
        else:
            if _run(["git", "merge-base", "--is-ancestor", branch, main_b], root).returncode != 0:
                why.append(f"{main_b} 에 병합 안 됨")
            if path.exists():
                st = _run(["git", "status", "--porcelain"], path)
                if st.returncode != 0:
                    why.append(f"상태를 읽지 못함: {st.stderr.strip()[-200:]}")
                elif st.stdout.strip():
                    why.append(f"미커밋 변경 {len(st.stdout.strip().splitlines())}개")
            # 전체 공지(to * · report — converge 의 "main 갱신")는 세지 않는다: 병합된 worktree 에는 따라올 일이 없다.
            # 직접 받은 것과 전체에 보낸 질문 · 인계는 답이 필요하므로 계속 막는다
            n = len([m for m in collab.pending(branch, root)
                     if not ("*" in m["to"] and m.get("type") == "report")])
            if n:
                why.append(f"받은함 미처리 {n}개(python nova.py inbox — 끝내면 done)")
        rows.append({"branch": branch, "path": str(path), "ok": not why, "why": why, "removed": False, "leftover": ""})
    if not rows:
        print("■ .worktrees/ 아래 worktree 없음 — 정리할 것 없음")
        return rows
    print(f"■ worktree 정리 판정(기준 {main_b}){'' if yes else ' — 보여 주기만(지우려면 --yes)'}")
    for r in rows:
        print(f"  {'정리' if r['ok'] else '남김'} {r['branch'] or '(detached)'} · {r['path']}"
              + ("" if r["ok"] else " — " + " · ".join(r["why"])))
    if not yes:
        return rows
    for r in rows:
        if r["ok"]:
            _remove(root, r)
    if any(r["removed"] for r in rows):
        print("  원격 브랜치는 지우지 않았다 — 필요하면: git push origin --delete <브랜치>")
    return rows


def _remove(root: Path, r: dict) -> None:
    """한 worktree 정리. 폴더 삭제 실패(Windows — 다른 창이 잡고 있음)가 브랜치 삭제를 막지 않게 단계를 잇지 않고 따로 본다."""
    path, branch = Path(r["path"]), r["branch"]
    rm = _run(["git", "worktree", "remove", str(path)], root)
    if rm.returncode != 0:
        # 등록은 풀리고 폴더 삭제만 실패했을 수 있다 — 등록 찌꺼기를 걷어 내고 브랜치 정리로 간다
        print(f"  ⚠ worktree remove 실패(계속 진행): {(rm.stderr or rm.stdout).strip()[-200:]}")
        _run(["git", "worktree", "prune"], root)
    if any(b == branch for _, b in linked_worktrees(root)):
        print(f"  ✗ {branch} — worktree 등록이 남아 브랜치를 지우지 않았다(git worktree list 로 확인)")
        return
    br = _run(["git", "branch", "-d", branch], root)
    if br.returncode != 0:
        print(f"  ✗ {branch} 로컬 브랜치 삭제 실패: {(br.stderr or br.stdout).strip()[-200:]}")
        return
    r["removed"] = True
    if path.exists():
        try:
            _rmdir(path)
        except OSError:
            r["leftover"] = str(path)
    print(f"  ✓ 정리: {branch}" + (f"\n  ⚠ 남은 폴더 — 잡고 있는 창을 닫고 지우세요: {r['leftover']}" if r["leftover"] else ""))


def worktree_branches(root: Path) -> list[str]:
    return [ln.split("refs/heads/", 1)[1] for ln in git("worktree", "list", "--porcelain", cwd=root).splitlines()
            if ln.startswith("branch refs/heads/")]


def converge(bundle: str, *, root: Path | None = None, verify: bool = False, notify: bool = True) -> str:
    root = root or main_root()
    require_main("병합(converge)", root)
    branch = f"wt-{bundle}"
    if git("status", "--porcelain", cwd=root):
        raise SystemExit("✗ 본 작업 트리에 커밋 안 된 변경이 있다 — 병합 전에 정리한다")
    wt = root / ".worktrees" / branch
    if wt.exists() and git("status", "--porcelain", cwd=wt):
        raise SystemExit(f"✗ {branch} 에 커밋 안 된 변경이 있다 — 그 worktree 에서 커밋하고 다시")
    _, bundles = gate(plan_path(root))
    b = next((x for x in bundles if x.get("묶음") == bundle), None)
    if not b:
        raise SystemExit(f"✗ '{bundle}' 은 병렬 묶음 표에 없다 — 경로를 모르면 병합 범위를 검사할 수 없다")
    # --no-renames: 이름 바꾸기를 '옛 경로 삭제 + 새 경로 추가'로 본다 — 감지가 켜져 있으면 새 경로만 나와 밖 → 안 git mv 가 검사를 빠져나간다
    changed = [f for f in git("diff", "--name-only", "--no-renames", f"HEAD...{branch}", cwd=root).splitlines() if f]
    outside = [f for f in changed if f != HANDOFF and not in_bundle(f, b.get("경로", ""))]
    if outside:
        raise SystemExit(f"✗ 묶음 '{bundle}' 의 경로({b.get('경로', '')}) 밖 파일이 있다 — 병합하지 않았다:\n  " + "\n  ".join(outside)
                         + "\n  공통부 · 다른 묶음의 변경은 main 에서 따로 한다(그 worktree 에서 되돌리고 main 에 question)")
    r = subprocess.run(["git", "merge", "--no-ff", branch, "-m", f"merge: {branch} 병합(/converge)"], cwd=root,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        subprocess.run(["git", "merge", "--abort"], cwd=root, capture_output=True)
        raise SystemExit(f"✗ 병합 충돌 — 되돌렸다. 충돌 파일을 보고 다시:\n{r.stdout}{r.stderr}")
    if HANDOFF in changed and (root / HANDOFF).exists():
        print(f"■ {branch} 의 {HANDOFF}\n{(root / HANDOFF).read_text(encoding='utf-8').rstrip()}\n"
              f"  → 이 내용을 /history-new 기록의 부록(history)으로 옮긴 뒤 지운다(git rm {HANDOFF})")
    if verify:
        for cmd in (["nova.py", "test"], ["nova.py", "lint"]):
            v = subprocess.run([py(), *cmd], cwd=root)
            if v.returncode != 0:
                raise SystemExit(f"✗ 병합 뒤 {' '.join(cmd)} 실패 — 고치거나 되돌린다(git reset --hard ORIG_HEAD)")
    others = [x for x in worktree_branches(root) if x != branch and x.startswith("wt-")]
    if notify and others:
        import collab
        collab.send(["*"], "report", "main 갱신 — /worktree-sync",
                    f"{branch} 가 main 에 병합됐다(파일 {len(changed)}개). 각 worktree 에서 커밋한 뒤 python nova.py worktree-sync 로 따라잡는다.\n"
                    f"남은 worktree: {', '.join(others)}", sender="main", cwd=root)
    return git("log", "-1", "--format=%h %s", cwd=root)


REBRANCH = 20   # 이보다 많이 뒤처지면 보고에 재분기 권고(브랜치만 main 에서 새로 딴다)


def classify(f: str, mine: dict | None, bundles: list[dict]) -> str:
    """들어올 파일의 부류 — 공통부 목록의 정본은 upstream.COMMON 이다."""
    import upstream
    if upstream.in_scope(f):
        return "공통부"
    if f.startswith("docs/"):
        return "기록"
    if mine and in_bundle(f, mine.get("경로", "")):
        return "내 묶음"
    if any(in_bundle(f, b.get("경로", "")) for b in bundles if b is not mine):
        return "다른 묶음"
    return "그 밖"


def conflict_advice(files: list[str], mine: dict | None, bundles: list[dict]) -> dict[str, str]:
    """충돌 처방을 경로 부류로 정한다(판단하지 않는다). 공통부를 브랜치 쪽으로 맞추면 main 정본이 조용히 되돌려진다."""
    rule = {
        "공통부": "main 채택 — 브랜치 쪽 변경이 필요하면 main 에 question(상행 요청)",
        "기록": "main 채택 + 보고 — worktree 는 기록을 쓰지 않으므로 충돌 자체가 단일 기록자 위반 신호",
        "내 묶음": "브랜치 채택 — 내 묶음 경로는 이 브랜치가 쓴다",
        "다른 묶음": "정지 — 다른 묶음 경로를 이 브랜치가 고쳤다. 사용자 판정",
        "그 밖": "정지 — 규칙에 없는 자리. 추측으로 맞추지 않고 사용자 판정",
    }
    return {f: rule[classify(f, mine, bundles)] for f in files}


def sync(*, cwd: Path | None = None, notify: bool = True, dry: bool = False) -> dict:
    """worktree 에서 main 을 따라잡는다 — merge 만(rebase 는 이미 버스 · 검토에 적힌 커밋 해시를 바꾼다).
    dry 면 갈라 보이기만 한다 — 공통부의 파괴적 변경을 읽고 멈출 자리(관문)가 병합 앞에 있어야 하므로."""
    cwd = Path(cwd or Path.cwd())
    if not in_linked_worktree(cwd):
        raise SystemExit("✗ worktree-sync 는 worktree 안에서만 쓴다 — 본 작업 트리는 main 그 자체다")
    if git("status", "--porcelain", cwd=cwd):
        raise SystemExit("✗ 커밋 안 된 변경이 있다 — 먼저 커밋한 뒤 다시(병합이 작업 중인 파일을 덮지 않게)")
    root = main_root(cwd)
    main_b, me = current_branch(root), current_branch(cwd)
    behind = int(git("rev-list", "--count", f"HEAD..{main_b}", cwd=cwd))
    base_before = git("rev-parse", "--short", git("merge-base", "HEAD", main_b, cwd=cwd), cwd=cwd)
    if behind == 0:
        print(f"✓ {me} 은 {main_b} 를 이미 품고 있다 — 받을 것 없음(상속 기준 {main_b}@{base_before})")
        return {"behind": 0, "groups": {}, "merged": False, "dry": dry, "base_before": base_before, "mine_known": True}
    files = [f for f in git("diff", "--name-only", "--no-renames", f"HEAD...{main_b}", cwd=cwd).splitlines() if f]   # 옛 경로도 부류에 넣는다(converge 와 같은 이유)
    _, bundles = gate(plan_path(root))
    mine = next((b for b in bundles if f"wt-{b.get('묶음')}" == me), None)
    groups: dict[str, list[str]] = {"공통부": [], "기록": [], "내 묶음": [], "다른 묶음": [], "그 밖": []}
    for f in files:
        groups[classify(f, mine, bundles)].append(f)
    print(f"■ {me} ← {main_b}: {behind}커밋 · 파일 {len(files)}개 · 상속 기준 {main_b}@{base_before}")
    for k, fs in groups.items():
        if fs:
            print(f"  {k} {len(fs)}: " + ", ".join(fs[:12]) + (" …" if len(fs) > 12 else ""))
    if not mine:   # 0개와 판정 불가를 구분한다 — 행이 없으면 '내 묶음 0개'가 아니라 모르는 것이다
        print(f"  ⚠ 내 묶음 판정 불가 — 마스터플랜 '병렬 묶음' 표에 '{me.removeprefix('wt-')}' 행이 없다(내 묶음 · 다른 묶음 수를 믿지 않는다)")
    if behind > REBRANCH:
        print(f"  ⚠ {behind}커밋 뒤처짐(>{REBRANCH}) — 재분기 권고: 커밋 뒤 브랜치만 main 에서 새로 딴다. 계속할지는 사용자가 정한다")
    result = {"behind": behind, "groups": groups, "merged": False, "dry": dry, "base_before": base_before,
              "mine_known": mine is not None}
    if dry:
        print(f"  (--dry) 병합하지 않았다 — 공통부 diff 를 읽고(git diff HEAD...{main_b} -- <경로>) 파괴적 변경이 없으면 다시 실행")
        return result
    r = subprocess.run(["git", "merge", main_b, "--no-edit"], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        conflicts = [f for f in git("diff", "--name-only", "--diff-filter=U", cwd=cwd).splitlines() if f]
        subprocess.run(["git", "merge", "--abort"], cwd=cwd, capture_output=True)
        adv = conflict_advice(conflicts, mine, bundles)
        raise SystemExit("✗ 병합 충돌 — 되돌렸다(아무것도 바뀌지 않음). 충돌 파일과 처방(경로 부류로 정한다):\n  "
                         + ("\n  ".join(f"{f} → {a}" for f, a in adv.items()) or r.stdout + r.stderr)
                         + "\n  맞춘 뒤 다시: python nova.py worktree-sync")
    base_after = git("rev-parse", "--short", main_b, cwd=cwd)
    result.update(merged=True, base_after=base_after)
    if notify:
        import collab
        collab.send(["main"], "report", f"{me} — main 따라잡음({behind}커밋)",
                    f"상속 기준 {main_b}@{base_before} → {main_b}@{base_after}\n"
                    + "\n".join(f"{k}: {len(fs)}개" for k, fs in groups.items() if fs)
                    + ("" if mine else "\n내 묶음 판정 불가(묶음 표에 행 없음)"), cwd=cwd)
    print(f"✓ merge {main_b} → {me} · 상속 기준 {main_b}@{base_before} → {main_b}@{base_after}"
          + (" · main 에 보고를 보냈다" if notify else "") + "\n  다음: python nova.py check(격리 재검증 — 빨강이면 멈춘다)")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gate")
    sub.add_parser("list")
    n = sub.add_parser("new")
    n.add_argument("bundle", nargs="?")
    n.add_argument("--scratch", metavar="이름", help="격리 작업 폴더(게이트 · 묶음 표를 보지 않는다) — 브랜치 scratch-<이름>")
    n.add_argument("--no-install", action="store_true", help="uv sync 를 하지 않는다")
    n.add_argument("--no-push", action="store_true", help="원격에 브랜치를 올리지 않는다(묶음)")
    n.add_argument("--push", action="store_true", help="격리 작업 브랜치를 원격에 올린다(기본은 올리지 않음)")
    pr = sub.add_parser("prune")
    pr.add_argument("--yes", action="store_true", help="판정만 보이지 않고 실제로 지운다")
    sy = sub.add_parser("sync")
    sy.add_argument("--dry", action="store_true", help="갈라 보이기만 하고 병합하지 않는다(파괴적 변경 판독용)")
    c = sub.add_parser("converge")
    c.add_argument("bundle")
    c.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "gate":
        why, bundles = gate(plan_path(main_root()))
        if why:
            print("✗ 병렬 게이트 닫힘 — 직렬로 진행한다")
            for w in why:
                print("  " + w)
            return 1
        print(f"✓ 병렬 게이트 열림 — 묶음 {len(bundles)}개: {', '.join(b['묶음'] for b in bundles)}")
        return 0
    if a.cmd == "new" and (bool(a.bundle) == bool(a.scratch)):
        ap.error("new 는 <묶음> 또는 --scratch <이름> 중 하나만 준다")
    if a.cmd == "new" and a.scratch:
        p = scratch(a.scratch, install=not a.no_install, push=a.push)
        print(f"✓ 격리 작업 폴더 {p} (브랜치 scratch-{a.scratch}) · 인계 카드를 버스로 보냄\n  다음: cd {p} → claude → /session-start")
        return 0
    if a.cmd == "prune":
        prune(yes=a.yes)
        return 0
    if a.cmd == "new":
        p = new(a.bundle, install=not a.no_install, push=not a.no_push)
        print(f"✓ worktree {p} (브랜치 wt-{a.bundle}) · 인계 카드를 버스로 보냄\n  다음: cd {p} → claude → /session-start")
        return 0
    if a.cmd == "sync":
        sync(dry=a.dry)
        return 0
    if a.cmd == "converge":
        print(f"✓ 병합: {converge(a.bundle, verify=a.verify)}\n  다음: main 에서 /history-new · git_record.py (단일 기록자)")
        return 0
    print(git("worktree", "list", cwd=main_root()))
    _, bundles = gate(plan_path(main_root()))
    for b in bundles:
        p = main_root() / ".worktrees" / f"wt-{b.get('묶음')}"
        print(f"  {b.get('묶음')}: {'있음' if p.exists() else '아직 없음'} · {b.get('경로', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
