#!/usr/bin/env python3
"""상류 판본 받기 — Nova 에서 만든 프로젝트(복제본)가 Nova 의 새 판본에서 **공통부만** 검증하며 받는다.

  python nova.py upstream status            nova.project.json 의 upstream(url · base · tag) · 최신 정식 태그 · 그 사이 판본 수
  python nova.py upstream tags              상류의 정식 태그 목록과 내 기준 판본(받을 판본은 사람이 고른다)
  python nova.py upstream plan <태그> [--allow-ref]   dry-run — 파일마다 3-way 판정(쓰기 0건) · 건너뛰는 판본의 '복제본이 받을 때'
  python nova.py upstream apply <태그> [--allow-ref]  surface 가 하나도 없을 때만 적용(스냅샷 → 적용 → base 갱신 → 채택 기록)
  대상은 정식 태그(vX.Y.Z)만 — 최신을 자동으로 고르지 않는다. 사전 판본 · 브랜치 · 커밋은 --allow-ref(규약 docs/conventions/versioning.md)

3-way 판정(base = 내가 선 상류 판본 · theirs = 받을 판본 · mine = 내 작업 트리, 내용 sha256 비교):
  replace  내가 안 건드렸다(mine == base) → 상류 것으로 바꾼다
  already  이미 그 내용이다(mine == theirs)
  add      상류가 새로 만들었다(base · mine 없음)
  skip     받을 것이 없다 — 복제본이 만든 것(theirs · base 없음) · 상류가 안 바꿨다(base == theirs)
  surface  그 밖 — 양쪽이 바꿨다 · 상류가 지웠다 · 같은 경로를 각자 만들었다 → 사람이 본다
원자성: surface 가 하나라도 있으면 apply 는 아무것도 쓰지 않는다(부분 적용 뒤 base 를 올리면 다음 판정의 기준선이 틀린다).
참고: project-start-guide-05 scripts/sync-upstream.mjs decide() 를 Nova 공통부에 맞게 줄였다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import versions  # noqa: E402
from novalib import ROOT, require_main, write  # noqa: E402

# 공통부 — 상류(Nova)가 주인인 경로. 이 상수 하나가 정본이다(worktree-sync 도 이것으로 들어올 변경을 가른다)
COMMON = (
    "packages/common-py/nova_common/",
    "scripts/",
    ".claude/commands/",
    ".claude/skills/",
    ".claude/agents/",
    ".claude/hooks/",
    "docs/conventions/",
    "docs/std/",
    "design/tokens/",
    "web/packages/",
    "apps/kmp/uikit/",
    "infra/docker/",
    "registry/naming.json",
    "packs/_template/",       # 팩 틀(도메인 에이전트 틀 agent.md 포함) — 틀이 바뀌면 복제본은 packs.py agent <팩> 로 다시 만든다   # 명명 규약 선언 정본 — naming.md 생성 구간과 짝(파일 하나도 접두 비교로 들어간다)
)
# 프로젝트가 원천을 바꾸는 곳 — 바뀐 것이 있으면 자동으로 덮어쓰지 않고 surface 로 올린다
SURFACE_ONLY = ("design/tokens/",)
# 공통부 안이지만 프로젝트 소유 · 생성물(적용 뒤 python nova.py gen 이 다시 만든다)
EXCLUDE = (
    "packages/common-py/nova_common/services.json",
    ".claude/agents/README.md",   # 편제표는 생성물 — 적용 뒤 claude_check.py --write 가 다시 만든다
    "web/packages/ui/src/tokens.css",
    "apps/kmp/uikit/src/commonMain/kotlin/kr/nova/uikit/DesignTokens.kt",
)
JUNK = ("__pycache__/", "node_modules/", "/build/", "/.gradle/", "/dist/")
VERDICTS = ("replace", "already", "add", "skip", "surface")
KO = {"replace": "바꿈", "already": "이미 같음", "add": "새 파일", "skip": "건너뜀", "surface": "사람 확인"}


def in_scope(path: str) -> bool:
    p = path.replace("\\", "/")
    if p in EXCLUDE or p.endswith((".pyc", ".tsbuildinfo")) or any(j in "/" + p for j in JUNK):
        return False
    if p.startswith(".claude/agents/domain/") or (p.startswith(".claude/agents/") and p.endswith("-specialist.md")):
        return False   # 도메인 에이전트는 프로젝트 소유(팩과 짝) — 틀은 packs/_template/agent.md 로 받는다
    return p.startswith(COMMON)


def digest(data: bytes) -> str:
    """줄 끝(CRLF/LF)은 내용 차이로 보지 않는다 — Windows 작업 트리와 git 객체를 같은 잣대로 잰다."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def decide(base: str | None, theirs: str | None, mine: str | None) -> tuple[str, str]:
    """세 해시(없으면 None)로 판정 하나와 이유. 순수 함수."""
    if theirs is None:
        if base is None:
            return ("skip", "복제본이 만든 파일 — 상류에 대응물이 없다(건드리지 않는다)") if mine is not None else ("already", "어디에도 없다")
        if mine is None:
            return "already", "상류도 복제본도 지웠다"
        return "surface", "상류가 지웠다 — 삭제는 판단이라 자동으로 하지 않는다"
    if base is None:
        if mine is None:
            return "add", "상류가 새로 만든 파일"
        if mine == theirs:
            return "already", "기준선에는 없지만 양쪽이 같다"
        return "surface", "양쪽이 같은 경로를 각자 만들었고 내용이 다르다"
    if mine is None:
        if base == theirs:
            return "skip", "복제본이 지웠고 상류는 그대로다 — 되살리지 않는다"
        return "surface", "복제본이 지웠는데 상류는 바꿨다"
    if mine == theirs:
        return "already", "이미 그 내용이다"
    if mine == base:
        return "replace", "내가 안 건드렸다"
    if base == theirs:
        return "skip", "복제본만 고쳤고 상류는 안 바꿨다 — 받을 것이 없다"
    return "surface", "상류와 복제본이 둘 다 바꿨다"


def classify(files_base: dict[str, str], files_theirs: dict[str, str], files_mine: dict[str, str]) -> dict[str, tuple[str, str]]:
    """경로 → (판정, 이유). 공통부 밖은 판정하지 않는다. 토큰 원천은 바뀐 것이 있으면 surface."""
    out = {}
    for p in sorted(set(files_base) | set(files_theirs) | set(files_mine)):
        if not in_scope(p):
            continue
        v, why = decide(files_base.get(p), files_theirs.get(p), files_mine.get(p))
        if p.startswith(SURFACE_ONLY) and v in ("replace", "add"):
            v, why = "surface", f"토큰 원천은 프로젝트가 바꾼다 — 상류 변경을 직접 옮긴다({why})"
        out[p] = (v, why)
    return out


# ───────────────────────── git 읽기
def _git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    r = subprocess.run(["git", *args], cwd=root, input=data, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"✗ git {' '.join(args)} 실패: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout


def resolve(root: Path, url: str, ref: str) -> str:
    """ref(태그 · 커밋)를 커밋 해시로. 커밋 해시는 로컬에 있으면 그대로, 태그 이름은 늘 상류에서 받는다
    (복제본에 같은 이름의 자기 태그가 있어도 섞이지 않게)."""
    if re.fullmatch(r"[0-9a-f]{7,64}", ref):
        r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], cwd=root, capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip()
    _git(root, "fetch", "-q", "--no-tags", url, ref)
    return _git(root, "rev-parse", "FETCH_HEAD^{commit}").decode().strip()


def tree(root: Path, commit: str) -> dict[str, bytes]:
    """커밋의 공통부 파일 → 내용(git cat-file --batch 한 번)."""
    rows = [ln.split(b"\t", 1) for ln in _git(root, "ls-tree", "-r", "-z", commit).split(b"\0") if ln]
    want = [(meta.split()[2].decode(), path.decode("utf-8")) for meta, path in rows
            if meta.split()[1] == b"blob" and in_scope(path.decode("utf-8"))]
    if not want:
        return {}
    raw = _git(root, "cat-file", "--batch", data="".join(f"{oid}\n" for oid, _ in want).encode())
    out, i = {}, 0
    for _, path in want:
        nl = raw.index(b"\n", i)
        size = int(raw[i:nl].split()[2])
        out[path] = raw[nl + 1: nl + 1 + size]
        i = nl + 1 + size + 1
    return out


def worktree_files(root: Path) -> dict[str, bytes]:
    r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root, capture_output=True)
    if r.returncode == 0:
        paths = [p.decode("utf-8") for p in r.stdout.split(b"\0") if p]
    else:   # git 저장소가 아니면 공통부 폴더를 직접 훑는다
        paths = [f.relative_to(root).as_posix() for c in COMMON if (root / c).exists() for f in (root / c).rglob("*") if f.is_file()]
    return {p: (root / p).read_bytes() for p in paths if in_scope(p) and (root / p).is_file()}


# ───────────────────────── 계획 · 적용
def meta_of(root: Path) -> dict:
    return json.loads((root / "nova.project.json").read_text(encoding="utf-8"))


def upstream_of(root: Path) -> dict:
    meta = meta_of(root)
    if meta.get("slug") == "nova":
        raise SystemExit("✗ 이 저장소는 Nova 자신이다 — 상류가 아니라 원천이다(복제본이 여기서 받는다)")
    u = meta.get("upstream") or {}
    if not u.get("url"):
        raise SystemExit('✗ nova.project.json 에 upstream.url 이 없다 — {"upstream": {"url": "<Nova 원격 또는 경로>", "base": "<선 판본 커밋>"}}')
    return u


def require_formal(tag: str, allow_ref: bool) -> None:
    """받을 대상은 정식 태그(vX.Y.Z)만 — 사전 판본 · 브랜치 · 커밋은 사람이 --allow-ref 로 풀 때만(규약 versioning.md §4 · §6)."""
    if not allow_ref and not versions.is_formal(tag):
        raise SystemExit(f"✗ 받을 대상은 정식 태그(vX.Y.Z)만이다: {tag} — 사전 판본 · 브랜치 · 커밋을 받으려면 --allow-ref"
                         "(후보: python nova.py upstream tags)")


def formal_remote(u: dict, root: Path) -> dict[str, str]:
    """상류의 정식 태그 → 커밋. 닿지 못하면 RuntimeError."""
    return {t: c for t, c in versions.remote_tags(u["url"], root).items() if versions.is_formal(t)}


def clone_section(text: str) -> str:
    m = re.search(r"^## 복제본이 받을 때[^\n]*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else "(노트에 '복제본이 받을 때' 절이 없다 — 노트의 '바뀐 것'을 읽는다)"


def skipped_notes(u: dict, target: str, root: Path) -> list[tuple[str, str, str]]:
    """내 기준 판본(upstream.tag) 뒤부터 대상까지 정식 판본마다 노트의 '복제본이 받을 때' 절 — (태그, 건너뜀|대상, 본문).
    기준 판본을 모르거나 상류에 닿지 못하면 빈 목록(report 가 그 사실을 말한다)."""
    mine = u.get("tag", "")
    if not versions.valid(mine) or not versions.valid(target):
        return []
    try:
        tags = formal_remote(u, root)
    except RuntimeError:
        return []
    want = [t for t in versions.formal_sorted(tags) if versions.key(mine) < versions.key(t) < versions.key(target)]
    out = []
    for t in [*want, target]:
        r = subprocess.run(["git", "fetch", "-q", "--no-tags", u["url"], f"refs/tags/{t}"], cwd=root, capture_output=True)
        note = subprocess.run(["git", "show", f"FETCH_HEAD:docs/releases/{t}.md"], cwd=root, capture_output=True) if r.returncode == 0 else r
        body = clone_section(note.stdout.decode("utf-8", "replace")) if note.returncode == 0 else "(노트 docs/releases/" + t + ".md 를 읽지 못했다)"
        out.append((t, "대상" if t == target else "건너뜀", body))
    return out


def plan(tag: str, root: Path = ROOT, allow_ref: bool = False) -> dict:
    require_formal(tag, allow_ref)
    u = upstream_of(root)
    theirs_c = resolve(root, u["url"], tag)
    base_c = resolve(root, u["url"], u["base"]) if u.get("base") else ""
    theirs = tree(root, theirs_c)
    base = tree(root, base_c) if base_c else {}
    mine = worktree_files(root)
    files = classify({p: digest(b) for p, b in base.items()}, {p: digest(b) for p, b in theirs.items()},
                     {p: digest(b) for p, b in mine.items()})
    return {"tag": tag, "url": u["url"], "base": base_c, "theirs": theirs_c, "files": files, "_content": theirs,
            "no_base": not base_c, "mine_tag": u.get("tag", ""), "notes": skipped_notes(u, tag, root)}


def counts(files: dict) -> dict[str, int]:
    return {v: sum(1 for x, _ in files.values() if x == v) for v in VERDICTS}


def report(res: dict) -> None:
    c = counts(res["files"])
    print(f"■ 상류 {res['tag']} ({res['theirs'][:10]}) ← 기준선 {res['base'][:10] or '(없음)'} · 공통부 {len(res['files'])}개 파일")
    if res["no_base"]:
        print("  ⚠ 기준선(upstream.base)이 비어 있다 — 상류와 내용이 다른 파일은 모두 surface 로 잡힌다")
    print("  " + " · ".join(f"{KO[v]}({v}) {c[v]}" for v in VERDICTS))
    for v in ("surface", "replace", "add"):
        for p, (x, why) in res["files"].items():
            if x == v:
                print(f"  {'✗' if v == 'surface' else '·'} {v:8} {p} — {why}")
    notes = res.get("notes") or []
    if notes:
        n = sum(1 for _, kind, _ in notes if kind == "건너뜀")
        print(f"■ 내 기준 {res.get('mine_tag')} → {res['tag']} · 건너뛰는 판본 {n}개 — 판본마다 '복제본이 받을 때'를 먼저 읽는다")
        for t, kind, body in notes:
            print(f"  [{t} · {kind}]")
            for ln in body.splitlines():
                print(f"    {ln}")
    elif not versions.valid(res.get("mine_tag") or ""):
        print("  ⚠ 내 기준 판본(upstream.tag)을 모른다 — 건너뛰는 판본의 노트를 직접 읽는다(python nova.py upstream tags)")


def apply(tag: str, root: Path = ROOT, allow_ref: bool = False) -> dict:
    require_main("상류 판본 적용", root)
    res = plan(tag, root, allow_ref)
    report(res)
    surf = [p for p, (v, _) in res["files"].items() if v == "surface"]
    if surf:
        print(f"✗ surface {len(surf)}건 — 아무것도 쓰지 않았다. 각 파일을 직접 맞춘 뒤(상류 것을 옮기거나 base 로 되돌리기) 다시 plan")
        raise SystemExit(1)
    todo = [p for p, (v, _) in res["files"].items() if v in ("replace", "add")]
    now = dt.datetime.now()
    snap_rel = f"docs/releases/upstream/{now:%Y%m%dT%H%M%S}"
    snap = root / snap_rel
    for p in todo:                                      # 덮어쓸 파일을 먼저 남긴다(되돌리기 = 이 폴더를 다시 복사)
        if (root / p).exists():
            (snap / p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / p, snap / p)
    c = counts(res["files"])
    write(snap / "manifest.json", json.dumps({"tag": tag, "from": res["base"], "to": res["theirs"], "url": res["url"],
                                              "replace": [p for p in todo if res["files"][p][0] == "replace"],
                                              "add": [p for p in todo if res["files"][p][0] == "add"]},
                                             ensure_ascii=False, indent=2) + "\n")
    for p in todo:
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_bytes(res["_content"][p])
    meta = meta_of(root)
    meta["upstream"] = {**meta.get("upstream", {}), "base": res["theirs"], "tag": tag}
    write(root / "nova.project.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    led_p = root / "docs" / "releases" / "adoption.json"
    led = json.loads(led_p.read_text(encoding="utf-8")) if led_p.exists() else {"adoptions": []}
    row = {"date": now.isoformat(timespec="seconds"), "tag": tag, "from": res["base"], "to": res["theirs"],
           "replace": c["replace"], "add": c["add"], "already": c["already"], "skip": c["skip"], "snapshot": snap_rel}
    led["adoptions"].append(row)
    write(led_p, json.dumps(led, ensure_ascii=False, indent=2) + "\n")
    print(f"✓ {tag} 적용 — 바꿈 {c['replace']} · 새 파일 {c['add']} · 스냅샷 {snap_rel}")
    print("  다음: python nova.py gen(생성물) → uv run python scripts/claude_check.py --write(편제표) → python nova.py check → /history-new")
    return row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("tags")
    for n in ("plan", "apply"):
        sp = sub.add_parser(n)
        sp.add_argument("tag")
        sp.add_argument("--allow-ref", action="store_true", help="정식 태그가 아닌 대상(사전 판본 · 브랜치 · 커밋)도 받는다")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if a.cmd in ("status", "tags"):
        meta = meta_of(root)
        if meta.get("slug") == "nova":
            latest = versions.latest_formal(versions.local_tags(root))
            print("■ 이 저장소는 Nova 자신 — 상류가 아니라 원천이다. 복제본은 nova.project.json upstream 으로 여기서 판본을 받는다"
                  f"\n  최신 정식 태그(로컬): {latest or '(없음)'}")
            return 0
        u = meta.get("upstream") or {}
        if a.cmd == "status":
            print(f"■ 상류 url  : {u.get('url') or '(없음)'}\n  기준선 base: {u.get('base') or '(없음)'}" + (f" · 태그 {u['tag']}" if u.get("tag") else ""))
        if not u.get("url"):
            print("  ⚠ upstream.url 이 없다 — 판본 후보를 볼 수 없다")
            return 0
        try:
            tags = formal_remote(u, root)
        except RuntimeError as e:
            print(f"  ⚠ 상류에 닿지 못함 — {e}")
            return 0
        mine = u.get("tag") or next((t for t, c in tags.items() if c == u.get("base")), "")
        order = versions.formal_sorted(tags)
        latest = order[-1] if order else ""
        gap = sum(1 for t in order if versions.valid(mine) and versions.key(t) > versions.key(mine))
        print(f"  최신 정식 {latest or '(없음)'} · 내 기준 {mine or '(모름)'}"
              + (f" · 사이 정식 판본 {gap}개" if versions.valid(mine) else ""))
        if a.cmd == "status":
            print(f"  공통부: {' · '.join(COMMON)}")
            return 0
        for t in reversed(order):
            print(f"  {t}  {tags[t][:10]}" + ("  ← 내 기준" if t == mine else ""))
        print("  받을 판본은 사람이 고른다 — plan · apply 는 최신을 자동으로 고르지 않는다: python nova.py upstream plan <태그>")
        return 0
    if a.cmd == "plan":
        res = plan(a.tag, root, a.allow_ref)
        report(res)
        n = counts(res["files"])["surface"]
        print(f"  (dry-run — 쓰지 않았다) {'surface 를 먼저 맞춘다' if n else '다음: python nova.py upstream apply ' + a.tag}")
        return 1 if n else 0
    apply(a.tag, root, a.allow_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
